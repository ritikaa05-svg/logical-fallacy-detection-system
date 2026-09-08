import asyncio
import copy
import json
import logging
import os
import threading
import time
import traceback
from collections import defaultdict
from pathlib import Path

import aiohttp
import onnxruntime as ort
import torch
import torch.nn as nn
from transformers import (
    AutoConfig,
    AutoModel,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DebertaV2Config,
    PreTrainedModel,
)

from backend.app.config import settings
from backend.app.core.device_manager import device_manager
from backend.app.core.lifecycle import lifecycle_manager
from backend.app.core.telemetry import metrics

logger = logging.getLogger(__name__)


class DebertaV3MultiHead(PreTrainedModel):
    """
    DeBERTa-v3 model with two classification heads.
    Standardized to match 'microsoft/deberta-v3-base' (12 layers).
    """

    config_class = DebertaV2Config
    base_model_prefix = "deberta"

    def __init__(self, config):
        super().__init__(config)
        self.num_labels_coarse = getattr(config, "num_labels_coarse", 4)
        self.num_labels_fine = getattr(config, "num_labels_fine", 22)

        # KEY FIX: Use standard AutoModel from_config
        # Note: If checkpoint uses 'encoder.*', we might need to wrap it
        self.deberta = AutoModel.from_config(config)

        self.pooler = nn.Linear(config.hidden_size, config.hidden_size)
        self.pooler_activation = nn.Tanh()
        self.dropout = nn.Dropout(config.hidden_dropout_prob)

        self.coarse_head = nn.Linear(config.hidden_size, self.num_labels_coarse)
        self.fine_head = nn.Linear(config.hidden_size, self.num_labels_fine)

        self.post_init()

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        labels_coarse=None,
        labels_fine=None,
        return_dict=True,
    ):
        outputs = self.deberta(input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids)

        # Use first token [CLS] for pooling
        cls_output = outputs.last_hidden_state[:, 0, :]
        pooled_output = self.pooler(cls_output)
        pooled_output = self.pooler_activation(pooled_output)
        pooled_output = self.dropout(pooled_output)

        coarse_logits = self.coarse_head(pooled_output)
        fine_logits = self.fine_head(pooled_output)

        loss = None
        if labels_coarse is not None and labels_fine is not None:
            loss_fct = nn.CrossEntropyLoss()
            loss_coarse = loss_fct(coarse_logits.view(-1, self.num_labels_coarse), labels_coarse.view(-1))
            loss_fine = loss_fct(fine_logits.view(-1, self.num_labels_fine), labels_fine.view(-1))
            loss = 0.3 * loss_coarse + 0.7 * loss_fine

        if not return_dict:
            output = (coarse_logits, fine_logits) + outputs[2:]
            return ((loss,) + output) if loss is not None else output

        return {
            "loss": loss,
            "coarse_logits": coarse_logits,
            "fine_logits": fine_logits,
            "hidden_states": outputs.hidden_states,
            "attentions": outputs.attentions,
        }


from backend.app.services.explainability import compute_attributions


class UnifiedClassifier:
    """
    Unified Classifier service with fallback to separate Stage 2 and Stage 3 models.
    Supports a mock mode for extremely low-memory environments.
    """

    # Default labels (used if config.json missing)
    DEFAULT_COARSE_LABELS = [
        "Formal",
        "Informal (Ambiguity)",
        "Informal (Other)",
        "Informal (Presumption)",
        "Informal (Relevance)",
        "Non-Fallacious",
    ]

    DEFAULT_FINE_LABELS = [
        "ad_hominem",
        "affirming_consequent",
        "appeal_to_authority",
        "appeal_to_emotion",
        "appeal_to_nature",
        "appeal_to_tradition",
        "bandwagon",
        "begging_the_question",
        "composition",
        "denying_antecedent",
        "division",
        "equivocation",
        "factual_statement",
        "false_cause",
        "false_dilemma",
        "hasty_generalization",
        "moving_goalposts",
        "no_true_scotsman",
        "red_herring",
        "slippery_slope",
        "straw_man",
        "tu_quoque",
        "tu_quoque_contextual",
        "valid_reasoning",
    ]

    def __init__(self, model_path: str | None = None):
        self.device = device_manager.get_torch_device()
        self.model = None
        self.tokenizer = None
        self.ort_session = None
        self.use_onnx = False
        self.mock_mode = False
        self.is_single_head = False

        # Instance labels
        self.coarse_labels = self.DEFAULT_COARSE_LABELS
        self.fine_labels = self.DEFAULT_FINE_LABELS

        # Fallback models and their tokenizers
        self.model_s2 = None
        self.tokenizer_s2 = None
        self.model_s3 = None
        self.tokenizer_s3 = None

        self._last_text = None
        self._last_result: dict | None = None
        # Cache key (include flags)
        self._last_key: tuple[str, bool] | None = None
        # Thread-safe cache lock
        self._cache_lock = threading.Lock()
        # Mock-mode reload cooldown
        self._last_reload_attempt: float = 0.0
        self._mock_cooldown_seconds: float = 60.0

        # Shadow Model for validation
        self.shadow_model = None
        self.shadow_tokenizer = None

        # Comparison logging path
        self.shadow_log_path = Path("docs/SHADOW_DEPLOYMENT_LOG.jsonl")

        # Check memory before loading heavy models
        try:
            import psutil

            available_gb = psutil.virtual_memory().available / (1024**3)
            # Threshold lowered to 0.5GB to prevent false Mock Mode triggers
            if available_gb < 0.5:
                logger.warning(f"Extremely low memory ({available_gb:.1f}GB). Forcing Mock Mode for stability.")
                self.mock_mode = True
                return

            if os.getenv("LOGISCAN_MOCK_MODE", "false").lower() == "true":
                logger.info("LOGISCAN_MOCK_MODE environment variable is set. Using Mock Mode.")
                self.mock_mode = True
                return

        except ImportError:
            pass

    def _load(self):
        """Internal loader for ModelLifecycleManager."""
        # Reset mock mode so a retry after a previous failure can succeed
        self.mock_mode = False

        # 1. Load Primary Unified Model (Authoritative)
        target_path = settings.STAGE2_MODEL_PATH
        if Path(target_path).exists() and (Path(target_path) / "config.json").exists():
            try:
                self.load(target_path)
                logger.info(f"Loaded Authoritative Model from {target_path}")
            except Exception as e:
                logger.error(f"Failed to load authoritative model from {target_path}: {e}")
                logger.info("Falling back to separate models...")
                self._load_fallbacks()
        else:
            self._load_fallbacks()

        # 2. Load Shadow Model (Legacy or New)
        if getattr(settings, "ENABLE_SHADOW_MODE", False) and getattr(settings, "SHADOW_MODEL_PATH", None):
            shadow_path = Path(settings.SHADOW_MODEL_PATH)
            if shadow_path.exists() and (shadow_path / "config.json").exists():
                try:
                    logger.info(f"Loading Shadow Model from {shadow_path} to CPU...")
                    self.shadow_tokenizer = AutoTokenizer.from_pretrained(str(shadow_path), local_files_only=True)
                    # Load as standard sequence classification (will at least load fine head if multi-head)
                    self.shadow_model = AutoModelForSequenceClassification.from_pretrained(
                        str(shadow_path), local_files_only=True, ignore_mismatched_sizes=True
                    ).to("cpu")
                    self.shadow_model.eval()
                    logger.info(f"✅ Shadow Model Loaded on CPU (Labels: {self.shadow_model.config.num_labels}).")
                except Exception as e:
                    logger.error(f"Failed to load shadow model: {e}")

        if not self.model and not self.model_s2 and not self.use_onnx:
            logger.error("CRITICAL: No classification models found. Using Mock Mode.")
            self.mock_mode = True

        return self

    def _load_fallbacks(self):
        """Loads separate Stage 2 and Stage 3 models as fallback (Offline Only)."""
        logger.info("Searching for fallback Stage 2 & 3 models...")

        # Load Stage 3
        for p in ["models/stage3_production_fallacy", "models/stage3_fallacy_classifier", "models/unified_classifier"]:
            path = Path(p)
            if path.exists() and (path / "config.json").exists():
                try:
                    self.tokenizer_s3 = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
                    self.model_s3 = AutoModelForSequenceClassification.from_pretrained(
                        str(path), local_files_only=True
                    ).to(self.device)
                    self.model_s3.eval()
                    logger.info(f"Loaded fallback Stage 3: {p}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load fallback Stage 3 from {p}: {e}")

        # Load Stage 2
        for p in ["models/stage2_coarse_classifier", "models/stage2_fallacy_classifier", "models/unified_classifier"]:
            path = Path(p)
            if path.exists() and (path / "config.json").exists():
                try:
                    self.tokenizer_s2 = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
                    self.model_s2 = AutoModelForSequenceClassification.from_pretrained(
                        str(path), local_files_only=True
                    ).to(self.device)
                    self.model_s2.eval()
                    logger.info(f"Loaded fallback Stage 2: {p}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load fallback Stage 2 from {p}: {e}")

    async def predict(self, text: str, include_explanations: bool = False, skip_cache: bool = False) -> dict:
        """Single entry point for predictions, handles unified, fallback, or mock.
        Added skip_cache to bypass internal in-process cache."""
        start_time = time.perf_counter()

        # THREAD-SAFE CACHE CHECK
        try:
            with self._cache_lock:
                if not skip_cache and self._last_key == (text, include_explanations) and self._last_result:
                    # Deepcopy to avoid shared mutable structures
                    res = copy.deepcopy(self._last_result)
                    res["latency_ms"] = (time.perf_counter() - start_time) * 1000
                    return res
        except Exception:
            # Defensive: if cache lock or deepcopy fails, continue with fresh inference
            pass

        # 1. Check for API Fallback (Preferred for low-memory environments)
        if device_manager.use_api_fallback and settings.HUGGINGFACE_API_TOKEN:
            try:
                result = await self._predict_via_api(text)
                if result:
                    result["latency_ms"] = (time.perf_counter() - start_time) * 1000
                    # Cache result only when allowed
                    if not skip_cache:
                        try:
                            with self._cache_lock:
                                self._last_key = (text, include_explanations)
                                self._last_result = copy.deepcopy(result)
                        except Exception:
                            pass
                    return result
            except Exception as e:
                logger.error(f"API Fallback failed: {e}. Trying local/mock...")

        # 2. Try loading and running the real model.
        # If a previous load attempt failed and we are stuck in mock mode,
        # evict the cached model so the next attempt retries fresh loading.
        if self.mock_mode:
            now = time.time()
            if now - self._last_reload_attempt < self._mock_cooldown_seconds:
                logger.debug("Mock-mode reload cooldown active. Skipping reload attempt.")
                result = self._predict_mock(text)
                result["latency_ms"] = (time.perf_counter() - start_time) * 1000
                return result
            self._last_reload_attempt = now
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lifecycle_manager.evict_model, "unified_classifier")
            self.mock_mode = False

        try:
            # Ensure models are loaded via lifecycle manager
            # Load models via lifecycle manager in threadpool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            svc = await loop.run_in_executor(None, lifecycle_manager.get_or_load, "unified_classifier", self._load)

            if svc.use_onnx:
                result = self._run_inference_onnx(svc, text)
            elif svc.model and svc.tokenizer:
                result = self._run_inference_unified(svc, text, include_explanations=include_explanations)
            elif svc.model_s2 and svc.model_s3:
                result = self._run_inference_separate(svc, text)
            else:
                result = self._predict_mock(text)
        except Exception as e:
            logger.error(f"Prediction pipeline failed: {e}")
            result = self._predict_mock(text)

        assert result is not None
        result["latency_ms"] = (time.perf_counter() - start_time) * 1000

        metrics.observe_latency("unified_classifier", result["latency_ms"] / 1000.0)

        # 3. Parallel Shadow Execution (DISABLED by default in production)
        if not self.mock_mode and getattr(settings, "ENABLE_SHADOW_MODE", False):
            try:
                svc = lifecycle_manager.get_or_load("unified_classifier", self._load)
                if svc.shadow_model:
                    shadow_result = self._run_inference_shadow(svc, text)
                    self._log_shadow_comparison(text, result, shadow_result)
            except Exception as e:
                logger.error(f"Shadow execution failed: {e}")

        # Cache final result (thread-safe) unless skip_cache requested
        if not skip_cache:
            try:
                with self._cache_lock:
                    self._last_key = (text, include_explanations)
                    self._last_result = copy.deepcopy(result)
            except Exception:
                pass
        return result

    async def _predict_via_api(self, text: str) -> dict | None:
        """Calls Hugging Face Inference API as a fallback with retries and backoff."""
        if settings.HF_MODEL_ID is None:
            logger.debug("HF_MODEL_ID is None, skipping API fallback.")
            return None

        # Use configured HF model id (this is an owner/repo style id for the HF Inference API)
        api_url = f"{settings.HUGGINGFACE_API_URL}/{settings.HF_MODEL_ID}"
        headers = (
            {"Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}"} if settings.HUGGINGFACE_API_TOKEN else {}
        )
        payload = {"inputs": text, "parameters": {"top_k": 5}}

        max_attempts = 3

        async def _attempt():
            for attempt in range(max_attempts):
                try:
                    async with aiohttp.ClientSession() as session:
                        timeout = aiohttp.ClientTimeout(total=10.0)
                        async with session.post(api_url, json=payload, headers=headers, timeout=timeout) as response:
                            if response.status == 200:
                                api_res = await response.json()
                                # Defensive format detection
                                if isinstance(api_res, dict):
                                    fine_labels = [api_res.get("label", "unknown")]
                                    fine_scores = [api_res.get("score", 0.0)]
                                elif isinstance(api_res, list):
                                    if api_res and isinstance(api_res[0], dict):
                                        first = api_res[0]
                                        if "label" in first and "score" in first:
                                            fine_labels = [item.get("label") for item in api_res]
                                            fine_scores = [item.get("score") for item in api_res]
                                        elif "entity_group" in first:
                                            fine_labels = []
                                            fine_scores = []
                                            logger.warning(
                                                "HF API returned token classification format, expected text classification"
                                            )
                                        elif "generated_text" in first:
                                            fine_labels = []
                                            fine_scores = []
                                            logger.warning(
                                                "HF API returned text generation format, expected text classification"
                                            )
                                        else:
                                            fine_labels = [
                                                item.get(list(item.keys())[0], "unknown") for item in api_res
                                            ]
                                            fine_scores = [0.0] * len(api_res)
                                    else:
                                        fine_labels = []
                                        fine_scores = []
                                else:
                                    fine_labels = []
                                    fine_scores = []

                                logger.debug(
                                    f"HF API response format: {type(api_res).__name__}, extracted {len(fine_labels)} labels"
                                )

                                if not fine_labels:
                                    logger.warning("HF API returned no usable labels, falling through to local model")
                                    return None

                                top_fine = fine_labels[0] if fine_labels else None
                                coarse = "Informal (Relevance)"  # Default
                                if top_fine in ["affirming_consequent", "denying_antecedent"]:
                                    coarse = "Formal"
                                elif top_fine in ["equivocation"]:
                                    coarse = "Informal (Ambiguity)"

                                return {
                                    "coarse_label": coarse,
                                    "coarse_confidence": fine_scores[0] if fine_scores else 0.0,
                                    "fine_labels": fine_labels,
                                    "fine_confidences": fine_scores,
                                    "salient_tokens": [],  # API doesn't return saliency
                                    "explanations_requested": False,
                                }
                            else:
                                logger.warning(f"HF API returned status {response.status} on attempt {attempt + 1}")
                except (TimeoutError, aiohttp.ClientError) as e:
                    logger.warning(f"HF API call failed on attempt {attempt + 1}: {e}")
                # Backoff before retrying
                await asyncio.sleep(2**attempt)

            logger.error("HF API fallback failed after retries")
            return None

        try:
            return await asyncio.wait_for(_attempt(), timeout=10.0)
        except TimeoutError:
            logger.error("HF API fallback timed out after 10s total.")
            return None

    def _run_inference_unified(self, svc, text: str, include_explanations: bool = False) -> dict | None:
        """Internal runner for authoritative model (supports both single and multi-head)."""
        device = next(svc.model.parameters()).device
        if device.type == "cuda":
            if not device_manager.cuda_healthy():
                device_manager.reset_cuda()
                if not device_manager.cuda_healthy():
                    logger.warning("CUDA unrecoverable. Reloading model on CPU.")
                    svc.model = svc.model.to("cpu")
                    device = torch.device("cpu")
        inputs = svc.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
        svc.model.eval()

        # 1. Single-Head Path (Phase 4 Authoritative)
        if getattr(svc, "is_single_head", False):
            with torch.no_grad():
                outputs = svc.model(**inputs)
                f_logits = outputs.logits

            f_probs = torch.softmax(f_logits, dim=-1)[0]

            # Derive coarse probabilities from fine-label distribution instead of hard one-hot
            coarse_probs: dict[str, float] = defaultdict(float)
            for fine_label, fine_prob in zip(svc.fine_labels, f_probs):
                mapped = self.SHADOW_COARSE_MAP.get(fine_label)
                if mapped and mapped != "Unknown":
                    coarse_probs[mapped] += fine_prob.item()
            c_probs = torch.zeros(len(svc.coarse_labels), device=device)
            for i, label in enumerate(svc.coarse_labels):
                if label in coarse_probs:
                    c_probs[i] = coarse_probs[label]
            if c_probs.sum() > 0:
                c_probs = c_probs / c_probs.sum()

            return self._process_logits(
                text,
                svc.model,
                svc.tokenizer,
                c_probs,
                f_probs,
                svc.coarse_labels,
                svc.fine_labels,
                include_explanations=include_explanations,
            )

        # 2. Multi-Head Path (Legacy/Fallback)
        # Ensure quantization state is moved to device for custom classes
        if hasattr(svc.model, "coarse_head"):
            svc.model.coarse_head.to(device)
            svc.model.fine_head.to(device)
            svc.model.pooler.to(device)

        with torch.no_grad():
            outputs = svc.model(**inputs)
            c_logits = outputs.get("coarse_logits")
            f_logits = outputs.get("fine_logits")

        if c_logits is None or f_logits is None:
            return self._empty_result()

        c_probs = torch.softmax(c_logits, dim=-1)[0]
        f_probs = torch.softmax(f_logits, dim=-1)[0]

        return self._process_logits(
            text,
            svc.model,
            svc.tokenizer,
            c_probs,
            f_probs,
            svc.coarse_labels,
            svc.fine_labels,
            include_explanations=include_explanations,
        )

    # Phase 4 to Coarse Category Mapping
    SHADOW_COARSE_MAP = {
        "ad_hominem": "Informal (Relevance)",
        "affirming_consequent": "Formal",
        "appeal_to_authority": "Informal (Relevance)",
        "appeal_to_emotion": "Informal (Relevance)",
        "appeal_to_nature": "Informal (Presumption)",
        "appeal_to_tradition": "Informal (Presumption)",
        "bandwagon": "Informal (Relevance)",
        "begging_the_question": "Informal (Presumption)",
        "composition": "Informal (Presumption)",
        "denying_antecedent": "Formal",
        "division": "Informal (Presumption)",
        "equivocation": "Informal (Ambiguity)",
        "exclusive_premises": "Formal",
        "existential_fallacy": "Formal",
        "factual_statement": "Non-Fallacious",
        "false_cause": "Informal (Presumption)",
        "false_dilemma": "Informal (Presumption)",
        "hasty_generalization": "Informal (Relevance)",
        "illicit_major": "Formal",
        "illicit_minor": "Formal",
        "moving_goalposts": "Informal (Relevance)",
        "no_true_scotsman": "Informal (Presumption)",
        "red_herring": "Informal (Relevance)",
        "slippery_slope": "Informal (Presumption)",
        "straw_man": "Informal (Relevance)",
        "tu_quoque": "Informal (Relevance)",
        "tu_quoque_contextual": "Informal (Relevance)",
        "undistributed_middle": "Formal",
        "valid_reasoning": "Non-Fallacious",
    }

    # Label mapping from fallback model label names to canonical LogiScan fine labels.
    # Fallback models may have 13, 14, or 20 labels with different naming conventions.
    FALLBACK_LABEL_MAP = {
        "ad hominem": "ad_hominem",
        "ad_hominem": "ad_hominem",
        "ad populum": "bandwagon",
        "appeal to emotion": "appeal_to_emotion",
        "appeal_to_emotion": "appeal_to_emotion",
        "appeal_to_authority": "appeal_to_authority",
        "appeal_to_nature": "appeal_to_nature",
        "appeal_to_tradition": "appeal_to_tradition",
        "bandwagon": "bandwagon",
        "begging_the_question": "begging_the_question",
        "circular reasoning": "begging_the_question",
        "composition": "composition",
        "denying_antecedent": "denying_antecedent",
        "division": "division",
        "equivocation": "equivocation",
        "false_cause": "false_cause",
        "false causality": "false_cause",
        "false dilemma": "false_dilemma",
        "false_dilemma": "false_dilemma",
        "faulty generalization": "hasty_generalization",
        "hasty_generalization": "hasty_generalization",
        "moving_goalposts": "moving_goalposts",
        "no_true_scotsman": "no_true_scotsman",
        "red_herring": "red_herring",
        "slippery_slope": "slippery_slope",
        "straw_man": "straw_man",
        "tu_quoque": "tu_quoque",
        "tu_quoque_contextual": "tu_quoque_contextual",
        "fallacy of logic": "formal_fallacy",
        "fallacy of credibility": "appeal_to_authority",
        "fallacy of relevance": "red_herring",
        "fallacy of extension": "slippery_slope",
        "intentional": "ad_hominem",
    }

    def _map_fallback_labels(self, raw_labels, raw_scores, canonical_labels):
        """Map fallback model labels to canonical LogiScan labels.

        Creates a score vector over canonical_labels by matching each
        fallback prediction to its canonical equivalent. Unmappable labels
        (e.g., 'miscellaneous') are discarded.
        """
        mapped = {label: 0.0 for label in canonical_labels}
        for raw_label, score in zip(raw_labels, raw_scores):
            clean = raw_label.strip().lower()
            canonical = self.FALLBACK_LABEL_MAP.get(clean)
            if canonical and canonical in mapped:
                mapped[canonical] = max(mapped[canonical], score)
        return mapped

    def _run_inference_separate(self, svc, text: str) -> dict:
        """Internal runner for separate fallback models."""
        device_s2 = svc.model_s2.device
        device_s3 = svc.model_s3.device

        # Stage 2
        inputs_s2 = svc.tokenizer_s2(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(
            device_s2
        )
        with torch.no_grad():
            out_s2 = svc.model_s2(**inputs_s2)
            c_probs = torch.softmax(out_s2.logits, dim=-1)[0]

        # Stage 3 - map fallback labels to canonical 22-label schema
        inputs_s3 = svc.tokenizer_s3(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(
            device_s3
        )
        with torch.no_grad():
            out_s3 = svc.model_s3(**inputs_s3)
            f_probs = torch.softmax(out_s3.logits, dim=-1)[0]

        # Use canonical labels, not the fallback model's label set
        c_labels = svc.coarse_labels
        f_labels = svc.fine_labels

        # Map fallback model's raw labels to canonical indices
        raw_f_labels = list(getattr(svc.model_s3.config, "id2label", {}).values())
        raw_f_scores = f_probs.tolist()
        mapped_scores = self._map_fallback_labels(raw_f_labels, raw_f_scores, f_labels)

        # Convert mapped dict back to ordered tensors matching f_labels
        mapped_probs = torch.tensor([mapped_scores[l] for l in f_labels], device=f_probs.device)

        return self._process_logits(text, svc.model_s3, svc.tokenizer_s3, c_probs, mapped_probs, c_labels, f_labels)

    def _run_inference_shadow(self, svc, text: str) -> dict:
        """Runs the shadow model with compatibility shim."""
        if not svc.shadow_model or not svc.shadow_tokenizer:
            return self._empty_result()

        start_time = time.perf_counter()
        # Explicitly use CPU for shadow model
        inputs = svc.shadow_tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(
            "cpu"
        )

        with torch.no_grad():
            logits = svc.shadow_model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]

        id2label = {int(k): v for k, v in svc.shadow_model.config.id2label.items()}

        # Shim logic: Map top-1 fine label to coarse category
        top_idx = torch.argmax(probs).item()
        top_label = id2label[top_idx]
        # Use SHADOW_COARSE_MAP for Phase 4 or fallback for legacy
        coarse_label = self.SHADOW_COARSE_MAP.get(top_label, "Informal (Other)")

        # Get top 3 for fine result
        top_vals, top_indices = torch.topk(probs, k=min(3, len(id2label)))
        fine_labels = [id2label[i.item()] for i in top_indices]
        fine_confs = [v.item() for v in top_vals]

        latency = (time.perf_counter() - start_time) * 1000

        return {
            "coarse_label": coarse_label,
            "coarse_confidence": probs[top_idx].item(),
            "fine_labels": fine_labels,
            "fine_confidences": fine_confs,
            "latency_ms": latency,
        }

    def _log_shadow_comparison(self, text, prod_res, shadow_res):
        """Log comparison between production and shadow model for analysis."""
        try:
            import json as _json  # Local import to be safe

            log_entry = {
                "timestamp": time.time(),
                "text_snippet": text[:100],
                "production": {
                    "coarse": prod_res.get("coarse_label"),
                    "fine": prod_res.get("fine_labels")[:1] if prod_res.get("fine_labels") else None,
                    "confidence": float(prod_res.get("fine_confidences")[0]) if prod_res.get("fine_confidences") else 0,
                    "latency": prod_res.get("latency_ms"),
                },
                "shadow": {
                    "coarse": shadow_res.get("coarse_label"),
                    "fine": shadow_res.get("fine_labels")[:1] if shadow_res.get("fine_labels") else None,
                    "confidence": float(shadow_res.get("fine_confidences")[0])
                    if shadow_res.get("fine_confidences")
                    else 0,
                    "latency": shadow_res.get("latency_ms"),
                },
                "agreement": prod_res.get("fine_labels")[:1] == shadow_res.get("fine_labels")[:1],
            }

            with open(self.shadow_log_path, "a") as f:
                f.write(_json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Shadow logging failed: {e}")
            logger.error(traceback.format_exc())

    def _process_logits(
        self, text, model, tokenizer, c_probs, f_probs, c_labels, f_labels, include_explanations: bool = False
    ) -> dict:
        """Unified post-processor for probabilities and saliency."""
        c_idx = torch.argmax(c_probs).item()
        f_scores, f_indices = torch.sort(f_probs, descending=True)

        target_class = f_indices[0].item()
        salient_tokens = []

        # ON-DEMAND EXPLANATIONS: Only execute if requested OR debug mode enabled
        should_explain = include_explanations or getattr(settings, "DEBUG", False)

        if should_explain and model is not None and f_probs[target_class] > 0.05:
            try:
                salient_tokens = compute_attributions(model, tokenizer, text, target_class)
            except Exception as e:
                logger.error(f"Saliency computation failed: {e}")

        return {
            "coarse_label": c_labels[c_idx] if c_idx < len(c_labels) else "Unknown",
            "coarse_confidence": c_probs[c_idx].item(),
            "fine_labels": [
                f_labels[i.item()] if i.item() < len(f_labels) else f"class_{i.item()}" for i in f_indices[:3]
            ],
            "fine_confidences": [s.item() for s in f_scores[:3]],
            "salient_tokens": salient_tokens,
            "explanations_requested": should_explain,
        }

    def _run_inference_onnx(self, svc, text: str) -> dict:
        """Internal runner for ONNX model (Phase 4)."""
        inputs = svc.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)

        onnx_inputs = {"input_ids": inputs["input_ids"].numpy(), "attention_mask": inputs["attention_mask"].numpy()}

        # Run inference
        ort_outs = svc.ort_session.run(None, onnx_inputs)
        f_logits = torch.from_numpy(ort_outs[0])
        f_probs = torch.softmax(f_logits, dim=-1)[0]

        # Derive coarse probabilities from fine-label distribution instead of hard one-hot
        coarse_probs: dict[str, float] = defaultdict(float)
        for fine_label, fine_prob in zip(svc.fine_labels, f_probs):
            mapped = self.SHADOW_COARSE_MAP.get(fine_label)
            if mapped and mapped != "Unknown":
                coarse_probs[mapped] += fine_prob.item()
        c_probs = torch.zeros(len(svc.coarse_labels))
        for i, label in enumerate(svc.coarse_labels):
            if label in coarse_probs:
                c_probs[i] = coarse_probs[label]
        if c_probs.sum() > 0:
            c_probs = c_probs / c_probs.sum()

        return self._process_logits(
            text, None, svc.tokenizer, c_probs, f_probs, svc.coarse_labels, svc.fine_labels, include_explanations=False
        )

    def _predict_mock(self, text: str) -> dict:
        """Pattern-based mock prediction with simulated saliency."""
        t_lower = text.lower()
        if "therefore" in t_lower or "if" in t_lower:
            coarse, fine = "Formal", ["affirming_consequent", "denying_antecedent"]
        elif "you" in t_lower or "trust" in t_lower:
            coarse, fine = "Informal (Relevance)", ["ad_hominem", "tu_quoque"]
        else:
            coarse, fine = "Informal (Presumption)", ["hasty_generalization", "false_cause"]

        words = text.split()
        mock_salient = []
        curr = 0
        for i, w in enumerate(words):
            if i % 3 == 0:
                mock_salient.append({"token": w, "score": 0.8 if i == 0 else 0.4, "start": curr, "end": curr + len(w)})
            curr += len(w) + 1

        return {
            "coarse_label": coarse,
            "coarse_confidence": 0.85,
            "fine_labels": fine,
            "fine_confidences": [0.8, 0.4],
            "salient_tokens": mock_salient,
        }

    def _empty_result(self) -> dict:
        return {
            "coarse_label": "Unknown",
            "coarse_confidence": 0.0,
            "fine_labels": [],
            "fine_confidences": [],
            "salient_tokens": [],
        }

    def _initialize_bnb(self, model):
        """Force initialization of bitsandbytes layers by running a dummy pass."""
        try:
            device = next(model.parameters()).device
            seq_len = getattr(model.config, "max_position_embeddings", 512)
            pad_id = getattr(model.config, "pad_token_id", 0) or 0
            dummy_input = torch.full((1, seq_len), pad_id, dtype=torch.long).to(device)
            # Add an actual token at the end to avoid all-padding issues
            dummy_input[0, -1] = getattr(model.config, "bos_token_id", 0) or 0
            with torch.no_grad():
                _ = model(dummy_input)
            logger.info("✅ Bitsandbytes layers initialized via dummy pass.")
        except Exception as e:
            logger.warning(f"BNB initialization dummy pass failed: {e}")

    def load(self, path: str):
        """Load unified model and config safely with 4-bit quantization or ONNX."""
        import gc

        from transformers import BitsAndBytesConfig

        # 0. Check for ONNX (Priority for performance/memory)
        onnx_path = Path(path) / "model.onnx"
        if onnx_path.exists():
            try:
                logger.info(f"Found ONNX model at {onnx_path}. Initializing ORT session...")
                # Use CPUExecutionProvider for maximum memory savings on 4GB hardware
                self.ort_session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
                self.use_onnx = True
                self.is_single_head = True
                self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)

                config_path = Path(path) / "config.json"
                if config_path.exists():
                    with open(config_path) as f:
                        cfg_data = json.load(f)
                    if "fine_labels" in cfg_data:
                        self.fine_labels = cfg_data["fine_labels"]
                    elif "id2label" in cfg_data:
                        ids = sorted(int(k) for k in cfg_data["id2label"])
                        self.fine_labels = [cfg_data["id2label"][str(i)] for i in ids]
                        logger.info(f"Extracted {len(self.fine_labels)} fine labels from model id2label")
                    else:
                        self.fine_labels = self.DEFAULT_FINE_LABELS
                    if "coarse_labels" in cfg_data:
                        self.coarse_labels = cfg_data["coarse_labels"]
                    else:
                        self.coarse_labels = [
                            "Formal",
                            "Informal (Ambiguity)",
                            "Informal (Other)",
                            "Informal (Presumption)",
                            "Informal (Relevance)",
                            "Non-Fallacious",
                        ]
                        logger.info(f"Using {len(self.coarse_labels)} default coarse labels")

                logger.info("✅ ONNX Model ready on CPU.")
                return self
            except Exception as e:
                logger.error(f"Failed to load ONNX model: {e}. Falling back to PyTorch...")
                self.use_onnx = False

        # 1. Clear memory
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # 2. VRAM Guard - 4bit fits in ~1.2GB
        load_device = self.device
        use_4bit = False
        if torch.cuda.is_available():
            try:
                total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if total_vram < 4.5:
                    logger.warning(f"Low VRAM ({total_vram:.1f}GB). Enabling 4-bit for Unified Classifier.")
                    use_4bit = True
            except Exception:
                pass

        config_path = Path(path) / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                cfg_data = json.load(f)
            if "fine_labels" in cfg_data:
                self.fine_labels = cfg_data["fine_labels"]
            elif "id2label" in cfg_data:
                ids = sorted(int(k) for k in cfg_data["id2label"])
                self.fine_labels = [cfg_data["id2label"][str(i)] for i in ids]
                logger.info(f"Extracted {len(self.fine_labels)} fine labels from model id2label")
            else:
                self.fine_labels = self.DEFAULT_FINE_LABELS
            if "coarse_labels" in cfg_data:
                self.coarse_labels = cfg_data["coarse_labels"]
            else:
                self.coarse_labels = [
                    "Formal",
                    "Informal (Ambiguity)",
                    "Informal (Other)",
                    "Informal (Presumption)",
                    "Informal (Relevance)",
                    "Non-Fallacious",
                ]
                logger.info(f"Using {len(self.coarse_labels)} default coarse labels")

        logger.info(f"Loading weights into {load_device} (4bit={use_4bit})...")
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)

        hf_config = AutoConfig.from_pretrained(path, local_files_only=True)
        hf_config.num_labels_coarse = len(self.coarse_labels)
        hf_config.num_labels_fine = len(self.fine_labels)

        # 3. Quantized Loading
        bnb_config = None
        if use_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                llm_int8_enable_fp32_cpu_offload=True,
            )

        # 4. Authoritative Model Loading (Prioritize Standard HF for Phase 4)
        try:
            # Try standard sequence classification first (Phase 4)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                path,
                config=hf_config,
                local_files_only=True,
                quantization_config=bnb_config,
                ignore_mismatched_sizes=True,
                device_map="auto" if use_4bit else None,
            )

            # Detect architecture
            if hasattr(self.model, "classifier") and getattr(self.model.config, "num_labels", 0) >= 24:  # type: ignore[attr-defined]
                logger.info("✅ Authoritative Phase 4 single-head model loaded.")
                self.is_single_head = True
            elif hf_config.model_type == "deberta-v2":
                # Only try multi-head for DeBERTa
                logger.warning("Model does not match Phase 4 single-head. Attempting Legacy Multi-Head load...")
                self.model = DebertaV3MultiHead.from_pretrained(
                    path,
                    config=hf_config,
                    local_files_only=True,
                    quantization_config=bnb_config,
                    ignore_mismatched_sizes=True,
                    device_map="auto" if use_4bit else None,
                )
                self.is_single_head = False
                logger.info("✅ Legacy multi-head model loaded.")
            else:
                logger.warning(
                    f"Loaded standard {hf_config.model_type} model with "
                    f"{hf_config.num_labels} labels — not a supported configuration. "
                    f"Expected single-head (num_labels>=24) or DeBERTa multi-head."
                )
                raise RuntimeError(
                    f"Unsupported model configuration: {hf_config.model_type} "
                    f"with {hf_config.num_labels} labels. "
                    "Expected single-head (num_labels>=24) or DeBERTa multi-head."
                )

        except Exception as e:
            logger.error(f"Failed to load authoritative model: {e}")
            raise

        assert self.model is not None
        if use_4bit:
            # For quantized models with custom heads, we sometimes need to force
            # the heads to the same device as the base model's last layer
            device = next(self.model.parameters()).device
            if hasattr(self.model, "coarse_head"):
                self.model.coarse_head.to(device)
                self.model.fine_head.to(device)
                self.model.pooler.to(device)
            # FORCE INITIALIZATION
            self._initialize_bnb(self.model)
        elif not use_4bit:
            self.model.to(load_device)

        self.model.eval()
        logger.info(f"✅ Authoritative model ready on {self.model.device} (is_single_head={self.is_single_head})")

    async def predict_coarse(self, text: str, skip_cache: bool = False) -> tuple[str, float, float]:
        res = await self.predict(text, skip_cache=skip_cache)
        return (res.get("coarse_label", "Unknown"), res.get("coarse_confidence", 0.0), res.get("latency_ms", 0.0))

    async def predict_fine(
        self, text: str, include_explanations: bool = False, skip_cache: bool = False
    ) -> tuple[list[str], list[float], list[str], list[float], list[dict], bool, float]:
        res = await self.predict(text, include_explanations=include_explanations, skip_cache=skip_cache)
        f_labels = res.get("fine_labels", [])
        f_confs = res.get("fine_confidences", [])
        return (
            f_labels[:3],
            f_confs[:3],
            f_labels,
            f_confs,
            res.get("salient_tokens", []),
            res.get("explanations_requested", False),
            res.get("latency_ms", 0.0),
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences while preserving offsets."""
        import re
        # Pattern 1: Punctuation followed by whitespace and uppercase (standard)
        # Pattern 2: Punctuation followed immediately by uppercase (e.g. "...refute.Demo...")
        combined = re.compile(r"(?<=[.!?])(?:\s+(?=[A-Z])|(?=[A-Z][a-z]))")
        indices = [0] + [m.end() for m in combined.finditer(text)] + [len(text)]
        sentences = []
        for i in range(len(indices) - 1):
            start = indices[i]
            end = indices[i + 1]
            sent = text[start:end].strip()
            if len(sent) > 5:
                sentences.append(sent)
        return sentences

    async def predict_fine_multi(
        self, text: str, include_explanations: bool = False, skip_cache: bool = False
    ) -> dict:
        """Multi-sentence fallacy detection with per-sentence analysis and aggregation."""
        start_time = time.perf_counter()

        # Split into sentences
        sentences = self._split_sentences(text)

        # Handle single sentence case
        if len(sentences) <= 1:
            single_result = await self.predict(text, include_explanations=include_explanations, skip_cache=skip_cache)
            # Convert single result to multi format
            sentence_details = []
            if sentences:
                sent = sentences[0]
                sent_start = text.find(sent)
                sent_end = sent_start + len(sent) if sent_start != -1 else len(text)
                sentence_details = [
                    {
                        "sentence": sent,
                        "start": sent_start,
                        "end": sent_end,
                        "label": single_result.get("fine_labels", [None])[0],
                        "score": single_result.get("fine_confidences", [0.0])[0],
                    }
                ]
            return {
                "fine_labels": single_result.get("fine_labels", []),
                "fine_confidences": single_result.get("fine_confidences", []),
                "sentence_details": sentence_details,
                "salient_tokens": single_result.get("salient_tokens", []),
                "explanations_requested": single_result.get("explanations_requested", include_explanations),
                "latency_ms": (time.perf_counter() - start_time) * 1000,
            }
        
        # Process each sentence
        sentence_results = []
        sentence_details = []
        all_salient_tokens = []
        text_offset = 0
        
        for sentence in sentences:
            # Find actual sentence position in original text
            sent_start = text.find(sentence, text_offset)
            if sent_start == -1:
                sent_start = text_offset
            sent_end = sent_start + len(sentence)
            
            # Get prediction for this sentence
            res = await self.predict(sentence, include_explanations=include_explanations, skip_cache=skip_cache)
            
            # Collect top labels for this sentence
            top_labels = []
            top_scores = []
            fine_labels = res.get("fine_labels", [])
            fine_scores = res.get("fine_confidences", [])
            
            # Add top-1 label if present
            if fine_labels and fine_scores:
                top_labels.append(fine_labels[0])
                top_scores.append(fine_scores[0])
                # Add top-2 if score >= 0.25
                if len(fine_labels) > 1 and fine_scores[1] >= 0.25:
                    top_labels.append(fine_labels[1])
                    top_scores.append(fine_scores[1])
            
            sentence_results.append({
                "sentence": sentence,
                "start": sent_start,
                "end": sent_end,
                "labels": top_labels,
                "scores": top_scores,
                "salient_tokens": res.get("salient_tokens", [])
            })
            
            # Create sentence details for output
            if fine_labels and fine_scores:
                sentence_details.append({
                    "sentence": sentence,
                    "start": sent_start,
                    "end": sent_end,
                    "label": fine_labels[0],
                    "score": fine_scores[0],
                })
            
            # Collect salient tokens with adjusted offsets
            for token in res.get("salient_tokens", []):
                adjusted_token = token.copy()
                adjusted_token["start"] = token["start"] + sent_start
                adjusted_token["end"] = token["end"] + sent_start
                all_salient_tokens.append(adjusted_token)
            
            text_offset = sent_end
        
        # Aggregate results across sentences
        label_scores = {}
        for sent_result in sentence_results:
            for label, score in zip(sent_result["labels"], sent_result["scores"]):
                if label not in label_scores:
                    label_scores[label] = []
                label_scores[label].append(score)
        
        # Calculate max confidence for each label
        final_labels = []
        final_scores = []
        for label, scores in label_scores.items():
            max_score = max(scores)
            final_labels.append(label)
            final_scores.append(max_score)
        
        # Sort by confidence descending
        sorted_pairs = sorted(zip(final_labels, final_scores), key=lambda x: x[1], reverse=True)
        final_labels = [label for label, _ in sorted_pairs]
        final_scores = [score for _, score in sorted_pairs]
        
        return {
            "fine_labels": final_labels,
            "fine_confidences": final_scores,
            "sentence_details": sentence_details,
            "salient_tokens": all_salient_tokens,
            "explanations_requested": include_explanations,
            "latency_ms": (time.perf_counter() - start_time) * 1000,
        }


unified_classifier = UnifiedClassifier()
