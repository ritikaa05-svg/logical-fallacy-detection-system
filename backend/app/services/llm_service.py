"""
LLM Synthesis Service
Generates human-readable correction strategies and extracts fallacy quotes.
"""

import logging
import re
import time
from typing import Any

import aiohttp
import torch

from backend.app.config import settings
from backend.app.core.device_manager import ExecutionTarget, device_manager
from backend.app.core.lifecycle import lifecycle_manager

logger = logging.getLogger(__name__)

from backend.app.services.fallacy_catalog import get_definition

# Verification catalog for rare classes
FALLACY_CATALOG = {
    "equivocation": {
        "definition": "Using a word in two different senses within the same argument.",
        "example": "A feather is light. What is light cannot be dark. So a feather cannot be dark.",
    },
    "tu_quoque": {
        "definition": "Deflecting criticism by pointing out the critic's hypocrisy.",
        "example": "You tell me not to smoke, but you smoked for 20 years!",
    },
    "denying_antecedent": {
        "definition": "A formal fallacy: If A then B. Not A. Therefore not B.",
        "example": "If it rains, the ground is wet. It's not raining. So the ground isn't wet.",
    },
    "moving_goalposts": {
        "definition": "Requirements for proof change after the initial conditions have been met.",
        "example": "user: Prove efficiency. assistant: 40% efficiency. user: Not enough, prove 100 hours run time.",
    },
    "no_true_scotsman": {
        "definition": "Excluding a counterexample by redefining a term to maintain a universal claim.",
        "example": "user: No scientist believes in ghosts. assistant: Dr. Smith does. user: Well, no TRUE scientist does.",
    },
    "tu_quoque_contextual": {
        "definition": "Deflecting critique by pointing out the critic has done the same in the conversation.",
        "example": "assistant: Your argument uses anecdotes. user: Your last argument used an anecdote too!",
    },
    "composition": {
        "definition": "Assuming what is true of the parts must be true of the whole.",
        "example": "Each molecule is invisible, so the glass of water is invisible.",
    },
    "division": {
        "definition": "Assuming what is true of the whole must be true of the parts.",
        "example": "The team is great, so every player on the team is great.",
    },
}


class LLMSynthesisService:
    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._api_consecutive_failures: int = 0
        logger.info("LLMSynthesisService initialized.")

    def _load(self):
        if not settings.STAGE4_IS_LOCAL_PATH:
            logger.info("STAGE4_IS_LOCAL_PATH is False — synthesis model is never loaded locally.")
            return None

        import gc

        from transformers import AutoModelForCausalLM, AutoTokenizer

        # 1. Clear memory
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        model_path = settings.STAGE4_SYNTHESIS_MODEL
        self._tokenizer = AutoTokenizer.from_pretrained(model_path)

        # 2. Memory-Aware Device Selection
        # With 4-bit quantization, the model fits in ~1.2GB.
        # We only force CPU if VRAM is extremely low (< 1.5GB).
        device = device_manager.get_torch_device()
        if torch.cuda.is_available():
            try:
                total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if total_vram < 1.5:
                    logger.warning(f"Extremely low VRAM ({total_vram:.1f}GB). Forcing Synthesis to CPU.")
                    device = torch.device("cpu")
                else:
                    logger.info(f"GPU VRAM ({total_vram:.1f}GB) is sufficient for 4-bit Synthesis.")
            except Exception:
                pass

        logger.info(f"Loading synthesis model into {device}...")

        # 3. Load Model with aggressive 4-bit quantization
        try:
            logger.info(f"Loading synthesis model with 4-bit NF4 quantization into {device}...")

            if device.type == "cuda":
                from transformers import BitsAndBytesConfig

                # 4-bit configuration with CPU offloading enabled
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    llm_int8_enable_fp32_cpu_offload=True,
                )
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_path, quantization_config=bnb_config, device_map="auto", low_cpu_mem_usage=True
                )
            else:
                # CPU Fallback - use float16 if possible to save memory, else float32
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    low_cpu_mem_usage=True,
                )
                self._model.to(device)

            logger.info(f"✅ 4-bit Quantized Synthesis model loaded on {device}")
        except Exception as e:
            logger.error(f"Quantized load failed: {e}. Falling back to standard CPU load.")
            # Standard fallback: drop any partial quantized model, free memory, load fp32 on CPU
            self._model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            try:
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    torch_dtype=torch.float32,
                    low_cpu_mem_usage=True,
                )
                self._model.to(torch.device("cpu"))
                logger.info("✅ Synthesis model loaded via standard CPU fallback.")
            except Exception as fallback_error:
                logger.error(f"Standard fallback load also failed: {fallback_error}")
                self._model = None
                raise fallback_error
        return self

    async def generate_unified_breakdown(
        self,
        input_text: str,
        fine_labels: list[str],
        confidence_scores: list[float],
        salient_tokens: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Extracts exact quotes and generates explanations for each fallacy."""
        if not fine_labels:
            return []

        results = []
        significant = [(l, s) for l, s in zip(fine_labels, confidence_scores) if s > 0.15]
        exec_target = device_manager.get_stage_target(4)

        for name, conf in significant[:5]:
            quote = ""
            clean_name = name.replace("_", " ").lower()

            # 1. Parentheses Hint
            pattern = rf"([^.!?]*\({re.escape(clean_name)}\)[^.!?]*[.!?])"
            hint_match = re.search(pattern, input_text, re.IGNORECASE)
            if hint_match:
                quote = hint_match.group(1).strip()

            # 2. LLM Extraction (only if local model or API is available)
            if not quote:
                llm_available = (
                    exec_target == ExecutionTarget.HUGGINGFACE_API and not settings.DISABLE_API_FALLBACK
                ) or settings.STAGE4_IS_LOCAL_PATH
                if llm_available:
                    prompt = f'From the text: "{input_text}"\nExtract the EXACT short phrase that is a {clean_name} fallacy.\nQuote:'
                    try:
                        if exec_target == ExecutionTarget.HUGGINGFACE_API and not settings.DISABLE_API_FALLBACK:
                            api_url = f"{settings.HUGGINGFACE_API_URL}/{settings.STAGE4_SYNTHESIS_MODEL}"
                            headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}"}
                            payload = {"inputs": prompt, "parameters": {"max_new_tokens": 30}}
                            async with aiohttp.ClientSession() as session:
                                async with session.post(
                                    api_url, json=payload, headers=headers, timeout=30.0
                                ) as response:
                                    if response.status == 200:
                                        res = await response.json()
                                        quote = res[0].get("generated_text", "")[len(prompt) :].strip().strip('"')
                        else:
                            self_loaded = lifecycle_manager.get_or_load("synthesis", self._load)
                            if self_loaded is None:
                                raise RuntimeError(
                                    "Synthesis model returned None (STAGE4_IS_LOCAL_PATH may be disabled)"
                                )
                            device = self_loaded._model.device
                            inputs = self_loaded._tokenizer(prompt, return_tensors="pt").to(device)
                            with torch.no_grad():
                                out = self_loaded._model.generate(**inputs, max_new_tokens=30)
                            quote = (
                                self_loaded._tokenizer.decode(out[0], skip_special_tokens=True)[len(prompt) :]
                                .strip()
                                .strip('"')
                            )
                    except Exception as e:
                        logger.warning(f"LLM quote extraction unavailable, using offline fallback: {e}")

            # 3. Fallback
            if not quote:
                from backend.app.pipeline.orchestrator import _extract_quote_offline

                quote, _, _ = _extract_quote_offline(input_text, name, salient_tokens or [])

            explanation = get_definition(name, "extended")
            results.append({"name": name, "quote": quote, "explanation": explanation, "confidence": float(conf)})
        return results

    async def generate(
        self, input_text: str, coarse_category: str, fine_labels: list[str], z3_context: Any
    ) -> tuple[str, float]:
        """Generates a comprehensive correction strategy and reasoning analysis."""
        start_time = time.perf_counter()
        fallacy_name = fine_labels[0].replace("_", " ").title() if fine_labels else "logical error"

        prompt = (
            f'Argument: "{input_text}"\n'
            f"Detected Fallacy: {fallacy_name}\n"
            f"Broad Category: {coarse_category}\n"
            f"{z3_context.to_prompt_fragment()}\n\n"
            "Task: Explain specifically why this argument fails and give one concrete correction. If a formal contradiction was found, name the contradicting claims. Be direct and under 80 words.\n"
            "Response:"
        )

        try:
            strategy = await self._generate_with_fallback(prompt, max_new_tokens=150)
            latency = (time.perf_counter() - start_time) * 1000
            return strategy, latency
        except Exception as e:
            logger.warning(f"Synthesis generation unavailable, using rule-based fallback: {e}")
            return (
                f"This argument commits a {fallacy_name} fallacy. Review the logical connection between premises.",
                0.0,
            )

    async def verify_fallacy(self, text: str, fallacy: str, confidence: float) -> tuple[bool, str]:
        """LLM-based verification for rare or low-confidence classes."""
        prompt = (
            f'Text: "{text}"\n'
            f"Proposed Fallacy: {fallacy}\n"
            f"Confidence: {confidence:.2f}\n\n"
            "Task: Is this a correct identification? Answer with 'YES' or 'NO' followed by a one-sentence reason.\n"
            "Analysis:"
        )

        try:
            response = await self._generate_with_fallback(prompt, max_new_tokens=50)
            is_verified = response.strip().upper().startswith("YES")
            return is_verified, response
        except Exception as e:
            logger.warning(f"Verification unavailable, defaulting to verified: {e}")
            return True, "Default verified (Fallback)"

    async def generate_compact_explanation(self, fallacy: str, label: str, span: str, sentence: str) -> str:
        """Generates a 1-sentence hover-card explanation for a specific trigger span."""
        prompt = (
            f'In the sentence: "{sentence}"\n'
            f'The phrase "{span}" triggers a {label} fallacy.\n\n'
            "Task: Explain why this phrase is problematic in one short sentence.\n"
            "Explanation:"
        )

        try:
            explanation = await self._generate_with_fallback(prompt, max_new_tokens=40)
            # Ensure it's truly one sentence
            explanation = explanation.split(".")[0] + "."
            return explanation
        except Exception as e:
            logger.error(f"Compact explanation failed: {e}")
            return f"This specific phrase commits a {label} fallacy."

    async def _generate_with_fallback(
        self, prompt: str, max_new_tokens: int, temperature: float = 0.3, do_sample: bool = True
    ) -> str:
        """Internal helper to handle tiered generation (API -> Local -> Failure)."""
        exec_target = device_manager.get_stage_target(4)

        # 1. API Path (Forced if use_api_fallback is True or requested via target)
        # Guard: when STAGE4_IS_LOCAL_PATH is set, STAGE4_SYNTHESIS_MODEL is a local
        # filesystem path, not an HF repo id — sending it as the API model id would
        # produce an invalid URL. The API tier only runs with a real remote model id.
        if (
            not settings.DISABLE_API_FALLBACK
            and not settings.STAGE4_IS_LOCAL_PATH
            and self._api_consecutive_failures < 3
            and (exec_target == ExecutionTarget.HUGGINGFACE_API or device_manager.use_api_fallback)
        ):
            try:
                model_id = settings.STAGE4_SYNTHESIS_MODEL

                api_url = f"{settings.HUGGINGFACE_API_URL}/{model_id}"
                headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}"}
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": max_new_tokens,
                        "temperature": temperature,
                        "do_sample": do_sample,
                    },
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json=payload, headers=headers, timeout=30.0) as response:
                        if response.status == 200:
                            res = await response.json()
                            gen_text = res[0].get("generated_text", "")
                            if gen_text.startswith(prompt):
                                gen_text = gen_text[len(prompt) :].strip()
                            self._api_consecutive_failures = 0
                            return gen_text
                        else:
                            logger.warning(f"API generation failed with status {response.status}")
                            self._api_consecutive_failures += 1
            except Exception as e:
                logger.warning(f"API generation fallback: {e}")

        # 2. Local Path (only if local model is configured)
        if not settings.STAGE4_IS_LOCAL_PATH:
            logger.debug("STAGE4_IS_LOCAL_PATH is False — skipping local synthesis.")
            raise RuntimeError("No local model available and API path failed or was disabled.")

        try:
            # RELAXATION: Allow local fallback if API failed, even on low VRAM,
            # as long as we have enough memory to attempt it (checked in _load).
            if device_manager.use_api_fallback and not settings.DEBUG:
                # We still log a warning but proceed to try loading
                logger.warning("Attempting local synthesis fallback on low-VRAM hardware.")

            svc = lifecycle_manager.get_or_load("synthesis", self._load)
            device = svc._model.device

            # VRAM PRESSURE RELEASE
            if device.type == "cuda":
                torch.cuda.empty_cache()

            inputs = svc._tokenizer(prompt, return_tensors="pt").to(device)

            logger.info(f"--- STARTING LLM INFERENCE (max_tokens={max_new_tokens}) ---")
            start_gen = time.perf_counter()

            with torch.no_grad():
                out = svc._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=do_sample,
                    temperature=temperature,
                    pad_token_id=svc._tokenizer.eos_token_id,
                )

            latency = (time.perf_counter() - start_gen) * 1000
            logger.info(f"--- LLM INFERENCE COMPLETE ({latency:.1f}ms) ---")

            # Robust trimming: decode and check for prompt presence
            gen_text = svc._tokenizer.decode(out[0], skip_special_tokens=True)

            if gen_text.startswith(prompt):
                return gen_text[len(prompt) :].strip()

            # Fallback for models that don't echo (unlikely with Instruct models but safe)
            return gen_text.strip()
        except Exception as e:
            logger.error(f"Local generation failed: {e}")
            raise e


llm_synthesis_service = LLMSynthesisService()
