"""Before/after fine-tuning evaluation for the defense slides.

Answers two supervisor questions with real numbers:

1. "Off-the-shelf or custom?" — compares the off-the-shelf HuggingFace
   pretrained backbone (randomly-initialised head, zero fine-tuning) against
   the fine-tuned production model, plus a from-scratch TF-IDF + Logistic
   Regression reference and the majority-class baseline.

2. "Before and after fine-tune?" — the same split, same data, only the
   training state differs.

Runs:
  - Stage 2/3 (29 classes): microsoft/deberta-v3-small (zero-shot) vs
    models/stage3_v13_classifier (fine-tuned), stratified 90/10 split seed 42
    (identical to cloud_training/scripts/train_stage3_v13.py).
  - Stage 1 (binary): distilbert-base-uncased (zero-shot) vs
    models/stage1_v13_classifier (fine-tuned), on data/stage1_splits.json val split.

Usage:
    venv/bin/python scripts/eval_zero_shot.py
"""
import argparse
import json
from pathlib import Path

import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
RESULTS_PATH = ROOT / "results" / "before_after_finetune.json"


def tokenize(tokenizer, texts, max_length):
    enc = tokenizer(
        texts,
        truncation=True,
        padding=True,
        max_length=max_length,
        return_tensors="pt",
    )
    return {k: v.to(DEVICE) for k, v in enc.items()}


def eval_model(model, tokenizer, texts, labels, max_length=256, batch_size=32):
    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            inputs = tokenize(tokenizer, batch_texts, max_length)
            logits = model(**inputs).logits
            preds.extend(torch.argmax(logits, dim=1).cpu().tolist())
    return f1_score(labels, preds, average="macro")


def majority_baseline_f1(labels):
    majority = max(set(labels), key=labels.count)
    return f1_score(labels, [majority] * len(labels), average="macro")


def tfidf_lr_baseline(train_texts, train_labels, val_texts, val_labels):
    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=50_000, sublinear_tf=True)
    X_tr = vec.fit_transform(train_texts)
    X_va = vec.transform(val_texts)
    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(X_tr, train_labels)
    return f1_score(val_labels, clf.predict(X_va), average="macro")


def load_stage23_split(seed):
    with open(ROOT / "data" / "unified_training_data_v1.3.json") as f:
        data = json.load(f)
    labeled = [d for d in data if "fallacy" in d]
    texts = [d["text"] for d in labeled]
    label_list = sorted({d["fallacy"] for d in labeled})
    labels = [label_list.index(d["fallacy"]) for d in labeled]
    X_train, X_val, y_train, y_val = train_test_split(
        texts, labels, test_size=0.1, random_state=seed, stratify=labels
    )
    return texts, labels, X_train, y_train, X_val, y_val, label_list


def load_stage1_split():
    with open(ROOT / "data" / "stage1_splits.json") as f:
        splits = json.load(f)
    val = splits["val"]
    train = splits["train"]
    return (
        [d["text"] for d in train],
        [d["label"] for d in train],
        [d["text"] for d in val],
        [d["label"] for d in val],
    )


def run_stage23(seed):
    print("\n=== Stage 2/3: 29-class fallacy classification (val split, seed 42) ===")
    _, _, X_train, y_train, X_val, y_val, label_list = load_stage23_split(seed)
    n_val = len(X_val)
    results = {"val_samples": n_val, "n_classes": len(label_list)}

    results["majority_class_baseline"] = round(majority_baseline_f1(y_val), 4)
    print(f"majority-class baseline          : {results['majority_class_baseline']:.4f}")

    results["tfidf_logreg_from_scratch"] = round(
        tfidf_lr_baseline(X_train, y_train, X_val, y_val), 4
    )
    print(f"TF-IDF + LogReg (custom, scratch) : {results['tfidf_logreg_from_scratch']:.4f}")

    zero_shot = AutoModelForSequenceClassification.from_pretrained(
        "microsoft/deberta-v3-small",
        num_labels=len(label_list),
        ignore_mismatched_sizes=True,
    ).to(DEVICE)
    tokenizer = AutoTokenizer.from_pretrained("microsoft/deberta-v3-small")
    results["deberta_zero_shot"] = round(
        eval_model(zero_shot, tokenizer, X_val, y_val), 4
    )
    print(f"deberta-v3-small OFF-THE-SHELF     : {results['deberta_zero_shot']:.4f}")

    finetuned = AutoModelForSequenceClassification.from_pretrained(
        str(ROOT / "models" / "stage3_v13_classifier"),
        local_files_only=True,
    ).to(DEVICE)
    ft_tokenizer = AutoTokenizer.from_pretrained(
        str(ROOT / "models" / "stage3_v13_classifier"), local_files_only=True
    )
    results["deberta_finetuned"] = round(
        eval_model(finetuned, ft_tokenizer, X_val, y_val), 4
    )
    print(f"deberta-v3-small FINE-TUNED        : {results['deberta_finetuned']:.4f}")

    del zero_shot, finetuned
    torch.cuda.empty_cache() if DEVICE.type == "cuda" else None
    return results


def run_stage1():
    print("\n=== Stage 1: binary argument gate (val split) ===")
    X_train, y_train, X_val, y_val = load_stage1_split()
    results = {"val_samples": len(X_val)}

    results["majority_class_baseline"] = round(majority_baseline_f1(y_val), 4)
    print(f"majority-class baseline          : {results['majority_class_baseline']:.4f}")

    zero_shot = AutoModelForSequenceClassification.from_pretrained(
        "distilbert-base-uncased", num_labels=2, ignore_mismatched_sizes=True
    ).to(DEVICE)
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    results["distilbert_zero_shot"] = round(
        eval_model(zero_shot, tokenizer, X_val, y_val, max_length=512), 4
    )
    print(f"distilbert OFF-THE-SHELF           : {results['distilbert_zero_shot']:.4f}")

    finetuned = AutoModelForSequenceClassification.from_pretrained(
        str(ROOT / "models" / "stage1_v13_classifier"), local_files_only=True
    ).to(DEVICE)
    ft_tokenizer = AutoTokenizer.from_pretrained(
        str(ROOT / "models" / "stage1_v13_classifier"), local_files_only=True
    )
    results["distilbert_finetuned"] = round(
        eval_model(finetuned, ft_tokenizer, X_val, y_val, max_length=512), 4
    )
    print(f"distilbert FINE-TUNED              : {results['distilbert_finetuned']:.4f}")
    return results


def report_only(seed):
    """Print + save the full per-class classification report of the fine-tuned
    Stage 2/3 model on the standardized seed-42 val split."""
    _, _, _, _, X_val, y_val, label_list = load_stage23_split(seed)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(ROOT / "models" / "stage3_v13_classifier"), local_files_only=True
    ).to(DEVICE)
    tokenizer = AutoTokenizer.from_pretrained(
        str(ROOT / "models" / "stage3_v13_classifier"), local_files_only=True
    )
    preds = []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(X_val), 32):
            inputs = tokenize(tokenizer, X_val[i : i + 32], 256)
            logits = model(**inputs).logits
            preds.extend(torch.argmax(logits, dim=1).cpu().tolist())

    report = classification_report(
        y_val, preds, target_names=label_list, digits=3, zero_division=0, output_dict=True
    )
    print(classification_report(y_val, preds, target_names=label_list, digits=3, zero_division=0))
    out = ROOT / "results" / "val_report_seed42.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"split_seed": seed, "report": report}, f, indent=2)
    print(f"Saved {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    if args.report_only:
        report_only(args.seed)
        return

    out = {
        "seed": args.seed,
        "stage23": run_stage23(args.seed),
        "stage1": run_stage1(),
        "device": str(DEVICE),
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved {RESULTS_PATH}")


if __name__ == "__main__":
    main()
