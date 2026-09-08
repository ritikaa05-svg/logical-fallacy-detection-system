"""Evaluate Stage 3 fallacy classifier on held-out test data."""

import argparse
import json
from collections import Counter
from pathlib import Path

import torch
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def load_v1_1_classes() -> set[str]:
    p = Path("data/unified_training_data_v1.1.json")
    if p.exists():
        with open(p) as f:
            d = json.load(f)
        return {x["fallacy"] for x in d}
    return set()


def main():
    parser = argparse.ArgumentParser(description="Evaluate Stage 3 classifier on held-out data.")
    parser.add_argument(
        "--data-path",
        default="data/unified_training_data_v1.2.json",
        help="Path to the training/evaluation dataset (default: data/unified_training_data_v1.2.json)",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        default=True,
        help="Compute majority-class baseline (default: True)",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_false",
        dest="baseline",
        help="Skip majority-class baseline",
    )
    parser.add_argument(
        "--model-path",
        default="models/stage3_production_fallacy",
        help="Path to trained model directory",
    )
    args = parser.parse_args()

    with open(args.data_path) as f:
        data = json.load(f)

    texts = [d["text"] for d in data]
    labels_list = sorted({d["fallacy"] for d in data})
    label2id = {l: i for i, l in enumerate(labels_list)}
    labels = [label2id[d["fallacy"]] for d in data]

    print(f"Dataset: {len(texts)} samples, {len(labels_list)} classes")
    print(f"Loaded from: {args.data_path}")
    print()

    print("Per-class counts:")
    for l in labels_list:
        print(f"  {l}: {labels.count(label2id[l])}")
    print()

    prev_classes = load_v1_1_classes()
    new_classes = [l for l in labels_list if l not in prev_classes]
    if new_classes:
        print(f"New in v1.2 ({len(new_classes)} classes with zero samples in v1.1):")
        for cl in new_classes:
            print(f"  {cl} ({labels.count(label2id[cl])} samples)")
        print()

    if args.baseline:
        majority_class = Counter(labels).most_common(1)[0][0]
        majority_f1 = f1_score(labels, [majority_class] * len(labels), average="macro")
        print(f"Majority baseline (macro F1): {majority_f1:.4f}")
    else:
        majority_f1 = None

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=labels
        )
    except ValueError:
        print("Cannot stratify — using random split")
        X_train, X_test, y_train, y_test = train_test_split(texts, labels, test_size=0.2, random_state=42)

    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    print()

    id2label = {i: l for l, i in label2id.items()}

    model_path = Path(args.model_path)
    if not model_path.exists():
        print(f"No trained model at {args.model_path}")
        return

    print(f"Loading trained model from {args.model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    model.eval()

    all_preds = []
    batch_size = 16
    for i in range(0, len(X_test), batch_size):
        batch_texts = X_test[i : i + batch_size]
        inputs = tokenizer(
            batch_texts,
            return_tensors="pt",
            truncation=True,
            max_length=256,
            padding=True,
        )
        with torch.no_grad():
            logits = model(**inputs).logits
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.extend(preds)

    all_labels = sorted(set(y_test) | set(all_preds))
    target_names = [id2label.get(i, f"class_{i}") for i in all_labels]

    print("=" * 60)
    print("CLASSIFICATION REPORT")
    print("=" * 60)
    print(
        classification_report(
            y_test,
            all_preds,
            target_names=target_names,
            labels=all_labels,
            zero_division=0,
        )
    )

    macro_f1 = f1_score(y_test, all_preds, average="macro")
    micro_f1 = f1_score(y_test, all_preds, average="micro")
    print(f"Macro F1:  {macro_f1:.4f}")
    print(f"Micro F1:  {micro_f1:.4f}")
    if majority_f1 is not None:
        print(f"Baseline:  {majority_f1:.4f}")
        print(f"Delta:     {macro_f1 - majority_f1:+.4f}")


if __name__ == "__main__":
    main()
