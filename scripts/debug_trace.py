import os
import sys

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Set project root
sys.path.append(os.getcwd())


def trace_pipeline(model_dir, text):
    print(f"\n--- Tracing: '{text}' ---")

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
    model.eval()

    # 1. Tokenizer
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    print(f"Input IDs: {inputs['input_ids'].tolist()}")

    # 2. Inference
    with torch.no_grad():
        logits = model(**inputs).logits

    probs = torch.softmax(logits, dim=-1)[0]
    top_prob, top_idx = torch.max(probs, dim=0)

    # Label mapping
    id2label = {int(k): v for k, v in model.config.id2label.items()}
    label = id2label[top_idx.item()]

    print(f"Logits: {logits.tolist()}")
    print(f"Predicted Label: {label} (Conf: {top_prob.item():.4f})")


test_cases = [
    "A logical fallacy is a flaw in reasoning.",  # factual_statement
    "If it rains, the ground gets wet. It is raining. Therefore the ground gets wet.",  # valid_reasoning
    "Person A: We should build more bike lanes. Person B: So you want to ban all cars and force everyone to walk?",  # straw_man
    "You're wrong because you're an idiot.",  # ad_hominem
    "If it rains, the ground gets wet. The ground is wet. Therefore it rained.",  # affirming_consequent
]

model_dir = "models/new/stage3_fine_classifier"
for t in test_cases:
    trace_pipeline(model_dir, t)
