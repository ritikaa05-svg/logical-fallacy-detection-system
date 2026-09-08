import asyncio
import logging
import os
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Add project root to path
sys.path.append(os.getcwd())


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- TEST CASES ---
TEST_CASES = {
    "Non-Arguments": [
        "LogiScan uses a 4-stage neuro-symbolic pipeline to detect logical fallacies in text.",
        "A logical fallacy is a flaw in reasoning that weakens an argument.",
        "Python supports asynchronous programming.",
        "Water boils at 100°C.",
        "What is a straw man fallacy?",
    ],
    "Genuine Arguments": [
        "Because taxes increased, businesses left the city.",
        "If it rains, the ground gets wet. It is raining. Therefore the ground is wet.",
        "Smoking causes cancer because the chemicals damage DNA and prevent the body from fixing it.",
        "Therefore the proposal should be rejected.",
    ],
    "Known Fallacies": [
        {"text": "So you're saying we should just give up and let everyone starve?", "fallacy": "straw_man"},
        {"text": "You are just a shill for the oil companies.", "fallacy": "ad_hominem"},
        {"text": "I wore my lucky socks and won, so the socks caused the win.", "fallacy": "false_cause"},
        {"text": "What about the other problems in the world?", "fallacy": "red_herring"},
        {"text": "I'm right because I'm correct.", "fallacy": "begging_the_question"},
    ],
}


def load_model_direct(path):
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(path, local_files_only=True)
    model.eval()
    return model, tokenizer


async def run_inference(model, tokenizer, text, is_binary=True):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=256)
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]

    if is_binary:
        # LABEL_0 is negative (Non-Argument), LABEL_1 is positive (Argument)
        salience = probs[1].item()
        return salience >= 0.5, salience
    else:
        # Multi-class for Stage 2
        idx = torch.argmax(probs).item()
        label = model.config.id2label[idx]
        return label, probs[idx].item()


import onnxruntime as ort


def load_onnx_direct(path):
    onnx_path = Path(path) / "model.onnx"
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    return session, tokenizer


async def run_inference_onnx(session, tokenizer, text, is_binary=True):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=256)
    onnx_inputs = {"input_ids": inputs["input_ids"].numpy(), "attention_mask": inputs["attention_mask"].numpy()}
    outputs = session.run(None, onnx_inputs)
    logits = torch.from_numpy(outputs[0])
    probs = torch.softmax(logits, dim=-1)[0]

    if is_binary:
        salience = probs[1].item()
        return salience >= 0.5, salience
    else:
        idx = torch.argmax(probs).item()
        # id2label mapping usually in config.json, but ORT session doesn't have it directly
        # We'll assume the order is the same as the PyTorch model
        return idx, probs[idx].item()


async def run_validation():
    print("🚀 Starting Isolated Model Validation (Stage 1 & 2)...")

    s1_new_path = "models/new/stage1_gatekeeper"
    s2_new_path = "models/new/stage2_coarse_classifier"
    s1_old_path = "models/stage1_gatekeeper"
    s2_old_path = "models/stage2_coarse_classifier"

    # Load PyTorch
    print("Loading PyTorch models...")
    s1_new, t1_new = load_model_direct(s1_new_path)
    s2_new, t2_new = load_model_direct(s2_new_path)
    s1_old, t1_old = load_model_direct(s1_old_path)
    s2_old, t2_old = load_model_direct(s2_old_path)

    # Load ONNX
    print("Loading ONNX models...")
    s1_onnx, t1_onnx = load_onnx_direct(s1_new_path)
    s2_onnx, t2_onnx = load_onnx_direct(s2_new_path)

    comparison = []

    for cat, samples in TEST_CASES.items():
        print("\n" + "=" * 20)
        print(f" CATEGORY: {cat}")
        print("=" * 20)
        for sample in samples:
            text = sample if isinstance(sample, str) else sample["text"]

            # 1. Stage 1 Comparison
            _, sal_old = await run_inference(s1_old, t1_old, text, True)
            _, sal_new = await run_inference(s1_new, t1_new, text, True)
            _, sal_onnx = await run_inference_onnx(s1_onnx, t1_onnx, text, True)

            # 2. Stage 2 Comparison
            lbl_old, _ = await run_inference(s2_old, t2_old, text, False)
            lbl_new, _ = await run_inference(s2_new, t2_new, text, False)

            # For ONNX, run_inference returns index, map it manually
            lbl_idx_onnx, _ = await run_inference_onnx(s2_onnx, t2_onnx, text, False)
            lbl_onnx = s2_new.config.id2label[lbl_idx_onnx]

            print(f"\nText: {text[:60]}...")
            print(f"  S1 Salience: OLD={sal_old:.4f} | NEW_PT={sal_new:.4f} | NEW_ONNX={sal_onnx:.4f}")
            print(f"  S2 Category: OLD={lbl_old} | NEW_PT={lbl_new} | NEW_ONNX={lbl_onnx}")

            status = "✅ FIXED" if cat == "Non-Arguments" and sal_onnx < 0.6 else "STABLE"
            if cat == "Non-Arguments" and sal_old > 0.6 and sal_onnx < 0.6:
                print(f"  Result: {status}")

            comparison.append({"text": text, "cat": cat, "s1_old": sal_old, "s1_new": sal_onnx, "s2_new": lbl_onnx})

    return comparison


if __name__ == "__main__":
    asyncio.run(run_validation())
