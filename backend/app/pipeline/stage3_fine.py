"""
Stage 3: Fine-Grained Fallacy Classification (25-class)
Primary: Fine-tuned RoBERTa 25-class model
Fallback: q3fer 14-class model
Emergency: Heuristic pattern matching
"""

import logging

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {
    "affirming_consequent": 0.9,
    "denying_antecedent": 0.9,
    "undistributed_middle": 0.85,
    "illicit_major": 0.85,
    "illicit_minor": 0.85,
    "exclusive_premises": 0.9,
    "existential_fallacy": 0.9,
    "false_dilemma": 0.8,
    "ad_hominem": 0.7,
    "straw_man": 0.8,
    "appeal_to_emotion": 0.5,
    "appeal_to_authority": 0.6,
    "appeal_to_nature": 0.5,
    "tu_quoque": 0.65,
    "red_herring": 0.55,
    "genetic_fallacy": 0.6,
    "equivocation": 0.75,
    "amphiboly": 0.7,
    "composition": 0.65,
    "division": 0.65,
    "accent": 0.6,
    "begging_the_question": 0.95,
    "complex_question": 0.7,
    "false_cause": 0.8,
    "slippery_slope": 0.6,
}

from backend.app.services.unified_classifier import unified_classifier


class FineClassifier:
    def __init__(self):
        logger.info("FineClassifier (Unified) created.")

    async def predict(
        self, text: str, include_explanations: bool = False, skip_cache: bool = False
    ) -> tuple[list[str], list[float], list[str], list[float], list[dict], bool, float]:
        return await unified_classifier.predict_fine(
            text, include_explanations=include_explanations, skip_cache=skip_cache
        )

    async def predict_multi(
        self, text: str, include_explanations: bool = False, skip_cache: bool = False
    ) -> dict:
        """Multi-sentence fallacy detection passthrough."""
        return await unified_classifier.predict_fine_multi(
            text, include_explanations=include_explanations, skip_cache=skip_cache
        )

    @staticmethod
    def calculate_logic_score(labels, scores, top_k=3):
        """
        Calculates a logic health score (1.0 = clean, 0.0 = fallacious).
        Uses a weighted penalty system with a 0.35 cap per fallacy to prevent
        a single detection from zeroing out the entire score.
        """
        if not labels or not scores:
            return 1.0

        total_penalty = 0.0
        # Penalize up to top_k fallacies
        for label, score in zip(labels[:top_k], scores[:top_k]):
            if label == "factual_statement" or label == "valid_reasoning":
                continue

            severity = SEVERITY_WEIGHTS.get(label, 0.5)
            # Increased multiplier from 0.4 to 1.0 and removed the 0.35 cap
            # to allow a single clear fallacy to drive the score significantly lower.
            penalty = (score**0.5) * severity * 1.0
            total_penalty += penalty

        return max(0.0, min(1.0, 1.0 - total_penalty))

    @property
    def fallacy_labels(self):
        return list(SEVERITY_WEIGHTS.keys())


fine_classifier = FineClassifier()
