"""
Main Pipeline Orchestrator
Coordinates all four stages of the LogiScan inference pipeline.
Manages early exits, caching, error handling, and metric collection.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import torch

from backend.app.config import settings
from backend.app.core.device_manager import device_manager
from backend.app.core.security import generate_cache_key
from backend.app.core.telemetry import metrics
from backend.app.pipeline.stage1_gatekeeper import gatekeeper_service
from backend.app.pipeline.stage2_coarse import coarse_classifier
from backend.app.pipeline.stage3_fine import fine_classifier
from backend.app.schemas.inference import (
    ArgumentIntelligenceResult,
    FallacyAnnotation,
    FallacyDetail,
    InferenceResult,
    SpanAnnotation,
)
from backend.app.services.cache_service import cache_service
from backend.app.services.explainability import get_sentence_context, get_top_spans
from backend.app.services.fallacy_catalog import get_definition
from backend.app.services.health_tracker import health_tracker
from backend.app.services.llm_service import FALLACY_CATALOG, llm_synthesis_service
from backend.app.services.structural_parser import structural_parser
from backend.app.services.trace_store import trace_store
from backend.app.services.z3_service import Z3Result, z3_service

logger = logging.getLogger(__name__)

MAX_QUOTE_CHARS = 200
MIN_FALLACY_CONFIDENCE = 0.55
RARE_CLASSES = set(FALLACY_CATALOG.keys())

# Classes with <200 training samples require higher confidence thresholds
# to mitigate lexical shortcut bias (see docs/lexical_bias_report.md)
# Phase 6 D3: thresholds reduced for classes expanded with synthetic hard negatives.
LOW_SUPPORT_CLASSES = {
    "moving_goalposts": 0.90,  # 25 samples, 10.88% top-3 bias
    "tu_quoque_contextual": 0.90,  # 24 samples, 13.08% top-3 bias
    "no_true_scotsman": 0.90,  # 25 samples, 14.17% top-3 bias
    "composition": 0.85,  # 200 samples, 10.77% top-3 bias
    "division": 0.85,  # 200 samples, 12.44% top-3 bias
    "equivocation": 0.85,  # 100 samples, 9.44% top-3 bias
    "denying_antecedent": 0.75,  # was 0.85, reduced: expanded with 500+ synthetic samples
    "tu_quoque": 0.80,  # 100 samples, 7.89% top-3 bias
    "affirming_consequent": 0.70,  # was 0.80, reduced: close the 0.39 recall gap
    # Signature-heavy classes prone to false positives on isolated fragments
    # (e.g. "Therefore it rained." alone): require stronger evidence.
    "false_cause": 0.60,
    "appeal_to_emotion": 0.60,
    "hasty_generalization": 0.60,
}

# Semantic signatures: phrases that structurally announce each fallacy type.
# These are syntactic patterns, not topic keywords, so they fire on form, not topic.
FALLACY_SIGNATURES: dict[str, list[str]] = {
    "ad_hominem": [
        r"\byou\b.{0,30}\b(wrong|bad|idiot|liar|trust)",
        r"\bwho\s+(are|is)\s+you\b",
        r"\b(once|fired|entry-level job)\b.{0,60}\bcannot\s+be\s+trusted\b",
    ],
    "tu_quoque": [r"\byou\s+(also|too|did|do)\b", r"\bwhat\s+about\s+you\b"],
    "straw_man": [r"\bso\s+you('re|\s+are)\s+saying\b", r"\byou\s+(claim|said|think)\s+that\b"],
    "affirming_consequent": [r"\bif\b.{0,40}\bthen\b.{0,60}\btherefore\b", r"\bsince\b.{0,40}\bmust\b"],
    "denying_antecedent": [r"\bif\s+not\b", r"\bwithout\b.{0,30}\btherefore\s+not\b"],
    "false_dilemma": [r"\b(either|only)\b.{0,30}\bor\b", r"\bno\s+(other|alternative)\b"],
    "slippery_slope": [
        r"\b(next|then|soon|eventually|leads?\s+to)\b.{0,50}\b(chaos|disaster|end)\b",
        r"\bif\b.{0,50}\b(even|just)\b.{0,50}\b(run\s+out|close|collapse|lawless|disaster|ruin|bankrupt)\b",
        # "If we pass X, it will ban all ... and every citizen will eventually be forced..."
        r"\bif\b.{0,80}\bwill\b.{0,60}\b(every|all)\b.{0,50}\b(eventually|forced|ban|destroy|collapse|ruin|end|completely)\b",
    ],
    "appeal_to_ignorance": [
        r"\bno\s+one\b.{0,80}\bproven\b.{0,120}\b(which\s+means|means|therefore|so|thus)\b",
        r"\b(no\s+one|nobody|nothing)\s+has\s+ever\b.{0,100}\b(proven|proved|shown|demonstrated)\b",
    ],
    "appeal_to_authority": [
        r"\bexperts?\s+(say|agree|confirm)\b",
        r"\bscience\s+says\b",
        r"\bmust\s+be\s+true\b",
        r"\bso\s+it\s+must\s+be\b",
        r"\bexplicitly\s+stated\s+that\b",
        r"\b[a-z]+\s+(said|says|stated|claims)\b.{0,60}\b(so|therefore|thus)\b",
        r"\btrust\b.{0,20}\bjudgment\b",
        r"\baccording\s+to\b.{0,40}\b(must|cannot|certainly)\b",
    ],
    "appeal_to_emotion": [r"\b(children|families|innocent)\b.{0,40}\b(suffer|die|hurt)\b"],
    "bandwagon": [
        r"\beveryone\b.{0,30}\b(knows|does|believes)\b",
        r"\b(millions|thousands|most\s+people)\b.{0,30}\b(buying|doing|using|believ|invest)\b",
        r"\b(everyone|everybody)\b.{0,40}\b(proves|showing|which\s+proves)\b",
    ],
    "hasty_generalization": [r"\ball\b.{0,20}\bare\b", r"\balways\b.{0,20}\bnever\b"],
    "begging_the_question": [r"\bobviously\b", r"\bclearly\b.{0,30}\bbecause\b"],
    "red_herring": [r"\bwhat\s+about\b", r"\bbut\s+(look|consider)\b"],
    "no_true_scotsman": [r"\bno\s+real\b", r"\btrue\b.{0,20}\bwould\s+never\b"],
    "false_cause": [
        r"\btherefore\b.{0,30}\bcaused?\b",
        r"\bbecause\b.{0,40}\b(happened|resulted)\b",
        r"\b(after|since)\b.{0,40}\btherefore\b",
    ],
    "appeal_to_nature": [
        r"\bnatural\b",
        r"\bchemical.free\b",
        r"\b(all.natural|pure|organic)\b.{0,30}\b(better|safer|healthier)\b",
    ],
    "appeal_to_tradition": [r"\balways\s+(been|done)\b", r"\btradition(al)?\b", r"\btime.honored\b"],
    "composition": [
        r"\b(every|each)\b.{0,30}\b(so|therefore|thus)\b",
        r"\ball\b.{0,20}\bare\b.{0,30}\b(so|therefore|thus)\b",
    ],
    "division": [
        r"\b(the\s+whole|the\s+team|the\s+group|the\s+company)\b.{0,40}\b(every|each)\b",
        r"\b(is|are)\s+great\b.{0,40}\b(must\s+be|so)\b.{0,20}\b(great|excellent)\b",
    ],
    "equivocation": [
        r"\b(right|light|cold|hard|bright)\b.{0,40}\b(meaning|sense|definition)\b",
        r"\b(runs|light|cold|hard)\b.{0,30}\b(so|therefore|thus)\b",
    ],
    "moving_goalposts": [
        r"\b(that'?s?\s+not\s+enough|not\s+good\s+enough)\b",
        r"\b(but|however)\b.{0,20}\b(prove|show|demonstrate)\s+more\b",
        r"\bneed\s+a\s+different\s+(type|kind)\s+of\b",
    ],
    "tu_quoque_contextual": [
        r"\bbut\s+(you|look)\b.{0,20}\b(yourself|too|also)\b",
        r"\byou'?re?\s+one\s+to\s+talk\b",
        r"\bsays?\s+the\s+one\s+who\b",
    ],
    "exclusive_premises": [
        r"\bno\s+\w+\s+(are|is)\b.{0,80}\bno\s+\w+\s+(are|is)\b",
        r"\bnone\s+of\b.{0,60}\b(therefore|so|thus)\b",
        r"\bnot\s+(a|an|any)\b.{0,60}\bnot\s+(a|an|any)\b",
    ],
    "existential_fallacy": [
        r"\b(all|every|no)\b.{0,60}\b(some|few)\b.{0,60}\b(therefore|so|thus)\b",
        r"\b(therefore|so|thus)\b.{0,50}\bsome\b",
    ],
    "illicit_major": [
        r"\b(therefore|so|thus)\b.{0,50}\ball\s+\w+\s+(are|is)\b",
        r"\b(therefore|so|thus)\b.{0,50}\b(every|each)\s+\w+\b",
    ],
    "illicit_minor": [
        r"\b(therefore|so|thus)\b.{0,50}\bno\s+\w+\s+(are|is)\b",
        r"\b(therefore|so|thus)\b.{0,50}\bnone\s+of\s+(them|these|those)\b",
    ],
    "undistributed_middle": [
        r"\ball\s+\w+\s+(are|is)\s+\w+\b.{0,80}\ball\s+\w+\s+(are|is)\s+\w+\b",
        r"\b(since|because)\b.{0,50}\b(are|is)\b.{0,50}\b(therefore|so|thus)\b",
    ],
}


@dataclass
class Z3Context:
    status: str  # "SAT" | "UNSAT" | "UNKNOWN"
    triggered: bool  # Whether Z3 actually ran
    violations: list[str] = field(default_factory=list)  # e.g. ["P1 contradicts P3"]
    proof_sketch: str | None = None  # Short human-readable Z3 trace if available
    severity: str = "minor"  # "minor" | "moderate" | "critical"
    smt_script: str | None = None  # SMT-LIB script passed to the solver
    model: str | None = None  # Raw Z3 model output (SAT case)
    error_message: str | None = None  # Solver/translation error, if any
    parsing_confidence: float = 0.0  # LLM translation parsing confidence

    def to_prompt_fragment(self) -> str:
        if not self.triggered:
            return "Formal logic check: not applicable (informal fallacy)."

        lines = [f"Formal logic check result: {self.status}"]
        if self.status == "UNSAT":
            lines.append(
                "Meaning: the argument's premises are formally contradictory - the conclusion cannot logically follow."
            )
            if self.violations:
                lines.append("Specific contradictions: " + "; ".join(self.violations))
            lines.append(f"Severity: {self.severity.upper()} - this is a structural logical failure.")
        elif self.status == "SAT":
            lines.append(
                "Meaning: the premises are consistent, but the argument form is still invalid "
                "(the fallacy is in the inference step, not in a contradiction)."
            )
        else:
            lines.append(
                "Meaning: formal verification was inconclusive (timeout or parse error). "
                "Treat as informal analysis only."
            )
        return "\n".join(lines)


def _extract_quote_offline(
    text: str,
    fallacy: str,
    salient_tokens: list[dict],
    argument_structure: ArgumentIntelligenceResult | None = None,
    prefix_len: int = 0,
) -> tuple[str, int, int]:
    """
    Enhanced offline quote extraction (Tier 2 Discourse Segmenter).
    Returns (quote_text, start_offset, end_offset).
    Guards against returning the entire input text as one giant quote.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return text[:80], 0, min(80, len(text))

    # Guard: if there is only one sentence and it spans most of the text,
    # override to force a smaller segment.
    if len(sentences) == 1 and len(text) > MAX_QUOTE_CHARS:
        sent_text, s_start, s_end = sentences[0]
        clauses = re.split(r"([,;:\u2014\u2013-])", sent_text)
        for i in range(0, len(clauses), 2):
            clause = clauses[i].strip()
            if 10 < len(clause) < MAX_QUOTE_CHARS:
                q_start = text.find(clause, s_start)
                if q_start != -1:
                    return clause, q_start, q_start + len(clause)
        return sent_text[:MAX_QUOTE_CHARS], s_start, min(s_start + MAX_QUOTE_CHARS, s_end)

    # --- Tier 0.5: Structural Parser First ---
    if argument_structure and argument_structure.is_argument and argument_structure.confidence >= 0.7:
        conclusion = argument_structure.conclusion
        premises = argument_structure.premises
        patterns = FALLACY_SIGNATURES.get(fallacy, [])
        # Formal fallacies: return the conclusion as quote
        if fallacy in ("affirming_consequent", "denying_antecedent"):
            if conclusion and 10 < len(conclusion) < MAX_QUOTE_CHARS:
                c_start = text.find(conclusion)
                if c_start != -1:
                    return conclusion, c_start, c_start + len(conclusion)
        # For all fallacies: try conclusion first, then premises for best signature match
        best_text = ""
        best_score = 0.0
        for candidate in ([conclusion] if conclusion else []) + premises:
            cand_stripped = candidate.strip()
            if patterns:
                matches = sum(1 for p in patterns if re.search(p, cand_stripped, re.IGNORECASE))
                score = matches / len(patterns)
            else:
                score = 0.5 if len(cand_stripped) > 20 else 0.0
            if score > best_score:
                best_score = score
                best_text = cand_stripped
        if best_text and len(best_text) > 10:
            b_start = text.find(best_text)
            if b_start != -1:
                if len(best_text) > MAX_QUOTE_CHARS:
                    best_text = best_text[:MAX_QUOTE_CHARS]
                return best_text, b_start, b_start + len(best_text)

    # --- Tier 1: Saliency anchor (Fastest/Best if available) ---
    if salient_tokens:
        try:
            top = max(salient_tokens, key=lambda t: t.get("score", 0))
            # Salient tokens may be relative to analysis_text (with prefix); adjust to text offsets
            top_pos = (top.get("start", 0) + top.get("end", 0)) // 2 - prefix_len
            for sent_text, sent_start, sent_end in sentences:
                if sent_start <= top_pos < sent_end:
                    if len(sent_text) > 120:
                        clauses = re.split(r"([,;:\u2014\u2013-])", sent_text)
                        curr_sent_pos = 0
                        for i in range(0, len(clauses), 2):
                            clause = clauses[i]
                            sep = clauses[i + 1] if i + 1 < len(clauses) else ""
                            c_len = len(clause) + len(sep)
                            if curr_sent_pos <= (top_pos - sent_start) < curr_sent_pos + c_len:
                                q_text = clause.strip()
                                if len(q_text) > 10:
                                    q_start = text.find(q_text, sent_start + curr_sent_pos)
                                    if len(q_text) > MAX_QUOTE_CHARS:
                                        q_text = q_text[:MAX_QUOTE_CHARS]
                                    return q_text, q_start, q_start + len(q_text)
                            curr_sent_pos += c_len
                    if len(sent_text) > MAX_QUOTE_CHARS:
                        sent_text = sent_text[:MAX_QUOTE_CHARS]
                    return sent_text, sent_start, sent_end
        except Exception:
            pass

    # --- Tier 2: Expanded Discourse Marker Segmenter (dual-pass) ---
    patterns = FALLACY_SIGNATURES.get(fallacy, [])

    # Broader fallacies: try sentence-level first for recall
    broader = {
        "false_cause",
        "appeal_to_emotion",
        "slippery_slope",
        "appeal_to_nature",
        "appeal_to_tradition",
        "bandwagon",
        "hasty_generalization",
    }
    if fallacy in broader:
        for sent_text, s_start, s_end in sentences:
            if any(re.search(pat, sent_text, re.IGNORECASE) for pat in patterns):
                if len(sent_text) > MAX_QUOTE_CHARS:
                    sent_text = sent_text[:MAX_QUOTE_CHARS]
                return sent_text, s_start, s_end

    # All fallacies: clause-level match for precision
    # If a matched clause is short (<30 chars), prefer the full sentence.
    best_clause = ""
    best_clause_pos = (-1, -1)
    for sent_text, s_start, s_end in sentences:
        clauses = re.split(r"([,;:\u2014\u2013-])", sent_text)
        curr_sent_pos = 0
        for i in range(0, len(clauses), 2):
            clause = clauses[i]
            sep = clauses[i + 1] if i + 1 < len(clauses) else ""
            c_text = clause.strip()
            if len(c_text) > 10:
                if any(re.search(pat, c_text, re.IGNORECASE) for pat in patterns):
                    if len(c_text) < 30 and len(sent_text) > len(c_text):
                        if any(re.search(pat, sent_text, re.IGNORECASE) for pat in patterns):
                            if len(sent_text) > MAX_QUOTE_CHARS:
                                sent_text = sent_text[:MAX_QUOTE_CHARS]
                            sent_start = text.find(sent_text, s_start)
                            if sent_start != -1:
                                return sent_text, sent_start, sent_start + len(sent_text)
                    q_start = text.find(c_text, s_start + curr_sent_pos)
                    if q_start != -1:
                        if len(c_text) > MAX_QUOTE_CHARS:
                            c_text = c_text[:MAX_QUOTE_CHARS]
                        return c_text, q_start, q_start + len(c_text)
                    elif not best_clause:
                        best_clause = c_text
                        best_clause_pos = (s_start + curr_sent_pos, s_start + curr_sent_pos + len(c_text))
            curr_sent_pos += len(clause) + len(sep)

    if best_clause:
        if len(best_clause) > MAX_QUOTE_CHARS:
            best_clause = best_clause[:MAX_QUOTE_CHARS]
        return best_clause, best_clause_pos[0], best_clause_pos[1]

    # --- Tier 3: Semantic Sentence Selection (relevance scoring) ---
    def _relevance_score(s: str, fallacy_type: str) -> float:
        pats = FALLACY_SIGNATURES.get(fallacy_type, [])
        if not pats:
            return 0.5
        matches = sum(1 for p in pats if re.search(p, s, re.IGNORECASE))
        return matches / len(pats)

    def _position_bias(i: int, total: int) -> float:
        return (i + 1) / total if total > 0 else 0.0

    def _length_score(s: str) -> float:
        n = len(s)
        if 20 <= n <= 200:
            return 1.0
        if n < 20:
            return n / 20.0
        return max(0.0, 1.0 - (n - 200) / 200.0)

    scored = []
    for i, (txt, start, end) in enumerate(sentences):
        rel = _relevance_score(txt, fallacy)
        pos = _position_bias(i, len(sentences))
        leng = _length_score(txt)
        score = rel * 0.6 + pos * 0.2 + leng * 0.2
        scored.append((score, txt, start, end))

    best = max(scored, key=lambda x: x[0])
    result_text = best[1]

    # Final guard: never return the entire input text
    if result_text == text and len(text) > MAX_QUOTE_CHARS:
        result_text = result_text[:MAX_QUOTE_CHARS]
    if len(result_text) > MAX_QUOTE_CHARS:
        result_text = result_text[:MAX_QUOTE_CHARS]
    return result_text, best[2], best[3]


def _split_sentences(text: str):
    """Robust sentence splitter preserving offsets.
    Handles both '. ' and '.Uppercase' (no space) patterns.
    """
    results = []
    # Pattern 1: Punctuation followed by whitespace and uppercase (standard)
    # Pattern 2: Punctuation followed immediately by uppercase (e.g. "...refute.Demo...")
    combined = re.compile(r"(?<=[.!?])(?:\s+(?=[A-Z])|(?=[A-Z][a-z]))")

    indices = [0] + [m.end() for m in combined.finditer(text)] + [len(text)]

    for i in range(len(indices) - 1):
        start = indices[i]
        end = indices[i + 1]
        sent = text[start:end].strip()
        if len(sent) > 5:
            results.append((sent, start, end))
    return results


def _smallest_clause_containing(sentence: str, char_offset: int) -> str | None:
    """Finds the smallest comma/semicolon-delimited clause containing offset."""
    clauses = re.split(r"[,;]", sentence)
    pos = 0
    for clause in clauses:
        if pos <= char_offset <= pos + len(clause) and len(clause.strip()) > 12:
            return clause.strip()
        pos += len(clause) + 1
    return None


class OffsetMapper:
    """Handles mapping indices from analysis_text back to original user text."""

    def __init__(self, prefix_len: int):
        self.prefix_len = prefix_len

    def remap_salient(self, tokens: list[dict]) -> list[dict]:
        """Shift salient token offsets."""
        if self.prefix_len == 0:
            return tokens
        adjusted = []
        for t in tokens:
            t_dict = t if isinstance(t, dict) else t.model_dump()
            t_dict["start"] = max(0, t_dict["start"] - self.prefix_len)
            t_dict["end"] = max(0, t_dict["end"] - self.prefix_len)
            adjusted.append(t_dict)
        return adjusted

    def remap_annotations(
        self, annotations: list[FallacyAnnotation], original_text: str = ""
    ) -> list[FallacyAnnotation]:
        """Shift annotation and span offsets, updating text fields to match."""
        if self.prefix_len == 0:
            return annotations
        for f in annotations:
            f.sentence_start = max(0, f.sentence_start - self.prefix_len)
            f.sentence_end = max(0, f.sentence_end - self.prefix_len)
            for s in f.spans:
                s.start = max(0, s.start - self.prefix_len)
                s.end = max(0, s.end - self.prefix_len)
                if original_text and s.start < len(original_text):
                    s.text = original_text[s.start : s.end]
        return annotations


def _z3_severity(status: str, top_confidence: float) -> str:
    if status == "UNSAT" and top_confidence > 0.75:
        return "critical"
    if status == "UNSAT":
        return "moderate"
    return "minor"


class PipelineOrchestrator:
    """
    Central orchestrator for the 4-stage fallacy detection pipeline.

    Pipeline Flow:
    1. Stage 1 (Gatekeeper): Always runs. Determines if text contains a logical claim.
       - If salience < threshold: Return early with minimal result.
    2. Stage 2 (Coarse): Classifies into broad fallacy category.
    3. Stage 3 (Fine-Grained): Multi-label classification into 25 fallacy types.
    4. Stage 4 (Neuro-Symbolic):
       - If coarse == "Formal": Run Z3 solver for formal validity check.
       - Always: Generate human-readable correction via LLM synthesis.

    Performance Targets:
    - Cached: < 100ms
    - Uncached (CPU): < 3.0s total
    - Uncached (GPU): < 1.5s total
    """

    def __init__(self):
        self.degradation_tier: int = 0
        self._request_count: int = 0
        logger.info("PipelineOrchestrator initialized.")

    @staticmethod
    def _parse_stage3_result(
        s3_res: Any,
    ) -> tuple[list[str], list[float], list[dict], bool, float]:
        """Parse legacy 6/7-tuple Stage 3 result into its components."""
        explanations_requested = False
        s3_latency = 0.0
        salient_tokens: list[dict] = []
        fine_labels: list[str] = []
        fine_scores: list[float] = []
        if isinstance(s3_res, (list, tuple)):
            if len(s3_res) == 7:
                fine_labels, fine_scores, _, _, salient_tokens, explanations_requested, s3_latency = s3_res
            elif len(s3_res) == 6:
                fine_labels, fine_scores, _, _, salient_tokens, s3_latency = s3_res
                explanations_requested = False
            else:
                logger.warning(f"Unexpected Stage3 return shape: {len(s3_res)}. Falling back to empty results.")
        else:
            logger.warning("Stage3 returned non-iterable result. Falling back to empty results.")
        return fine_labels, fine_scores, salient_tokens, explanations_requested, s3_latency

    def _degrade(self, current_tier: int, to_tier: int, reason: str) -> int:
        if to_tier > current_tier:
            logger.warning(
                json.dumps({"event": "degradation", "from_tier": current_tier, "to_tier": to_tier, "reason": reason})
            )
            self.degradation_tier = to_tier
        return to_tier

    def _attempt_recovery(self):
        """Periodic recovery attempt — try to reset to tier 0 (GPU)."""
        try:
            if device_manager.reset_cuda():
                device_manager.set_api_fallback(False)
                self.degradation_tier = 0
                logger.debug("GPU recovery successful. Degradation reset to tier 0.")
            else:
                logger.debug("GPU recovery attempt: CUDA unavailable after reset.")
        except Exception as e:
            logger.warning(f"GPU recovery attempt failed: {e}. Staying at tier {self.degradation_tier}.")

    async def analyze(
        self,
        text: str,
        skip_cache: bool = False,
        history: list | None = None,
        include_explanations: bool = False,
        localize: bool = False,
        fast_track: bool = False,
        analysis_id: str | None = None,
    ) -> InferenceResult:
        """
        Execute the full inference pipeline.

        Args:
            text: Sanitized input text
            skip_cache: If True, bypass Redis cache
            history: Optional conversation history
            include_explanations: If True, generate saliency maps (slower)
            fast_path: If True, skip all LLM-heavy stages (structural parser LLM,
                       Stage 4 synthesis, reranker, unified breakdown). Useful for
                       fast iteration/testing.
            analysis_id: Unique ID for this analysis, used to persist its
                         symbolic trace (Phase 9.4).

        Returns:
            Complete InferenceResult with all stage outputs
        """
        pipeline_start = time.perf_counter()

        # --- Periodic Recovery Attempt ---
        self._request_count += 1
        if self._request_count % 50 == 0 and self.degradation_tier > 0:
            self._attempt_recovery()

        # --- Pre-processing: Segmentation ---
        from backend.app.pipeline.segmenter import segment_text

        segments = segment_text(text)

        if len(segments) > 1:
            logger.debug(f"Multi-segment analysis triggered: {len(segments)} segments identified.")

            results = []
            for i, seg in enumerate(segments):
                seg_is_window = seg.get("is_window", False)
                if i > 0 and "start_offset" in seg and "end_offset" in segments[i - 1]:
                    seg_is_window = seg_is_window or seg["start_offset"] < segments[i - 1]["end_offset"]
                res = await self._analyze_single_segment(
                    seg["text"],
                    skip_cache=skip_cache,
                    history=history,
                    include_explanations=include_explanations,
                    offset_shift=seg["start_offset"],
                    is_window=seg_is_window,
                    localize=localize,
                    fast_path=fast_track,
                    analysis_id=analysis_id,
                )
                results.append(res)

            return self._aggregate_with_contradictions(text, results, segments, pipeline_start, analysis_id)

        return await self._analyze_single_segment(
            text,
            skip_cache=skip_cache,
            history=history,
            include_explanations=include_explanations,
            localize=localize,
            fast_path=fast_track,
            analysis_id=analysis_id,
        )

    async def _analyze_single_segment(
        self,
        text: str,
        skip_cache: bool = False,
        history: list | None = None,
        include_explanations: bool = False,
        offset_shift: int = 0,
        is_window: bool = False,
        localize: bool = False,
        fast_path: bool = False,
        analysis_id: str | None = None,
    ) -> InferenceResult:
        """Internal runner for a single segment of text.

        Supports per-request localize override to temporarily disable API fallback
        for the duration of this segment's analysis.
        """
        pipeline_start = time.perf_counter()

        # Per-request localize override
        _original_api_fallback = None
        if localize:
            _original_api_fallback = device_manager.use_api_fallback
            device_manager.set_api_fallback(False)
            logger.debug("Localize mode: API fallback disabled for this request.")

        try:
            stage_latencies = {}
            degradation_tier = self.degradation_tier

            # Prepare context-aware text if history exists
            analysis_text = text
            prefix_len = 0
            if history:
                history_str = ""
                for turn in history:
                    role = turn.role if hasattr(turn, "role") else turn.get("role", "unknown")
                    content = turn.text if hasattr(turn, "text") else turn.get("text", "")
                    history_str += f"{role}: {content} [TURN] "
                prefix = f"{history_str}current: "
                prefix_len = len(prefix)
                analysis_text = f"{prefix}{text}"
                logger.debug(f"Using context-aware analysis text (shift={prefix_len})")

            # Map back to original text. History prefix is handled by OffsetMapper
            # (which subtracts prefix_len). Segment offset is added separately below.
            offset_mapper = OffsetMapper(prefix_len)

            # --- Cache Check ---
            # Cache key based on analysis_text to include history context
            cache_key = generate_cache_key(analysis_text)
            if not skip_cache and cache_service.is_available:
                cached_json = await cache_service.get(cache_key)
                if cached_json:
                    try:
                        result = InferenceResult.model_validate_json(cached_json)
                        result.cached = True
                        result.analysis_id = analysis_id
                        result.total_latency_ms = (time.perf_counter() - pipeline_start) * 1000
                        if analysis_id:
                            trace_store.capture(analysis_id, result)
                        logger.info(f"Cache hit: latency={result.total_latency_ms:.1f}ms")
                        return result
                    except Exception as e:
                        logger.error(f"Cache deserialization error: {e}. Running fresh inference.")

            # --- Stage 1: Gatekeeper ---
            try:
                s1_start = time.perf_counter()
                is_claim, salience, s1_latency = gatekeeper_service.predict(analysis_text)
                stage_latencies["stage1"] = s1_latency
                metrics.observe_latency("stage1", time.perf_counter() - s1_start)
                metrics.increment_throughput("stage1")
            except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                if "out of memory" in str(e).lower() or "CUDA" in str(e):
                    logger.error(f"Stage 1 CUDA error: {e}")
                    device_manager.reset_cuda()
                    degradation_tier = self._degrade(degradation_tier, 1, str(e))
                    # Retry on CPU
                    is_claim, salience, s1_latency = gatekeeper_service.predict(analysis_text)
                    stage_latencies["stage1"] = s1_latency
                else:
                    logger.error(f"Stage 1 failed: {e}")
                    return self._build_error_result(text, "Stage 1 inference failed.", pipeline_start, degradation_tier)
            except Exception as e:
                logger.error(f"Stage 1 failed: {e}")
                return self._build_error_result(text, "Stage 1 inference failed.", pipeline_start, degradation_tier)

            # --- Description Guard: High-precision regex for system documentation ---
            # Catch cases where ML models are over-confident on technical/educational text
            # Educational framing patterns: text describing fallacies, not committing them
            DESCRIPTION_PATTERNS = [
                r"LogiScan uses",
                r"neuro-symbolic pipeline",
                r"detect logical fallacies",
                r"software architecture",
                r"trained on \d+ samples",
                r"available in the docs folder",
                r"database schema consists",
                r"click the blue button",
                r"is a flaw in reasoning",
                r"^Definition:",
                r"^What is\s+",
                r"^\d+\.\s+Definition",
                r"\b(This|A|An)\s+(fallacy|logical fallacy|reasoning error)\b",
                r"^Example:",
                r"^Why it'?s a fallacy",
                r"\bis a (logical |common |formal |informal )?fallacy\b",
                r"\boccurs when\b",
                r"\b(also known as|called a)\b",
                r"^(What is|Define)\b",
            ]
            description_guard_fired = False
            if any(re.search(p, text, re.IGNORECASE) for p in DESCRIPTION_PATTERNS):
                logger.debug("Description guard triggered. Forcing non-argument status.")
                is_claim = False
                salience = 0.10
                description_guard_fired = True

            # --- Phase 5: Structural Analysis ---
            argument_structure = None
            try:
                if fast_path:
                    # Fast path: skip structural parser entirely
                    argument_structure = ArgumentIntelligenceResult(
                        status="skipped",
                        is_argument=False,
                        premises=[],
                        conclusion="",
                        reasoning_type="none",
                        latency_ms=0.0,
                    )
                else:
                    use_llm = not is_window
                    argument_structure = await structural_parser.parse_argument(
                        analysis_text, is_claim, use_llm=use_llm
                    )
                stage_latencies["structural_parser"] = argument_structure.latency_ms if argument_structure else 0.0
            except Exception as e:
                logger.error(f"Structural analysis failed: {e}")
                stage_latencies["structural_parser"] = 0.0

            # --- Description Guard Bypass ---
            if description_guard_fired:
                if argument_structure and argument_structure.is_argument:
                    argument_structure.is_argument = False
                return self._build_non_argument_result(
                    text, is_claim, salience, stage_latencies, pipeline_start, argument_structure, degradation_tier
                )

            # --- Pipeline Consistency Validation ---
            if argument_structure and argument_structure.is_argument:
                if not argument_structure.premises and not argument_structure.conclusion:
                    logger.warning(f"Inconsistent state: is_argument=True but no structure for '{text[:30]}...'")
                    # Ensure it doesn't stay True if no structure was found
                    argument_structure.is_argument = False

            # --- Argument Gate (REFACTORED) ---
            # 1. Explicit Non-Argument from Structural Parser
            #    Match any success status (success, success_regex, success_llm).
            #    ONLY bypass if Stage 1 salience isn't extremely high (uncertainty buffer).
            if (
                argument_structure
                and argument_structure.status in ("success", "success_regex", "success_llm")
                and not argument_structure.is_argument
            ):
                if salience < 0.95:
                    logger.debug(
                        f"Structural parser ({argument_structure.status}) identified non-argument. Bypassing fallacy classification."
                    )
                    return self._build_non_argument_result(
                        text, is_claim, salience, stage_latencies, pipeline_start, argument_structure, degradation_tier
                    )
                else:
                    logger.debug(
                        f"Structural parser identified non-argument, but Stage 1 salience is high ({salience:.3f}). Proceeding to classification."
                    )

            # 2. Salience Check (Secondary Filter)
            # We exit if salience is below threshold AND the parser failed or agreed.
            if gatekeeper_service.is_below_threshold(salience) and not (
                argument_structure and argument_structure.is_argument
            ):
                logger.debug(
                    f"Stage 1 threshold not met (salience={salience:.3f}) and no structural argument found. Stopping pipeline."
                )
                return self._build_non_argument_result(
                    text, is_claim, salience, stage_latencies, pipeline_start, argument_structure, degradation_tier
                )
            coarse_category = None
            coarse_confidence = 0.0
            try:
                s2_start = time.perf_counter()
                coarse_category, coarse_confidence, s2_latency = await coarse_classifier.predict(
                    analysis_text, skip_cache=skip_cache
                )
                stage_latencies["stage2"] = s2_latency
                metrics.observe_latency("stage2", time.perf_counter() - s2_start)
                metrics.increment_throughput("stage2")
            except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                if "out of memory" in str(e).lower() or "CUDA" in str(e):
                    degradation_tier = self._degrade(degradation_tier, 1, str(e))
                    device_manager.set_api_fallback(True)
                else:
                    logger.error(f"Stage 2 failed: {e}")
                stage_latencies["stage2"] = 0.0
            except Exception as e:
                logger.error(f"Stage 2 failed: {e}")
                stage_latencies["stage2"] = 0.0

            if coarse_category is None:
                coarse_category = "Unknown"
                coarse_confidence = 0.0

            # --- Production Decision Policy: Respect Non-Fallacious Category ---
            # If Stage 2 is highly confident that this is NOT a fallacy, stop.
            # UNIVERSAL ROBUSTNESS: Proceed if Stage 1 salience is very high (uncertainty buffer)
            if coarse_category == "Non-Fallacious" and coarse_confidence > 0.60:
                if salience < 0.90:
                    logger.debug(f"Stage 2 identifies as Non-Fallacious ({coarse_confidence:.2f}). Bypassing Stage 3.")
                    result = InferenceResult(
                        version=settings.APP_VERSION,
                        input_text=text,
                        is_logical_claim=is_claim,
                        salience_score=salience,
                        coarse_category="Non-Fallacious",
                        fine_labels=["factual_statement"],
                        confidence_scores=[coarse_confidence],
                        salient_tokens=[],
                        fallacies=[],
                        annotations=[],
                        z3_status=None,
                        correction_strategy="This text has been identified as non-fallacious. It is likely a factual statement or a logically valid claim.",
                        logic_score=1.0,
                        total_latency_ms=(time.perf_counter() - pipeline_start) * 1000,
                        stage_latencies=stage_latencies,
                        cached=False,
                        device_info=device_manager.device_info,
                        argument_structure=argument_structure,
                        degradation_tier=degradation_tier,
                    )
                    return result
                else:
                    logger.debug(
                        f"Stage 2 identifies as Non-Fallacious, but Stage 1 salience is high ({salience:.3f}). Proceeding to Stage 3 for verification."
                    )

            # --- Stage 3: Fine-Grained Classification ---
            s3_start = time.perf_counter()
            fine_labels: list[str] = []
            fine_scores: list[float] = []
            salient_tokens: list[dict[str, Any]] = []
            sentence_details: list[dict] = []
            explanations_requested = False
            s3_latency = 0.0

            async def _run_stage3_fallback() -> bool:
                """Legacy single-shot predict fallback (keeps predict mocks valid)."""
                nonlocal fine_labels, fine_scores, salient_tokens, explanations_requested, s3_latency
                try:
                    s3_res = await fine_classifier.predict(
                        analysis_text, include_explanations=include_explanations, skip_cache=skip_cache
                    )
                    fine_labels, fine_scores, salient_tokens, explanations_requested, s3_latency = (
                        self._parse_stage3_result(s3_res)
                    )
                    stage_latencies["stage3"] = s3_latency
                    metrics.observe_latency("stage3", time.perf_counter() - s3_start)
                    metrics.increment_throughput("stage3")
                    return True
                except Exception as e2:
                    logger.error(f"Stage 3 single-shot fallback also failed: {e2}")
                    stage_latencies["stage3"] = 0.0
                    return False

            try:
                # Multi-sentence detection: per-sentence labels merged across the text
                s3_res = await fine_classifier.predict_multi(
                    analysis_text, include_explanations=include_explanations, skip_cache=skip_cache
                )
                if isinstance(s3_res, dict):
                    fine_labels = list(s3_res.get("fine_labels", []))
                    fine_scores = [float(s) for s in s3_res.get("fine_confidences", [])]
                    salient_tokens = list(s3_res.get("salient_tokens", []))
                    sentence_details = list(s3_res.get("sentence_details", []))
                    explanations_requested = bool(s3_res.get("explanations_requested", include_explanations))
                    s3_latency = float(s3_res.get("latency_ms", 0.0))
                else:
                    # predict_multi produced legacy output (mock or unavailable): use it directly
                    s3_res = await fine_classifier.predict(
                        analysis_text, include_explanations=include_explanations, skip_cache=skip_cache
                    )
                    fine_labels, fine_scores, salient_tokens, explanations_requested, s3_latency = (
                        self._parse_stage3_result(s3_res)
                    )
                stage_latencies["stage3"] = s3_latency
                metrics.observe_latency("stage3", time.perf_counter() - s3_start)
                metrics.increment_throughput("stage3")
            except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                if "out of memory" in str(e).lower() or "CUDA" in str(e):
                    degradation_tier = self._degrade(degradation_tier, 1, str(e))
                    device_manager.set_api_fallback(True)
                    stage_latencies["stage3"] = 0.0
                else:
                    logger.error(f"Stage 3 multi-sentence detection failed: {e}. Falling back to single-shot predict.")
                    await _run_stage3_fallback()
            except Exception as e:
                logger.error(f"Stage 3 multi-sentence detection failed: {e}. Falling back to single-shot predict.")
                await _run_stage3_fallback()

            # --- Lexical Bias Mitigation: per-sentence floor + LOW_SUPPORT floors per label ---
            # Keep raw details for the signature supplement pass (below), which only
            # fires for sentences where the model found nothing (top-1 below floor).
            raw_sentence_details = list(sentence_details)
            filtered_details: list[dict] = []
            for detail in raw_sentence_details:
                label = detail.get("label")
                score = float(detail.get("score", 0.0))
                if not label:
                    continue
                min_conf = LOW_SUPPORT_CLASSES.get(label, 0.0)
                if score >= 0.35 and score >= min_conf:
                    filtered_details.append(detail)

            # --- Signature Supplement (~0.45 confidence) ---
            # Semantic signatures catch fallacies the ML model missed, merged into
            # sentence details so they surface as quotes + cards like real detections.
            # "Found nothing" = the top-1 prediction would not surface as a card:
            # below the 0.35 floor OR below its LOW_SUPPORT_CLASSES floor.
            signature_details: list[dict] = []
            for detail in raw_sentence_details:
                label = detail.get("label")
                score = float(detail.get("score", 0.0))
                min_conf = LOW_SUPPORT_CLASSES.get(label, 0.0)
                if score >= 0.35 and score >= min_conf:
                    continue
                sentence_text = detail.get("sentence", "")
                for fallacy_type, patterns in FALLACY_SIGNATURES.items():
                    if any(re.search(pat, sentence_text, re.IGNORECASE) for pat in patterns):
                        signature_details.append(
                            {
                                "sentence": sentence_text,
                                "start": detail.get("start", 0),
                                "end": detail.get("end", 0),
                                "label": fallacy_type,
                                "score": 0.45,
                            }
                        )
                        break

            sentence_details = filtered_details + signature_details

            # Merged label list: floor 0.35 + LOW_SUPPORT floors applied per label
            # (previously only the top label was demoted).
            filtered_labels: list[str] = []
            filtered_scores: list[float] = []
            for label, score in zip(fine_labels, fine_scores):
                min_conf = LOW_SUPPORT_CLASSES.get(label, 0.0)
                if score >= 0.35 and score >= min_conf:
                    filtered_labels.append(label)
                    filtered_scores.append(score)

            # Merge signature labels into the merged list (max confidence per label)
            for sig in signature_details:
                sig_label = sig["label"]
                sig_score = sig["score"]
                if sig_label in filtered_labels:
                    idx = filtered_labels.index(sig_label)
                    if sig_score > filtered_scores[idx]:
                        filtered_scores[idx] = sig_score
                else:
                    filtered_labels.append(sig_label)
                    filtered_scores.append(sig_score)

            fine_labels = filtered_labels
            fine_scores = filtered_scores

            # --- Few-Shot Reranker for Rare Classes ---
            reranked = False
            if not fast_path and fine_labels and fine_labels[0] in RARE_CLASSES and fine_scores[0] < 0.60:
                top_fallacy = fine_labels[0]
                top_conf = fine_scores[0]
                logger.debug(f"Low confidence ({top_conf:.2f}) on rare class '{top_fallacy}'. Invoking LLM reranker...")

                is_verified, explanation = await llm_synthesis_service.verify_fallacy(
                    text=text, fallacy=top_fallacy, confidence=top_conf
                )

                if not is_verified:
                    logger.debug(f"LLM Reranker rejected '{top_fallacy}'. Reason: {explanation}")
                    if len(fine_labels) > 1:
                        fine_labels = fine_labels[1:]
                        fine_scores = fine_scores[1:]
                    else:
                        fine_labels = ["Non-Fallacious"]
                        fine_scores = [1.0 - top_conf]
                    reranked = True
                else:
                    logger.debug(f"LLM Reranker verified '{top_fallacy}'.")

            logger.debug(f"Stage3 labels: {fine_labels}, Stage2: {coarse_category}")
            # --- Bi-Directional Coarse Category Override ---
            # Ensure Stage 2 (Coarse) and Stage 3 (Fine) are logically consistent
            # to prevent unnecessary heavy Stage 4 (Z3) runs on informal fallacies.
            FORMAL_FALLACIES = {
                "affirming_consequent",
                "denying_antecedent",
                "undistributed_middle",
                "fallacy of logic",
                "fallacy_of_logic",
                "formal_fallacy",
            }
            # Normalize labels for matching
            normalized = {f.replace(" ", "_") for f in fine_labels}
            is_formal_detected = any(f in FORMAL_FALLACIES for f in fine_labels) or any(
                f in FORMAL_FALLACIES for f in normalized
            )

            if is_formal_detected and coarse_category != "Formal":
                coarse_category = "Formal"
                logger.debug(f"Stage 2 overridden to 'Formal' based on Stage 3: {fine_labels}")
            elif not is_formal_detected and coarse_category == "Formal":
                # If Stage 3 top label maps to an informal category, demote Formal -> Informal
                if fine_labels:
                    from backend.app.services.unified_classifier import unified_classifier

                    mapped_coarse = unified_classifier.SHADOW_COARSE_MAP.get(fine_labels[0])
                    if mapped_coarse and mapped_coarse != "Formal":
                        coarse_category = mapped_coarse
                        logger.debug(
                            f"Stage 2 'Formal' demoted to '{coarse_category}' based on Stage 3: {fine_labels[0]}"
                        )

            # --- Stage 4: Neuro-Symbolic Layer ---
            z3_ctx = Z3Context(status="unknown", triggered=False)
            correction_strategy = None
            s4_symbolic_latency = 0.0
            s4_synthesis_latency = 0.0

            # LATENCY OPTIMIZATION: Only run heavy Stage 4 if a fallacy was detected
            if coarse_category == "Non-Fallacious":
                logger.debug("Stage 2 identifies as Non-Fallacious. Skipping heavy Stage 4 synthesis.")
                return InferenceResult(
                    version=settings.APP_VERSION,
                    input_text=text,
                    is_logical_claim=is_claim,
                    salience_score=salience,
                    coarse_category="Non-Fallacious",
                    fine_labels=["factual_statement"],
                    confidence_scores=[coarse_confidence] if coarse_confidence > 0 else [1.0],
                    salient_tokens=[],
                    fallacies=[],
                    annotations=[],
                    z3_status=None,
                    correction_strategy="No logical fallacies detected.",
                    logic_score=1.0,
                    total_latency_ms=(time.perf_counter() - pipeline_start) * 1000,
                    stage_latencies=stage_latencies,
                    cached=False,
                    device_info=device_manager.device_info,
                    argument_structure=argument_structure,
                    degradation_tier=degradation_tier,
                )

            # Symbolic branch: Only for formal arguments

            s4_sym_start = time.perf_counter()
            if coarse_category == "Formal":
                try:
                    z3_result: Z3Result = await z3_service.analyze(text)
                    z3_ctx = Z3Context(
                        status=z3_result.status,
                        triggered=True,
                        violations=getattr(z3_result, "violations", []),
                        proof_sketch=getattr(z3_result, "proof_sketch", None),
                        severity=_z3_severity(z3_result.status, fine_scores[0] if fine_scores else 0.5),
                        smt_script=getattr(z3_result, "smt_script", None),
                        model=getattr(z3_result, "model", None),
                        error_message=getattr(z3_result, "error_message", None),
                        parsing_confidence=getattr(z3_result, "parsing_confidence", 0.0),
                    )
                    s4_symbolic_latency = z3_result.latency_ms
                    stage_latencies["stage4_symbolic"] = s4_symbolic_latency
                    metrics.observe_latency("stage4_symbolic", time.perf_counter() - s4_sym_start)
                    metrics.increment_throughput("stage4_symbolic")
                except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                    if "out of memory" in str(e).lower() or "CUDA" in str(e):
                        logger.error(f"Z3 CUDA error: {e}")
                        device_manager.reset_cuda()
                        degradation_tier = self._degrade(degradation_tier, 1, str(e))
                        # Retry Z3 on CPU
                        try:
                            z3_result = await z3_service.analyze(text)
                            z3_ctx = Z3Context(
                                status=z3_result.status,
                                triggered=True,
                                violations=getattr(z3_result, "violations", []),
                                proof_sketch=getattr(z3_result, "proof_sketch", None),
                                severity=_z3_severity(z3_result.status, fine_scores[0] if fine_scores else 0.5),
                                smt_script=getattr(z3_result, "smt_script", None),
                                model=getattr(z3_result, "model", None),
                                error_message=getattr(z3_result, "error_message", None),
                                parsing_confidence=getattr(z3_result, "parsing_confidence", 0.0),
                            )
                            s4_symbolic_latency = z3_result.latency_ms
                            stage_latencies["stage4_symbolic"] = s4_symbolic_latency
                        except Exception as e2:
                            logger.error(f"Z3 analysis failed after CUDA recovery: {e2}")
                            z3_ctx = Z3Context(status="unknown", triggered=True)
                            stage_latencies["stage4_symbolic"] = 0.0
                    else:
                        logger.error(f"Z3 analysis failed: {e}")
                        z3_ctx = Z3Context(status="unknown", triggered=True)
                        stage_latencies["stage4_symbolic"] = 0.0
                except Exception as e:
                    logger.error(f"Z3 analysis failed: {e}")
                    z3_ctx = Z3Context(status="unknown", triggered=True)
                    stage_latencies["stage4_symbolic"] = 0.0
            else:
                # Explicitly mark as skipped for informal fallacies
                z3_ctx = Z3Context(status="skipped", triggered=False)
                stage_latencies["stage4_symbolic"] = 0.0

            # Synthesis branch: Always runs for explanation (skipped in fast_path)
            # Degradation ladder: Tier 0/1 (local LLM) → Tier 2 (API fallback) → Tier 3 (rule-based)
            s4_syn_start = time.perf_counter()
            if not fast_path:
                try:
                    correction_strategy, s4_synthesis_latency = await llm_synthesis_service.generate(
                        input_text=text,
                        coarse_category=coarse_category,
                        fine_labels=fine_labels,
                        z3_context=z3_ctx,
                    )
                    stage_latencies["stage4_synthesis"] = s4_synthesis_latency
                    metrics.observe_latency("stage4_synthesis", time.perf_counter() - s4_syn_start)
                    metrics.increment_throughput("stage4_synthesis")
                except Exception as e:
                    # Local LLM failed → degrade to Tier 2 (API fallback)
                    if degradation_tier < 2:
                        degradation_tier = self._degrade(degradation_tier, 2, str(e))
                    if not device_manager.use_api_fallback:
                        saved = device_manager.use_api_fallback
                        device_manager.set_api_fallback(True)
                        try:
                            correction_strategy, s4_synthesis_latency = await llm_synthesis_service.generate(
                                input_text=text,
                                coarse_category=coarse_category,
                                fine_labels=fine_labels,
                                z3_context=z3_ctx,
                            )
                            stage_latencies["stage4_synthesis"] = s4_synthesis_latency
                            metrics.observe_latency("stage4_synthesis", time.perf_counter() - s4_syn_start)
                            metrics.increment_throughput("stage4_synthesis")
                        except Exception as e2:
                            # API fallback also failed → degrade to Tier 3 (rule-based)
                            if degradation_tier < 3:
                                degradation_tier = self._degrade(degradation_tier, 3, str(e2))
                            correction_strategy = (
                                f"This argument may contain a {coarse_category or 'logical'} fallacy. "
                                "Consider reviewing the logical connection between your premises and conclusion."
                            )
                            stage_latencies["stage4_synthesis"] = 0.0
                        finally:
                            device_manager.set_api_fallback(saved)
                    else:
                        # Already on API fallback, it failed → degrade to Tier 3
                        if degradation_tier < 3:
                            degradation_tier = self._degrade(degradation_tier, 3, str(e))
                        correction_strategy = (
                            f"This argument may contain a {coarse_category or 'logical'} fallacy. "
                            "Consider reviewing the logical connection between your premises and conclusion."
                        )
                        stage_latencies["stage4_synthesis"] = 0.0
            else:
                correction_strategy = (
                    f"Fast-path analysis: detected {coarse_category or 'unknown'} category. "
                    f"Top label: {fine_labels[0] if fine_labels else 'none'}."
                )
                stage_latencies["stage4_synthesis"] = 0.0

            # --- Filter Fine Labels by Confidence ---
            # We only keep labels above the minimum noise threshold
            filtered_fine = []
            filtered_scores = []
            for lbl, score in zip(fine_labels, fine_scores):
                if score >= MIN_FALLACY_CONFIDENCE:
                    filtered_fine.append(lbl)
                    filtered_scores.append(score)

            # If everything was filtered, default to factual_statement
            if not filtered_fine:
                if argument_structure and argument_structure.is_argument:
                    # Structural parser found a real argument but no fallacy
                    # cleared the confidence floor: report it as valid reasoning.
                    filtered_fine = ["valid_reasoning"]
                    coarse_category = "Non-Fallacious"
                else:
                    filtered_fine = ["factual_statement"]
                filtered_scores = [1.0]

            # --- Calculate Logic Score ---
            logic_score = fine_classifier.calculate_logic_score(filtered_fine, filtered_scores)
            health_tracker.add_score(logic_score)

            # --- Build Obsidian-style Annotations ---
            fallacies_annotations = []

            if sentence_details:
                # Multi-sentence path: one annotation per sentence detail, using the
                # exact sentence quote + offsets (fixes highlighting to the correct
                # sentence per fallacy). Offsets are analysis_text-relative and are
                # remapped by OffsetMapper below.
                for detail in sentence_details:
                    f_type = detail.get("label")
                    f_score = float(detail.get("score", 0.0))
                    if f_type in ("factual_statement", "valid_reasoning"):
                        continue
                    sent_text = detail.get("sentence", "")
                    s_start = int(detail.get("start", 0))
                    s_end = int(detail.get("end", 0))
                    # Spans: clipped salient tokens when present, else full sentence
                    detail_spans: list[SpanAnnotation] = []
                    if salient_tokens and s_end > s_start:
                        for span in salient_tokens:
                            span_start = int(span.get("start", 0))
                            span_end = int(span.get("end", 0))
                            if s_start <= span_start and span_end <= s_end and span_start < span_end:
                                detail_spans.append(
                                    SpanAnnotation(
                                        text=analysis_text[span_start:span_end],
                                        start=span_start,
                                        end=span_end,
                                        saliency=float(span.get("score", 1.0)),
                                    )
                                )
                    if not detail_spans:
                        detail_spans = [
                            SpanAnnotation(text=sent_text, start=s_start, end=s_end, saliency=1.0)
                        ]
                    fallacies_annotations.append(
                        FallacyAnnotation(
                            type=f_type,
                            label=f_type.replace("_", " ").title(),
                            confidence=f_score,
                            definition=get_definition(f_type, "short"),
                            explanation=get_definition(f_type, "extended"),
                            sentence=sent_text,
                            sentence_start=s_start,
                            sentence_end=s_end,
                            spans=detail_spans,
                        )
                    )
            else:
                # Legacy path: loop through top 3 labels that passed the MIN_FALLACY_CONFIDENCE filter
                for i, (f_type, f_score) in enumerate(zip(filtered_fine[:3], filtered_scores[:3])):
                    if f_type in ("factual_statement", "valid_reasoning"):
                        continue

                    # 1. Primary: Use saliency data if available (only for the top fallacy for now to avoid overlapping confusion)
                    # Only trust saliency if explanations were requested or the classifier recorded that explanations were generated
                    salient_requested = include_explanations or bool(explanations_requested)
                    top_spans_data = (
                        get_top_spans(salient_tokens, threshold=0.15)
                        if (i == 0 and salient_requested and salient_tokens)
                        else []
                    )

                    if top_spans_data:
                        sentence_map: dict[tuple[int, int], dict[str, Any]] = {}
                        for span in top_spans_data:
                            # IMPORTANT: salient_tokens use indices relative to analysis_text
                            s_text, s_start, s_end = get_sentence_context(analysis_text, span["start"])
                            s_key = (s_start, s_end)
                            if s_key not in sentence_map:
                                sentence_map[s_key] = {"text": s_text, "spans": []}
                            sentence_map[s_key]["spans"].append(span)

                        for (s_start, s_end), s_data in sentence_map.items():
                            sentence_text = s_data["text"]
                            clipped_spans = []
                            for s in s_data["spans"]:
                                c_start = max(s["start"], s_start)
                                c_end = min(s["end"], s_end)
                                if c_start < c_end:
                                    clipped_spans.append(
                                        SpanAnnotation(
                                            text=analysis_text[c_start:c_end],
                                            start=c_start,
                                            end=c_end,
                                            saliency=s["saliency"],
                                        )
                                    )

                            if clipped_spans:
                                fallacies_annotations.append(
                                    FallacyAnnotation(
                                        type=f_type,
                                        label=f_type.replace("_", " ").title(),
                                        confidence=f_score,
                                        definition=get_definition(f_type, "short"),
                                        explanation=get_definition(f_type, "extended"),
                                        sentence=sentence_text,
                                        sentence_start=s_start,
                                        sentence_end=s_end,
                                        spans=clipped_spans,
                                    )
                                )

                    # 2. Fallback: Saliency-Free Highlighting (for secondary labels or CPU mode)
                    else:
                        quote, q_text_start, q_text_end = _extract_quote_offline(
                            text, f_type, salient_tokens if i == 0 else [], argument_structure, prefix_len=prefix_len
                        )
                        if q_text_start != -1:
                            # Shift forward by prefix_len (for history mapper).
                            # NOTE: offset_shift is added later in Step 2 of remapping.
                            q_start = q_text_start + prefix_len
                            q_end = q_text_end + prefix_len

                            # For fallback, we highlight the entire extracted quote as a single span
                            fallacies_annotations.append(
                                FallacyAnnotation(
                                    type=f_type,
                                    label=f_type.replace("_", " ").title(),
                                    confidence=f_score,
                                    definition=get_definition(f_type, "short"),
                                    explanation=get_definition(f_type, "extended"),
                                    sentence=quote,
                                    sentence_start=q_start,
                                    sentence_end=q_end,
                                    spans=[
                                        SpanAnnotation(
                                            text=quote,
                                            start=q_start,
                                            end=q_end,
                                            saliency=1.0,  # High contrast for fallback
                                        )
                                    ],
                                )
                            )

            # --- Remap offsets ---
            # Step 1: Handle history prefix (subtract prefix_len via OffsetMapper)
            salient_tokens = offset_mapper.remap_salient(salient_tokens)
            fallacies_annotations = offset_mapper.remap_annotations(fallacies_annotations, original_text=text)
            # Step 2: Handle segment offset (add offset_shift to map into full text)
            if offset_shift:
                for a in fallacies_annotations:
                    a.sentence_start += offset_shift
                    a.sentence_end += offset_shift
                    for s in a.spans:
                        s.start += offset_shift
                        s.end += offset_shift
                for t in salient_tokens:
                    if isinstance(t, dict):
                        t["start"] = t.get("start", 0) + offset_shift
                        t["end"] = t.get("end", 0) + offset_shift

            # --- Build Unified Fallacy Breakdown ---
            unified_fallacies = []
            try:
                # Run LLM breakdown when not in fast_path AND LLM is available AND (salient tokens exist OR API fallback is available)
                llm_available = settings.STAGE4_IS_LOCAL_PATH or device_manager.use_api_fallback
                use_llm_breakdown = (
                    not fast_path and llm_available and (salient_tokens or device_manager.use_api_fallback)
                )
                if use_llm_breakdown:
                    # Strip non-fallacious labels before LLM breakdown
                    llm_labels = [
                        (l, s)
                        for l, s in zip(filtered_fine, filtered_scores)
                        if l not in ("factual_statement", "valid_reasoning")
                    ]
                    if not llm_labels:
                        llm_labels = [("factual_statement", 1.0)]
                    unified_data = await llm_synthesis_service.generate_unified_breakdown(
                        input_text=text,
                        fine_labels=[l for l, _ in llm_labels],
                        confidence_scores=[s for _, s in llm_labels],
                        salient_tokens=salient_tokens,
                    )
                    unified_fallacies = [FallacyDetail(**d) for d in unified_data]
                else:
                    # Fast-path / offline: cards from sentence details (pure ML, no LLM).
                    # Each card quotes its own sentence and carries its confidence.
                    if sentence_details:
                        seen_cards = set()
                        for detail in sentence_details:
                            name = detail.get("label")
                            if name in ("factual_statement", "valid_reasoning") or not name:
                                continue
                            card_key = (name, detail.get("sentence", ""))
                            if card_key in seen_cards:
                                continue
                            seen_cards.add(card_key)
                            unified_fallacies.append(
                                FallacyDetail(
                                    name=name,
                                    quote=detail.get("sentence", ""),
                                    explanation=get_definition(name, "extended"),
                                    confidence=float(detail.get("score", 0.0)),
                                )
                            )
                    else:
                        # Top 3 or filtered list
                        for name, conf in zip(filtered_fine[:3], filtered_scores[:3]):
                            if name in ("factual_statement", "valid_reasoning"):
                                continue
                            quote, _, _ = _extract_quote_offline(text, name, salient_tokens or [], argument_structure)
                            unified_fallacies.append(
                                FallacyDetail(
                                    name=name,
                                    quote=quote,
                                    explanation=get_definition(name, "extended"),
                                    confidence=float(conf),
                                )
                            )
            except Exception as e:
                logger.error(f"Unified breakdown generation failed: {e}")

            # --- Build Result ---
            total_latency = (time.perf_counter() - pipeline_start) * 1000

            result = InferenceResult(
                version=settings.APP_VERSION,
                input_text=text,
                is_logical_claim=is_claim,
                salience_score=salience,
                coarse_category=coarse_category,
                fine_labels=filtered_fine,
                confidence_scores=filtered_scores,
                salient_tokens=salient_tokens,
                fallacies=unified_fallacies,
                annotations=fallacies_annotations,
                argument_structure=argument_structure,
                z3_status=z3_ctx.status,
                correction_strategy=correction_strategy,
                logic_score=logic_score,
                total_latency_ms=total_latency,
                stage_latencies=stage_latencies,
                cached=False,
                reranked=reranked,
                device_info=device_manager.device_info,
                degradation_tier=degradation_tier,
            )
            result.analysis_id = analysis_id

            # --- Persist Symbolic Trace (Phase 9.4) ---
            if analysis_id:
                trace_store.capture(analysis_id, result, z3_ctx)

            # --- Cache Result ---
            if not skip_cache:
                await cache_service.set(cache_key, result.model_dump_json())

            logger.info(
                f"Pipeline complete: logic_score={logic_score:.2f}, "
                f"total_latency={total_latency:.1f}ms, "
                f"stages={list(stage_latencies.keys())}"
            )

            return result
        finally:
            if _original_api_fallback is not None:
                device_manager.set_api_fallback(_original_api_fallback)

    def _aggregate_results(
        self, full_text: str, results: list[InferenceResult], pipeline_start: float
    ) -> InferenceResult:
        """Merge multiple InferenceResults into a single comprehensive result.
        Filters out low-confidence noise (sub-MIN_FALLACY_CONFIDENCE).
        """
        is_logical_claim = any(r.is_logical_claim for r in results)
        avg_salience = sum(r.salience_score for r in results) / len(results)

        all_fallacies = []
        all_annotations = []
        fallacy_confidences: dict[str, float] = {}
        coarse_category_seen = set()
        z3_statuses = []

        for r in results:
            if r.z3_status:
                z3_statuses.append(r.z3_status)
            for f in r.fallacies:
                name = f.get("name") if isinstance(f, dict) else getattr(f, "name", None)
                conf = f.get("confidence") if isinstance(f, dict) else getattr(f, "confidence", 0)
                if conf < MIN_FALLACY_CONFIDENCE:
                    continue
                if name:
                    existing = fallacy_confidences.get(name, 0)
                    fallacy_confidences[name] = max(existing, conf)
                all_fallacies.append(f)
            for a in r.annotations:
                if a.confidence < MIN_FALLACY_CONFIDENCE:
                    continue
                # Deduplicate overlapping annotations
                a_spans = [(s.start, s.end) for s in getattr(a, "spans", [])]
                if not a_spans:
                    # No spans — always include (e.g., sentence-level only)
                    all_annotations.append(a)
                    continue
                is_overlap = False
                for existing in all_annotations:
                    e_spans = [(s.start, s.end) for s in getattr(existing, "spans", [])]
                    for a_start, a_end in a_spans:
                        for e_start, e_end in e_spans:
                            if a_start < e_end and e_start < a_end:
                                is_overlap = True
                                break
                        if is_overlap:
                            break
                    if is_overlap:
                        break
                if not is_overlap:
                    all_annotations.append(a)

            cc = r.coarse_category
            if cc:
                coarse_category_seen.add(cc)
                if cc == "Non-Fallacious":
                    pass

        # Deduplicate fallacies list by name
        seen_fallacies = set()
        deduplicated_fallacies = []
        for f in all_fallacies:
            name = f.get("name") if isinstance(f, dict) else getattr(f, "name", None)
            if name and name not in seen_fallacies:
                seen_fallacies.add(name)
                deduplicated_fallacies.append(f)
            elif not name:
                deduplicated_fallacies.append(f)
        all_fallacies = deduplicated_fallacies

        logic_score = min(r.logic_score for r in results)

        total_latency = (time.perf_counter() - pipeline_start) * 1000
        combined_stage_latencies: dict[str, float] = {}
        for r in results:
            for stage, lat in r.stage_latencies.items():
                combined_stage_latencies[stage] = combined_stage_latencies.get(stage, 0) + lat

        if not all_fallacies:
            correction = "No logical fallacies were detected in any of the analyzed segments."
            coarse = "Non-Fallacious"
        else:
            sorted_types = sorted(fallacy_confidences.keys(), key=lambda t: fallacy_confidences[t], reverse=True)
            correction = (
                f"Analysis complete across multiple segments. "
                f"Detected {len(all_fallacies)} potential fallacies: {', '.join(sorted_types)}."
            )
            # Pick the most relevant coarse category (first one that isn't Non-Fallacious)
            coarse = "Non-Fallacious"
            for r in results:
                if r.coarse_category and r.coarse_category != "Non-Fallacious":
                    coarse = r.coarse_category
                    break

        fine_labels = (
            sorted(fallacy_confidences.keys(), key=lambda t: fallacy_confidences[t], reverse=True)
            if fallacy_confidences
            else ["factual_statement"]
        )
        confidence_scores = [fallacy_confidences[t] for t in fine_labels] if fallacy_confidences else [1.0]

        # Aggregate Z3 status: if any are unsat, it's unsat. Otherwise if any sat, it's sat.
        final_z3 = "skipped"
        if "unsat" in z3_statuses:
            final_z3 = "unsat"
        elif "sat" in z3_statuses:
            final_z3 = "sat"
        elif "unknown" in z3_statuses:
            final_z3 = "unknown"

        aggregated_argument_structure = None
        for r in results:
            if r.argument_structure is not None:
                aggregated_argument_structure = r.argument_structure
                break

        return InferenceResult(
            version=settings.APP_VERSION,
            input_text=full_text,
            is_logical_claim=is_logical_claim,
            salience_score=avg_salience,
            coarse_category=coarse,
            fine_labels=fine_labels,
            confidence_scores=confidence_scores,
            salient_tokens=[],
            fallacies=all_fallacies,
            annotations=all_annotations,
            correction_strategy=correction,
            logic_score=logic_score,
            z3_status=final_z3,
            total_latency_ms=total_latency,
            stage_latencies=combined_stage_latencies,
            cached=False,
            device_info=device_manager.device_info,
            argument_structure=aggregated_argument_structure,
            degradation_tier=self.degradation_tier,
        )

    def _aggregate_with_contradictions(
        self,
        full_text: str,
        results: list[InferenceResult],
        segments: list[dict],
        pipeline_start: float,
        analysis_id: str | None = None,
    ) -> InferenceResult:
        """
        Wrap _aggregate_results and enrich the result with cross-segment
        contradiction data from the ContradictionDetector.

        Args:
            full_text: The original full input text.
            results:   Per-segment InferenceResult list.
            segments:  Raw segment dicts from segment_text() for page number extraction.
            pipeline_start: perf_counter start time.
            analysis_id: Unique ID for this analysis, used to persist its trace.

        Returns:
            InferenceResult with cross_segment_contradictions populated.
        """
        aggregated = self._aggregate_results(full_text, results, pipeline_start)
        aggregated.analysis_id = analysis_id
        if analysis_id:
            trace_store.capture(analysis_id, aggregated)

        # Only run contradiction detection when there are at least 2 segments
        if len(results) < 2:
            return aggregated

        try:
            from backend.app.services.contradiction_detector import (
                AnalysisSegment,
                contradiction_detector,
            )

            formal_types = {
                "affirming_consequent",
                "denying_antecedent",
                "undistributed_middle",
                "illicit_major",
                "illicit_minor",
                "exclusive_premises",
                "existential_fallacy",
            }

            analysis_segments = []
            for idx, r in enumerate(results):
                premises: list[str] = []
                conclusion = ""
                if r.argument_structure:
                    premises = r.argument_structure.premises or []
                    conclusion = r.argument_structure.conclusion or ""

                has_formal = any(lbl in formal_types for lbl in r.fine_labels)
                seg_dict = segments[idx] if idx < len(segments) else {}
                # page_number is only set by document-mode analysis; text-mode
                # segments (from segment_text) have no page concept and must not
                # be labeled as pages.
                page_number = seg_dict.get("page_number")

                analysis_segments.append(
                    AnalysisSegment(
                        text=r.input_text or "",
                        page_number=page_number if isinstance(page_number, int) else None,
                        premises=premises,
                        conclusion=conclusion,
                        has_formal_fallacy=has_formal,
                        fallacy_types=r.fine_labels,
                    )
                )

            contradiction_result = contradiction_detector.detect(analysis_segments)
            aggregated = aggregated.model_copy(update={"cross_segment_contradictions": contradiction_result})
        except Exception as exc:
            logger.warning(f"Cross-segment contradiction detection failed: {exc}", exc_info=True)

        return aggregated

    def _build_non_argument_result(
        self, text, is_claim, salience, stage_latencies, pipeline_start, argument_structure, degradation_tier=0
    ) -> InferenceResult:
        """Helper to create standardized result for non-argument early exits."""
        return InferenceResult(
            version=settings.APP_VERSION,
            input_text=text,
            is_logical_claim=is_claim,
            salience_score=salience,
            coarse_category="Non-Fallacious",
            fine_labels=["factual_statement"],
            confidence_scores=[1.0],
            salient_tokens=[],
            fallacies=[],
            annotations=[],
            z3_status="skipped",
            correction_strategy="This text has been identified as a factual description or statement rather than a structured argument.",
            logic_score=1.0,
            total_latency_ms=(time.perf_counter() - pipeline_start) * 1000,
            stage_latencies=stage_latencies,
            cached=False,
            device_info=device_manager.device_info,
            argument_structure=argument_structure,
            degradation_tier=degradation_tier,
        )

    def _build_error_result(
        self, text: str, error_message: str, pipeline_start: float, degradation_tier: int = 0
    ) -> InferenceResult:
        """Build a minimal result when the pipeline encounters a fatal error."""
        total_latency = (time.perf_counter() - pipeline_start) * 1000
        return InferenceResult(
            version=settings.APP_VERSION,
            input_text=text,
            is_logical_claim=False,
            salience_score=0.0,
            coarse_category=None,
            fine_labels=[],
            confidence_scores=[],
            salient_tokens=[],
            z3_status=None,
            correction_strategy=f"An error occurred during analysis: {error_message}",
            logic_score=0.5,  # Neutral score on error
            total_latency_ms=total_latency,
            stage_latencies={"error": total_latency},
            cached=False,
            reranked=False,
            device_info=device_manager.device_info,
            degradation_tier=degradation_tier,
        )


# Global singleton
pipeline_orchestrator = PipelineOrchestrator()
