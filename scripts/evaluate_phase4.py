"""Evaluate Phase 4 fallacy classifier on unified training data."""

import argparse
import json
from pathlib import Path

import torch
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def main():
    parser = argparse.ArgumentParser(description="Evaluate Phase 4 Model")
    parser.add_argument("--model_path", type=str, default="models/stage3_v13_classifier", help="Path to trained model")
    parser.add_argument(
        "--data_path", type=str, default="data/unified_training_data.json", help="Path to unified training data"
    )
    args = parser.parse_args()

    # 1. Load Data
    print(f"📂 Loading data from {args.data_path}...")
    with open(args.data_path) as f:
        data = json.load(f)

    # 2. Load Model & Tokenizer
    print(f"🔍 Loading model from {args.model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_path)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_path)
    model.eval()

    # Use GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"💻 Using device: {device}")

    # 3. Get label mapping from model
    id2label = model.config.id2label
    label2id = model.config.label2id
    # Convert keys to int if they are strings from JSON
    id2label = {int(k): v for k, v in id2label.items()}

    # 4. Filter data to only include labels the model knows
    texts = []
    labels = []
    for d in data:
        if d["fallacy"] in label2id:
            texts.append(d["text"])
            labels.append(label2id[d["fallacy"]])
        else:
            print(f"⚠️ Warning: Fallacy '{d['fallacy']}' not in model taxonomy. Skipping.")

    print(f"📊 Dataset: {len(texts)} samples, {len(id2label)} classes")

    # 5. Split (Reproduce the test split used in training if possible, but here we just do a consistent split)
    # Note: If training used a specific seed/split, we should ideally use that.
    # Assuming 80/20 split was used.
    _, X_test, _, y_test = train_test_split(texts, labels, test_size=0.2, random_state=42, stratify=labels)

    print(f"🧪 Evaluation set size: {len(X_test)}")

    # 6. Inference
    all_preds = []
    batch_size = 32
    print("🚀 Running inference...")
    for i in tqdm(range(0, len(X_test), batch_size)):
        batch_texts = X_test[i : i + batch_size]
        inputs = tokenizer(batch_texts, return_tensors="pt", truncation=True, max_length=256, padding=True).to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.extend(preds)

    # 7. Reporting
    target_names = [id2label[i] for i in range(len(id2label))]

    print(f"\n{'=' * 60}")
    print("PHASE 4 CLASSIFICATION REPORT")
    print(f"{'=' * 60}")
    print(classification_report(y_test, all_preds, target_names=target_names, zero_division=0))

    macro_f1 = f1_score(y_test, all_preds, average="macro")
    micro_f1 = f1_score(y_test, all_preds, average="micro")
    print(f"Macro F1:  {macro_f1:.4f}")
    print(f"Micro F1:  {micro_f1:.4f}")

    # Save results to a file
    results = {
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "report": classification_report(
            y_test, all_preds, target_names=target_names, zero_division=0, output_dict=True
        ),
    }

    output_path = Path("docs/PHASE4_EVAL_RESULTS.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Results saved to {output_path}")


if __name__ == "__main__":
    main()
