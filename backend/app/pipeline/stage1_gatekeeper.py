"""
Stage 1: Gatekeeper - Logical Claim Detection
Uses fine-tuned model from models/stage1_gatekeeper/
Falls back to heuristic if model not found.
"""

import logging
import math
import re
import time
from pathlib import Path

import onnxruntime as ort
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from backend.app.config import settings
from backend.app.core.lifecycle import lifecycle_manager

logger = logging.getLogger(__name__)


class GatekeeperService:
    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._ort_session = None
        self._use_onnx = False
        self._use_ml = False
        self._max_length = 256
        logger.info("GatekeeperService created.")

    def _load(self) -> "GatekeeperService":
        model_path = Path(settings.STAGE1_MODEL_PATH)

        # 1. Try ONNX (Priority for performance)
        onnx_path = model_path / "model.onnx"
        if onnx_path.exists():
            try:
                logger.info(f"Loading ONNX gatekeeper from {onnx_path}...")
                self._tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
                self._ort_session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
                self._use_onnx = True
                self._use_ml = True
                logger.info("✅ ONNX Gatekeeper ready on CPU.")
                return self
            except Exception as e:
                logger.error(f"Failed to load ONNX gatekeeper: {e}")
                self._use_onnx = False

        # 2. Fallback to PyTorch
        if model_path.exists() and (model_path / "config.json").exists():
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
                self._model = AutoModelForSequenceClassification.from_pretrained(str(model_path), local_files_only=True)
                self._model.eval()
                self._use_ml = True
                logger.info(f"✅ Loaded trained gatekeeper from {model_path}")
                return self
            except Exception as e:
                logger.warning(f"Failed to load trained model: {e}")

        # Fallback: load base model for heuristic mode tokenizer
        self._tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        self._use_ml = False
        logger.warning("Using heuristic fallback for gatekeeper.")
        return self

    def _ml_predict(self, text: str) -> tuple[bool, float]:
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            max_length=self._max_length,
            truncation=True,
            padding=True,
        )

        if self._use_onnx:
            onnx_inputs = {"input_ids": inputs["input_ids"].numpy(), "attention_mask": inputs["attention_mask"].numpy()}
            ort_outs = self._ort_session.run(None, onnx_inputs)
            logits = torch.from_numpy(ort_outs[0])
        else:
            from backend.app.core.device_manager import device_manager

            if hasattr(self._model, "device") and self._model.device.type == "cuda":
                if not device_manager.cuda_healthy():
                    device_manager.reset_cuda()
                    if not device_manager.cuda_healthy():
                        logger.warning("CUDA unrecoverable. Moving gatekeeper model to CPU.")
                        self._model = self._model.to("cpu")
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            with torch.no_grad():
                logits = self._model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)[0]
        salience = float(probs[1])  # Probability of "argument" class

        return salience >= settings.SALIENCE_THRESHOLD, salience

    def _heuristic_predict(self, text: str) -> tuple[bool, float]:
        text_lower = text.lower()

        # 1. Structural Logic Markers (Stronger evidence)
        structural_markers = [
            "therefore",
            "thus",
            "hence",
            "consequently",
            "it follows that",
            "implies",
            "leads to",
        ]

        # 2. Conditional/Premise Markers (Moderate evidence)
        premise_markers = [
            "if",
            "because",
            "since",
            "given that",
            "all",
            "every",
            "none",
            "either",
            "or",
        ]

        # 3. Soft Intent Markers (Weak evidence)
        intent_markers = [
            "must be",
            "should",
            "shouldn't",
            "listen to",
            "believe",
        ]

        # 4. Anti-Indicators (Description/Technical)
        description_markers = [
            "uses",
            "includes",
            "features",
            "available",
            "managed",
            "consists",
            "click",
            "running",
            "exports",
            "version",
            "documentation",
            "installation",
            "process",
            "pipeline",
            "frontend",
            "backend",
            "software",
            "architecture",
            "detect",
            "tool",
            "engine",
            "system",
            "application",
        ]

        score: float = 0.0

        # Structural matches are high weight
        for m in structural_markers:
            if re.search(rf"\b{m}\b", text_lower):
                score += 2.5

        # Premise matches are moderate
        for m in premise_markers:
            if re.search(rf"\b{m}\b", text_lower):
                score += 1.0

        # Intent markers are weak
        for m in intent_markers:
            if re.search(rf"\b{m}\b", text_lower):
                score += 0.5

        # Contextual persons (common in fallacies)
        person_indicators = ["she", "he", "they", "person", "opponent", "you"]
        if any(re.search(rf"\b{p}\b", text_lower) for p in person_indicators):
            score += 0.5

        # Penalize descriptions
        for m in description_markers:
            if re.search(rf"\b{m}\b", text_lower):
                score -= 1.5

        # Specific complex patterns
        if re.search(r"if\s+.+\s+(then|so|therefore)\s+", text_lower):
            score += 3

        # Length normalization
        word_count = len(text.split())
        if word_count < 5:
            score -= 2

        salience = float(1.0 / (1.0 + math.exp(-score / 2.0)))
        salience = max(0.0, min(1.0, salience))

        return salience >= settings.SALIENCE_THRESHOLD, salience

    def predict(self, text: str) -> tuple[bool, float, float]:
        start_time = time.perf_counter()
        # Use lifecycle manager to ensure model or service is ready
        svc = lifecycle_manager.get_or_load("stage1", self._load)

        if svc._use_ml:
            is_logical, salience = svc._ml_predict(text)
            method = "ML"
        else:
            is_logical, salience = svc._heuristic_predict(text)
            method = "heuristic"

        if is_logical:
            # Clear Stage 1 intermediate tensors before heavy Stage 2/3 loads
            from backend.app.core.lifecycle import DeviceMemoryCleanup

            DeviceMemoryCleanup.run()

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Stage 1: logical={is_logical}, salience={salience:.3f}, method={method}, latency={latency_ms:.1f}ms"
        )
        return is_logical, salience, latency_ms

    @staticmethod
    def is_below_threshold(score: float) -> bool:
        return score < settings.SALIENCE_THRESHOLD


gatekeeper_service = GatekeeperService()
