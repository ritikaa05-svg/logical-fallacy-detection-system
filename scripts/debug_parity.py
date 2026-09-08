import os
import sys

import onnxruntime as ort
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Set project root
sys.path.append(os.getcwd())


def check_parity(model_dir):
    print(f"--- Checking parity for {model_dir} ---")

    # Load PyTorch Model
    print("Loading PyTorch model...")
    pt_model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
    pt_model.eval()
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)

    # Load ONNX Model
    print("Loading ONNX model...")
    ort_session = ort.InferenceSession(f"{model_dir}/model.onnx", providers=["CPUExecutionProvider"])

    # Representative inputs
    test_texts = [
        "If it rains, the ground gets wet.",
        "You're wrong because you're an idiot.",
        "So you want to ban all cars and force everyone to walk?",
        "A logical fallacy is a flaw in reasoning.",
        "The ground is wet, therefore it rained.",
    ]

    for text in test_texts:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)

        # PyTorch Inference
        with torch.no_grad():
            pt_logits = pt_model(**inputs).logits

        # ONNX Inference
        onnx_inputs = {"input_ids": inputs["input_ids"].numpy(), "attention_mask": inputs["attention_mask"].numpy()}
        ort_logits = torch.from_numpy(ort_session.run(None, onnx_inputs)[0])

        # Compare
        diff = torch.abs(pt_logits - ort_logits).max().item()
        print(f"Text: '{text[:30]}...' | Max logit diff: {diff:.6e}")

        if diff > 1e-4:
            print("❌ Parity FAILED.")
        else:
            print("✅ Parity PASSED.")


if __name__ == "__main__":
    check_parity("models/new/stage3_fine_classifier")
