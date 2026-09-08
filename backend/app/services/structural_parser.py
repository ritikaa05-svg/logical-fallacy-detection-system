import logging
import re
import time
from typing import Any

from backend.app.config import settings
from backend.app.schemas.inference import ArgumentIntelligenceResult
from backend.app.services.llm_service import llm_synthesis_service

logger = logging.getLogger(__name__)

PREMISE_MARKERS = [
    "since",
    "because",
    "for",
    "as",
    "given that",
    "assuming that",
    "seeing as",
    "inasmuch as",
    "owing to",
    "due to the fact that",
]

CONCLUSION_MARKERS = [
    "therefore",
    "hence",
    "thus",
    "so",
    "consequently",
    "it follows that",
    "as a result",
    "accordingly",
    "which means that",
    "ergo",
    "then",
]


class StructuralParserService:
    """
    Phase 5: Argument Intelligence - Structural Parser.
    Extracts premises, conclusions, and determines reasoning types.
    Uses a chain of regex strategies; LLM is used only as a last resort
    when a local model is explicitly configured (STAGE4_IS_LOCAL_PATH=True).
    """

    PREMISE_MARKERS = PREMISE_MARKERS
    CONCLUSION_MARKERS = CONCLUSION_MARKERS

    async def parse_argument(
        self, text: str, is_logical_claim: bool, use_llm: bool = True
    ) -> ArgumentIntelligenceResult:
        """
        Extracts structural components of an argument.
        Uses enhanced regex strategies; LLM only if STAGE4_IS_LOCAL_PATH=True and conf <= 0.8.
        """
        start_time = time.perf_counter()

        if not is_logical_claim:
            return ArgumentIntelligenceResult(
                status="skipped", is_argument=False, latency_ms=(time.perf_counter() - start_time) * 1000
            )

        premises, conclusion, conf = self._extract_regex(text)

        # Return early if LLM is disabled, settings forbid it, or regex is confident enough
        if not use_llm or not settings.STAGE4_IS_LOCAL_PATH or conf > 0.8:
            return ArgumentIntelligenceResult(
                status="success_regex",
                is_argument=bool(premises and conclusion),
                premises=premises,
                conclusion=conclusion,
                reasoning_type=self._infer_reasoning_type(text, premises, conclusion),
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

        prompt = (
            f'Text: "{text}"\n'
            "Extract: Argument (Yes/No), Premises (sep by ;), Conclusion.\n"
            "Format: Arg: [Y/N] | Pre: [P1;P2] | Con: [C]\n"
            "Analysis:"
        )

        try:
            response = await llm_synthesis_service._generate_with_fallback(
                prompt, max_new_tokens=60, temperature=0.1, do_sample=False
            )
            parsed = self._parse_llm_response(response)
            is_argument = bool(parsed.get("is_argument", False) and parsed.get("premises") and parsed.get("conclusion"))

            return ArgumentIntelligenceResult(
                status="success_llm",
                is_argument=is_argument,
                premises=parsed.get("premises", []) if is_argument else [],
                conclusion=parsed.get("conclusion", "") if is_argument else "",
                reasoning_type=parsed.get("reasoning_type", "inductive"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return ArgumentIntelligenceResult(
                status="failed", is_argument=False, latency_ms=(time.perf_counter() - start_time) * 1000
            )

    # ------------------------------------------------------------------
    # Sentence splitter
    # ------------------------------------------------------------------

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences, handling common edge cases."""
        combined = re.compile(r"(?<=[.!?])(?:\s+(?=[A-Z])|(?=[A-Z][a-z]))")
        indices = [0] + [m.end() for m in combined.finditer(text)] + [len(text)]
        sentences = []
        for i in range(len(indices) - 1):
            sent = text[indices[i] : indices[i + 1]].strip()
            if len(sent) > 3:
                sentences.append(sent)
        return sentences

    # ------------------------------------------------------------------
    # Regex strategy A — Marker Pair  (confidence 0.90)
    # ------------------------------------------------------------------

    def _extract_marker_pair(self, text: str) -> tuple[list[str], str, float]:
        """Extract using premise + conclusion marker pairs in the same sentence."""
        sentences = self._split_sentences(text)
        for sent in sentences:
            sent_lower = sent.lower()

            premise_marker = None
            for marker in self.PREMISE_MARKERS:
                if (
                    sent_lower.startswith(marker)
                    or f" {marker} " in sent_lower
                    or f", {marker} " in sent_lower
                    or sent_lower.endswith(f" {marker}")
                ):
                    premise_marker = marker
                    break

            concl_marker = None
            for marker in self.CONCLUSION_MARKERS:
                if f" {marker} " in sent_lower or f", {marker} " in sent_lower or sent_lower.endswith(f" {marker}"):
                    concl_marker = marker
                    break

            if premise_marker and concl_marker:
                after_premise = re.split(rf"\b{re.escape(premise_marker)}\b", sent, flags=re.IGNORECASE, maxsplit=1)[-1]
                parts = re.split(rf"\b{re.escape(concl_marker)}\b", after_premise, flags=re.IGNORECASE, maxsplit=1)
                if len(parts) == 2:
                    premises = [parts[0].strip().rstrip(",")]
                    conclusion = parts[1].strip()
                    return premises, conclusion, 0.90

        return [], "", 0.0

    # ------------------------------------------------------------------
    # Regex strategy B — Conclusion Marker Only  (confidence 0.85)
    # ------------------------------------------------------------------

    def _extract_conclusion_marker(self, text: str) -> tuple[list[str], str, float]:
        """Split on conclusion markers — last segment is conclusion, rest are premises."""
        text_clean = text.replace("\n", " ")
        for marker in self.CONCLUSION_MARKERS:
            pattern = rf"\b{re.escape(marker)}\b"
            parts = re.split(pattern, text_clean, flags=re.IGNORECASE)
            if len(parts) >= 2:
                conclusion = parts[-1].strip()
                premises_text = " ".join(parts[:-1]).strip()
                premises = [p.strip() for p in re.split(r"[.!?]", premises_text) if len(p.strip()) > 10]
                if premises:
                    return premises, conclusion, 0.85
        return [], "", 0.0

    # ------------------------------------------------------------------
    # Regex strategy C — Question-Answer  (confidence 0.75)
    # ------------------------------------------------------------------

    def _extract_question_answer(self, text: str) -> tuple[list[str], str, float]:
        """Detect question sentences followed by premise-marker answer."""
        sentences = self._split_sentences(text)
        conclusion = ""
        premises = []
        for i, sent in enumerate(sentences):
            if sent.strip().endswith("?"):
                conclusion = sent.strip()
                # Look at subsequent sentences for premise markers
                for j in range(i + 1, len(sentences)):
                    following = sentences[j].strip()
                    following_lower = following.lower()
                    for marker in self.PREMISE_MARKERS:
                        if re.search(rf"\b{re.escape(marker)}\b", following_lower):
                            premises.append(following)
                            break
                if premises:
                    return premises, conclusion, 0.75
        return [], "", 0.0

    # ------------------------------------------------------------------
    # Regex strategy D — Last Sentence Fallback  (confidence 0.60)
    # ------------------------------------------------------------------

    def _extract_last_sentence(self, text: str) -> tuple[list[str], str, float]:
        """If >= 3 sentences, treat the last as conclusion, preceding as premises."""
        sentences = self._split_sentences(text)
        if len(sentences) >= 3:
            conclusion = sentences[-1].strip()
            premises = [s.strip() for s in sentences[:-1] if len(s.strip()) > 5]
            return premises, conclusion, 0.60
        return [], "", 0.0

    # ------------------------------------------------------------------
    # Strategy chain
    # ------------------------------------------------------------------

    def _extract_regex(self, text: str) -> tuple[list[str], str, float]:
        """Chain regex strategies in order of confidence, return first match."""
        strategies = [
            ("marker_pair", self._extract_marker_pair),
            ("conclusion_marker", self._extract_conclusion_marker),
            ("question_answer", self._extract_question_answer),
            ("last_sentence", self._extract_last_sentence),
        ]
        for name, strategy in strategies:
            premises, conclusion, conf = strategy(text)
            if premises and conclusion:
                logger.debug(f"Regex strategy '{name}' succeeded (conf={conf})")
                return premises, conclusion, conf
        return [], "", 0.0

    # ------------------------------------------------------------------
    # Reasoning type inference
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_reasoning_type(text: str, premises: list[str], conclusion: str) -> str:
        if any(m in text.lower() for m in ["if", "then", "therefore", "must", "necessarily"]):
            return "deductive"
        if any(m in text.lower() for m in ["probably", "likely", "suggests", "indicates"]):
            return "inductive"
        if conclusion.endswith("?") or any(p.endswith("?") for p in premises):
            return "abductive"
        return "deductive" if premises and conclusion else "unknown"

    # ------------------------------------------------------------------
    # LLM response parser
    # ------------------------------------------------------------------

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Minimal regex parser for the compact LLM prompt."""
        res = {"is_argument": False, "premises": [], "conclusion": ""}
        if "arg: y" in response.lower():
            res["is_argument"] = True

        p_match = re.search(r"pre:\s*\[?(.*?)\]?(?:\s*\||$)", response, re.IGNORECASE)
        if p_match:
            res["premises"] = [p.strip() for p in p_match.group(1).split(";") if p.strip()]

        c_match = re.search(r"con:\s*\[?(.*?)\]?(?:\s*\||$)", response, re.IGNORECASE)
        if c_match:
            res["conclusion"] = c_match.group(1).strip()

        return res


structural_parser = StructuralParserService()
