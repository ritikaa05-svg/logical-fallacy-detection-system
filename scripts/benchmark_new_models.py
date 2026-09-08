# NOTE (2026-08-05): SUPERSEDED by scripts/benchmark_model_series.py, which
# evaluates all model generations on the standardized splits and writes
# results/model_series_benchmark.json. Kept for manual ONNX spot-checks;
# stage1_v12 was retired (degenerate) and phase4_final_model was removed.
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import onnxruntime as ort
import torch
from transformers import AutoTokenizer

# Add project root to path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- TEST CASES ---
TEST_CASES = {
    "Non-Arguments": [
        "LogiScan uses a 4-stage neuro-symbolic pipeline to detect logical fallacies in text.",
        "Python supports asynchronous programming.",
        "Water boils at 100°C.",
        "The sky is blue and the grass is green.",
    ],
    "Genuine Arguments": [
        "Because taxes increased, businesses left the city.",
        "Smoking causes cancer because the chemicals damage DNA and prevent the body from fixing it.",
        "The sun has risen every day of my life. Therefore, the sun will rise tomorrow.",
    ],
    "Formal Fallacies (Critical Check)": [
        {
            "text": "If it rains, the grass is wet. The grass is wet. Therefore, it rained.",
            "fallacy": "affirming_consequent",
        },
        {
            "text": "If I am in Paris, I am in France. I am not in Paris. Therefore, I am not in France.",
            "fallacy": "denying_antecedent",
        },
    ],
    "Informal Fallacies": [
        {"text": "So you're saying we should just give up and let everyone starve?", "fallacy": "straw_man"},
        {"text": "You are just a shill for the oil companies.", "fallacy": "ad_hominem"},
        {"text": "I wore my lucky socks and won, so the socks caused the win.", "fallacy": "false_cause"},
        {"text": "Everyone is doing it, so it must be right.", "fallacy": "bandwagon"},
    ],
}


def load_onnx_direct(path):
    onnx_path = Path(path) / "model.onnx"
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    # Load config to get id2label
    with open(Path(path) / "config.json") as f:
        config = json.load(f)
    id2label = {int(k): v for k, v in config.get("id2label", {}).items()}

    return session, tokenizer, id2label


async def run_inference_onnx(session, tokenizer, text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=256)
    onnx_inputs = {"input_ids": inputs["input_ids"].numpy(), "attention_mask": inputs["attention_mask"].numpy()}
    outputs = session.run(None, onnx_inputs)
    logits = torch.from_numpy(outputs[0])
    probs = torch.softmax(logits, dim=-1)[0]
    return probs


async def compare_models():
    print("🚀 Starting Side-by-Side Model Comparison (Fresh vs. Production)...")

    # Paths
    models_config = [
        {
            "name": "Stage 1 (Gatekeeper)",
            "new": "models/stage1_v13_classifier",
            "old": "models/stage1_v13_classifier",
            "is_binary": True,
        },
        {
            "name": "Stage 2 (Coarse)",
            "new": "models/stage3_v13_classifier",
            "old": "models/stage3_v13_classifier",
            "is_binary": False,
        },
        {
            "name": "Stage 3 (Fine)",
            "new": "models/stage3_v13_classifier",
            "old": "models/stage3_v12",
            "is_binary": False,
        },
    ]

    # Load all models
    loaded_models = {}
    for cfg in models_config:
        print(f"Loading {cfg['name']}...")
        loaded_models[cfg["name"]] = {
            "new": load_onnx_direct(cfg["new"]),
            "old": load_onnx_direct(cfg["old"]),
            "is_binary": cfg["is_binary"],
        }

    for cat, samples in TEST_CASES.items():
        print("\n" + "=" * 40)
        print(f" CATEGORY: {cat}")
        print("=" * 40)

        for sample in samples:
            text = sample if isinstance(sample, str) else sample["text"]
            expected = sample.get("fallacy") if isinstance(sample, dict) else None

            print(f'\nText: "{text[:100]}..."')

            for name, m_data in loaded_models.items():
                probs_old = await run_inference_onnx(m_data["old"][0], m_data["old"][1], text)
                probs_new = await run_inference_onnx(m_data["new"][0], m_data["new"][1], text)

                if m_data["is_binary"]:
                    # Gatekeeper: Index 1 is 'Logical'
                    old_val = probs_old[1].item()
                    new_val = probs_new[1].item()
                    print(
                        f"  {name:20}: OLD={old_val:.4f} | NEW={new_val:.4f} {'(FIXED)' if old_val > 0.6 and new_val < 0.6 and cat == 'Non-Arguments' else ''}"
                    )
                else:
                    # Classifiers: Get top prediction
                    old_idx = torch.argmax(probs_old).item()
                    new_idx = torch.argmax(probs_new).item()
                    old_lbl = m_data["old"][2][old_idx]
                    new_lbl = m_data["new"][2][new_idx]
                    old_conf = probs_old[old_idx].item()
                    new_conf = probs_new[new_idx].item()

                    marker = ""
                    if expected:
                        if new_lbl == expected and old_lbl != expected:
                            marker = "⭐ IMPROVED"
                        elif new_lbl == expected:
                            marker = "✅ CORRECT"
                        elif old_lbl == expected:
                            marker = "❌ REGRESSION"
                        else:
                            marker = "❌ BOTH WRONG"

                    print(
                        f"  {name:20}: OLD={old_lbl:20} ({old_conf:.2f}) | NEW={new_lbl:20} ({new_conf:.2f}) {marker}"
                    )


if __name__ == "__main__":
    asyncio.run(compare_models())
