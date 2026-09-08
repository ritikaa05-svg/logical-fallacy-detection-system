"""
Cross-Segment Contradiction Detector — Phase 6, Deliverable B1.
Detects logical contradictions between document segments using lexical and Z3 strategies.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from backend.app.schemas.contradiction import ContradictionMatch, CrossSegmentContradictions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Antonym dictionary for lexical contradiction detection
# ---------------------------------------------------------------------------
ANTONYM_PAIRS: list[tuple[str, str]] = [
    ("increase", "decrease"),
    ("increase", "reduce"),
    ("increase", "decline"),
    ("increase", "fall"),
    ("improve", "worsen"),
    ("improve", "deteriorate"),
    ("support", "oppose"),
    ("support", "reject"),
    ("benefit", "harm"),
    ("benefit", "hurt"),
    ("promote", "prohibit"),
    ("promote", "ban"),
    ("effective", "ineffective"),
    ("effective", "useless"),
    ("safe", "dangerous"),
    ("safe", "unsafe"),
    ("should", "should not"),
    ("must", "must not"),
    ("always", "never"),
    ("all", "none"),
    ("true", "false"),
    ("valid", "invalid"),
    ("proven", "unproven"),
    ("proven", "disproven"),
    ("higher", "lower"),
    ("more", "less"),
    ("grow", "shrink"),
    ("expand", "contract"),
    ("gain", "lose"),
    ("success", "failure"),
    ("positive", "negative"),
    ("strong", "weak"),
    ("accept", "reject"),
    ("agree", "disagree"),
    ("confirm", "deny"),
    ("add", "remove"),
    ("enable", "disable"),
    ("allow", "prevent"),
    ("causes", "prevents"),
    ("leads to", "prevents"),
    ("creates", "destroys"),
    ("reduces", "increases"),
]

# Build a quick-lookup set of antonym pairs (lowercase, both directions)
_ANTONYM_SET: set[tuple[str, str]] = set()
for _a, _b in ANTONYM_PAIRS:
    _ANTONYM_SET.add((_a, _b))
    _ANTONYM_SET.add((_b, _a))


@dataclass
class AnalysisSegment:
    """Structured representation of a single analyzed document segment."""

    text: str
    page_number: int | None
    premises: list[str]
    conclusion: str
    has_formal_fallacy: bool
    fallacy_types: list[str] = field(default_factory=list)


def _extract_key_phrases(text: str) -> list[str]:
    """
    Extract significant noun-phrase-like chunks from text for antonym comparison.
    Uses simple whitespace tokenization — no heavy NLP dependency.
    """
    import re

    # Remove punctuation, lowercase, split
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    words = clean.split()
    # 1-gram and 2-gram phrases
    phrases = words[:]
    phrases += [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
    return phrases


def _detect_lexical_contradiction(
    text_a: str,
    text_b: str,
) -> tuple[bool, str, float]:
    """
    Check if text_a and text_b express contradicting ideas using antonym matching.

    Returns:
        (is_contradiction, description, confidence)
    """
    phrases_a = _extract_key_phrases(text_a)
    phrases_b = _extract_key_phrases(text_b)

    for pa in phrases_a:
        for pb in phrases_b:
            if (pa, pb) in _ANTONYM_SET:
                description = f"Lexical contradiction: '{pa}' appears in segment A but '{pb}' appears in segment B."
                # Higher confidence for exact multi-word antonym matches
                confidence = 0.75 if " " in pa or " " in pb else 0.65
                return True, description, confidence

    return False, "", 0.0


def _severity_from_confidence(confidence: float) -> str:
    """Map confidence to severity tier."""
    if confidence >= 0.80:
        return "critical"
    if confidence >= 0.65:
        return "moderate"
    return "minor"


class ContradictionDetector:
    """
    Service that detects logical contradictions between document segments.

    Two detection strategies:
    1. Lexical: keyword-based antonym lookup (fast, always runs).
    2. Z3: formal SMT contradiction check (runs when both segments have
       formal fallacy indicators and premises are available).
    """

    def detect(self, segments: list[AnalysisSegment]) -> CrossSegmentContradictions:
        """
        Compare every pair of segments for contradictions.

        Args:
            segments: List of AnalysisSegment built from per-segment InferenceResult.

        Returns:
            CrossSegmentContradictions with all detected matches.
        """
        t0 = time.perf_counter()
        contradictions: list[ContradictionMatch] = []
        total_pairs = 0

        for i in range(len(segments)):
            for j in range(i + 1, len(segments)):
                total_pairs += 1
                seg_a = segments[i]
                seg_b = segments[j]

                # --- Strategy 1: Lexical contradiction ---
                found, description, confidence = _detect_lexical_contradiction(seg_a.text, seg_b.text)
                if found:
                    page_a = seg_a.page_number
                    page_b = seg_b.page_number
                    if page_a and page_b:
                        description = f"Page {page_a} and Page {page_b} use contradictory language. " + description
                    contradictions.append(
                        ContradictionMatch(
                            segment_a_index=i,
                            segment_b_index=j,
                            segment_a_page=seg_a.page_number,
                            segment_b_page=seg_b.page_number,
                            type="lexical",
                            description=description,
                            severity=_severity_from_confidence(confidence),
                            confidence=confidence,
                        )
                    )
                    # Skip Z3 if lexical already found for this pair
                    continue

                # --- Strategy 2: Z3 SMT contradiction ---
                # Only attempt if both segments carry formal fallacy markers
                if seg_a.has_formal_fallacy and seg_b.has_formal_fallacy:
                    premises_a = ". ".join(seg_a.premises)
                    premises_b = ". ".join(seg_b.premises)
                    conclusion_a = seg_a.conclusion
                    conclusion_b = seg_b.conclusion
                    # Two checks: A.premises → ¬B.conclusion and B.premises → ¬A.conclusion
                    z3_contradiction = False
                    if premises_a and conclusion_b:
                        z3_contradiction = self._check_z3_contradiction(f"{premises_a} {conclusion_b}")
                    if not z3_contradiction and premises_b and conclusion_a:
                        z3_contradiction = self._check_z3_contradiction(f"{premises_b} {conclusion_a}")
                    if z3_contradiction:
                        page_a = seg_a.page_number
                        page_b = seg_b.page_number
                        page_desc = (
                            f"Page {page_a} and Page {page_b}"
                            if page_a and page_b
                            else f"Segment {i + 1} and Segment {j + 1}"
                        )
                        contradictions.append(
                            ContradictionMatch(
                                segment_a_index=i,
                                segment_b_index=j,
                                segment_a_page=seg_a.page_number,
                                segment_b_page=seg_b.page_number,
                                type="z3",
                                description=(
                                    f"Z3 formal contradiction detected between "
                                    f"{page_desc}: one segment's premises formally "
                                    "contradict the other's conclusion (unsatisfiable)."
                                ),
                                severity="critical",
                                confidence=0.90,
                            )
                        )

        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            f"Contradiction detection: {len(contradictions)} found across {total_pairs} pairs in {latency_ms:.1f}ms"
        )
        return CrossSegmentContradictions(
            contradictions=contradictions,
            total_pairs_checked=total_pairs,
            latency_ms=latency_ms,
        )

    def _check_z3_contradiction(self, text: str) -> bool:
        """
        Use the existing Z3 service to check if the combined premises are contradictory.

        Returns True if Z3 reports 'unsat' (i.e., the premises are inconsistent).
        """
        try:
            import asyncio
            import concurrent.futures

            from backend.app.services.z3_service import z3_service

            def _run_z3():
                return asyncio.run(z3_service.analyze(text))

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = loop.run_in_executor(pool, _run_z3)
                result = future.result(timeout=30)  # type: ignore[call-arg]

            return result.status == "unsat"
        except Exception as exc:
            logger.warning(f"Z3 contradiction check failed: {exc}")
            return False


# Module-level singleton
contradiction_detector = ContradictionDetector()
