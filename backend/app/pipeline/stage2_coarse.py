"""
Stage 2: Coarse Fallacy Classification (4-class)
Primary: Our trained model from models/stage2_coarse_classifier
Fallback: q3fer 14-class model
"""

import logging

logger = logging.getLogger(__name__)

from backend.app.services.unified_classifier import unified_classifier


class CoarseClassifier:
    def __init__(self):
        logger.info("CoarseClassifier (Unified) created.")

    async def predict(self, text: str, skip_cache: bool = False) -> tuple[str, float, float]:
        return await unified_classifier.predict_coarse(text, skip_cache=skip_cache)


coarse_classifier = CoarseClassifier()
