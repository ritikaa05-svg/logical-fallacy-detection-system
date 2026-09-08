"""
Z3 SMT Solver Service — Updated with LLM-assisted translation.
"""

import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass

from backend.app.config import settings
from backend.app.core.telemetry import metrics
from backend.app.services.llm_translator import llm_to_smt

logger = logging.getLogger(__name__)


@dataclass
class Z3Result:
    status: str
    parsing_confidence: float
    smt_script: str | None = None
    model: str | None = None
    error_message: str | None = None
    latency_ms: float = 0.0


class Z3Service:
    CONCLUSION_MARKERS = [
        "therefore",
        "hence",
        "thus",
        "so",
        "consequently",
        "it follows that",
        "we can conclude",
        "in conclusion",
    ]

    def __init__(self):
        self._solver_path = "z3"
        try:
            subprocess.run([self._solver_path, "--version"], capture_output=True, text=True, timeout=5)
            logger.debug("Z3 solver verified")
        except Exception:
            logger.warning("Z3 not found — formal verification disabled")
            self._solver_path = None

    IMPLICATION_MARKERS = [
        "leads to",
        "results in",
        "implies",
        "causes",
        "means that",
        "if",
        "when",
        "whenever",
        "since",
    ]

    def _extract_logical_structure_regex(self, text: str) -> tuple[list[str], str, float]:
        """Extract premises and conclusion using discourse markers (legacy fallback)."""
        text.lower()
        premises = []
        conclusion = ""
        confidence = 1.0

        # 1. Split into primary segments using conclusion markers
        found_marker = False
        for marker in self.CONCLUSION_MARKERS:
            # Look for marker after punctuation, whitespace, or at start of string
            # Captures until next punctuation or end of string
            pattern = re.compile(rf"(?:^|[.,;!?\n])\s*{marker}\s*[,]?\s*([^.!?\n]+)", re.IGNORECASE)
            match = pattern.search(text)
            if match:
                conclusion = match.group(1).strip()
                premise_part = text[: match.start()].strip()
                # Split premise part into individual claims
                premises = [s.strip().rstrip(".!?") for s in re.split(r"[.!?\n]\s*", premise_part) if s.strip()]
                confidence = 0.85
                found_marker = True
                break

        # 2. Fallback: last sentence is conclusion
        if not found_marker:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", text) if s.strip()]
            if len(sentences) >= 2:
                conclusion = sentences[-1].strip().rstrip(".!?")
                premises = [s.strip().rstrip(".!?") for s in sentences[:-1]]
                confidence = 0.65
            else:
                return [], "", 0.0

        return premises, conclusion, confidence

    def _build_smt_regex(self, premises: list[str], conclusion: str) -> tuple[str, float]:
        """Build SMT-LIBv2 script using robust propositional mapping."""
        lines = ["; LogiScan formal validity check (Propositional Regex)", "(set-logic QF_UF)", ""]

        # Track mappings: clean_text -> var_name
        mapping = {}

        # Add all markers to stop words for variable extraction
        all_markers = set(self.CONCLUSION_MARKERS) | set(self.IMPLICATION_MARKERS)

        def get_var(txt):
            # Normalize and extract first significant noun/verb
            original_txt = txt
            txt = txt.lower()
            # Remove markers from the text itself
            for m in all_markers:
                txt = txt.replace(m, "")

            # Ignore negation for variable identity
            search_txt = (
                txt.replace("isn't", "")
                .replace("not", "")
                .replace("no ", "")
                .replace("don't", "")
                .replace("doesn't", "")
            )
            words = re.findall(r"[a-z]{3,}", search_txt)
            stops = {
                "the",
                "and",
                "that",
                "this",
                "with",
                "from",
                "they",
                "then",
                "will",
                "what",
                "when",
                "were",
                "are",
                "was",
                "has",
                "had",
                "all",
                "does",
                "did",
                "you",
                "your",
                "must",
                "been",
                "have",
            }

            stems = []
            for w in words:
                if w in stops or w in all_markers:
                    continue
                # Moderate suffix stripping
                for suffix in ["ing", "ed", "es", "s"]:
                    if w.endswith(suffix) and len(w) > 4:
                        w = w[: -len(suffix)]
                        break
                stems.append(w)

            # Use top 2 stems for more specific unification
            clean = "_".join(stems[:2]) if stems else "prop"
            logger.debug(f"get_var: '{original_txt}' -> '{clean}' (stems={stems})")

            if clean not in mapping:
                mapping[clean] = f"v_{clean}"
            return mapping[clean]

        assertions = []
        for premise in premises:
            p_low = premise.lower()
            is_negated = any(n in p_low for n in ["not", "isn't", "no ", "don't", "doesn't"])

            # Check for implication markers
            imp_found = False
            for marker in self.IMPLICATION_MARKERS:
                if marker in p_low:
                    # Specific handling for "if ... then" or "if ... ,"
                    if marker in ["if", "when", "whenever"]:
                        # Extract antecedent and consequent
                        content = p_low.replace(marker, "", 1).strip()
                        parts = re.split(r"then|,|so", content, maxsplit=1)
                        if len(parts) == 2:
                            ant = get_var(parts[0])
                            cons = get_var(parts[1])
                            assertions.append(f"(=> {ant} {cons})")
                            imp_found = True
                            break
                    elif marker in ["leads to", "results in", "implies", "causes", "means that"]:
                        parts = p_low.split(marker, 1)
                        if len(parts) == 2:
                            ant = get_var(parts[0])
                            cons = get_var(parts[1])
                            assertions.append(f"(=> {ant} {cons})")
                            imp_found = True
                            break

            if not imp_found:
                var = get_var(premise)
                assertions.append(f"(not {var})" if is_negated else var)

        # Handle Conclusion
        c_low = conclusion.lower()
        is_concl_negated = any(n in c_low for n in ["not", "isn't", "no ", "don't", "doesn't"])
        concl_base_var = get_var(conclusion)
        concl_expr = f"(not {concl_base_var})" if is_concl_negated else concl_base_var

        # Declarations (Must include all used variables)
        used_vars = set()
        for ass in assertions:
            matches = re.findall(r"v_[a-z_]+", ass)
            used_vars.update(matches)
        used_vars.add(concl_base_var)

        for var_name in sorted(list(used_vars)):
            lines.append(f"(declare-const {var_name} Bool)")

        lines.append("")
        for ass in assertions:
            lines.append(f"(assert {ass})")

        lines.append("")
        lines.append("; Contradiction test: can premises be true while conclusion is false?")
        lines.append(f"(assert (not {concl_expr}))")
        lines.append("")
        lines.append("(check-sat)")

        script = "\n".join(lines)
        return script, 0.60

    def _run_z3(self, smt_script: str) -> tuple[str, str | None, str | None]:
        """Execute Z3 solver."""
        if not self._solver_path:
            return "unknown", None, "Z3 not installed"

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".smt2", delete=False) as tmp:
                tmp.write(smt_script)
                tmp_path = tmp.name

            result = subprocess.run(
                [self._solver_path, tmp_path],
                capture_output=True,
                text=True,
                timeout=settings.Z3_TIMEOUT_MS / 1000.0,
            )

            stdout = result.stdout.strip()

            if result.returncode != 0:
                return "error", None, result.stderr.strip()

            first_line = stdout.split("\n")[0].strip()
            if first_line == "unsat":
                return "unsat", None, None
            elif first_line == "sat":
                return "sat", stdout, None
            else:
                return "unknown", stdout, None

        except subprocess.TimeoutExpired:
            return "timeout", None, "Timeout"
        except Exception as e:
            return "error", None, str(e)
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def analyze(self, text: str) -> Z3Result:
        """
        Analyze argument formal validity using LLM-assisted SMT translation.
        Falls back to regex-based parsing if LLM fails.
        """
        start_time = time.perf_counter()

        # 1. Attempt LLM translation
        smt_script, confidence = await llm_to_smt(text)

        # 2. Fallback to Regex if LLM failed or low confidence
        if not smt_script or confidence < 0.5:
            logger.debug("LLM translation failed or low confidence. Falling back to regex.")
            premises, conclusion, extraction_conf = self._extract_logical_structure_regex(text)
            if extraction_conf >= settings.Z3_PARSING_CONFIDENCE_THRESHOLD:
                smt_script, build_conf = self._build_smt_regex(premises, conclusion)
                confidence = min(extraction_conf, build_conf)
            else:
                return Z3Result(
                    status="unknown",
                    parsing_confidence=extraction_conf,
                    error_message="Both LLM and Regex parsing failed",
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                )

        # 3. Run Z3 Solver
        status, model, error = self._run_z3(smt_script)

        # If LLM returned valid syntax but Z3 errored, try regex fallback
        if status == "error" and "error" in (error or "").lower() and confidence > 0.8:
            logger.warning(f"Z3 error on LLM script: {error}. Trying regex fallback.")
            premises, conclusion, extraction_conf = self._extract_logical_structure_regex(text)
            smt_script, confidence = self._build_smt_regex(premises, conclusion)
            status, model, error = self._run_z3(smt_script)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"Z3 Analysis complete: status={status}, confidence={confidence:.2f}")

        metrics.observe_latency("z3_service", latency_ms / 1000.0)

        return Z3Result(
            status=status,
            parsing_confidence=confidence,
            smt_script=smt_script,
            model=model,
            error_message=error,
            latency_ms=latency_ms,
        )


z3_service = Z3Service()
