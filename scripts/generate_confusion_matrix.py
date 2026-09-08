"""Generate a confusion matrix PNG for the defense slides.

Evaluates the production Stage 2/3 model (`models/stage3_v13_classifier`) on a
stratified 500-sample subset of `data/unified_training_data_v1.3.json` and
renders a heatmap to `docs/slides/assets/confusion_matrix.png`.

Usage:
    venv/bin/python scripts/generate_confusion_matrix.py
"""
import json
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models" / "stage3_v13_classifier"
DATA_FILE = ROOT / "data" / "unified_training_data_v1.3.json"
OUT = ROOT / "docs" / "slides" / "assets" / "confusion_matrix.png"

MAX_SAMPLES = 500
BATCH_SIZE = 32
MAX_LENGTH = 256


def main() -> None:
    with open(DATA_FILE) as f:
        data = json.load(f)
    labeled = [d for d in data if "fallacy" in d]
    texts = [d["text"] for d in labeled]
    labels = [d["fallacy"] for d in labeled]

    _, X_val, _, y_val = train_test_split(
        texts, labels, test_size=0.1, random_state=42, stratify=labels
    )
    rng = random.Random(42)
    idx = rng.sample(range(len(X_val)), k=min(MAX_SAMPLES, len(X_val)))
    X_val = [X_val[i] for i in idx]
    y_val = [y_val[i] for i in idx]

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(MODEL_DIR), local_files_only=True
    )
    model.eval()
    id2label = {int(k): v for k, v in model.config.id2label.items()}
    label_list = sorted({int(k) for k in model.config.id2label})

    preds = []
    with torch.no_grad():
        for i in range(0, len(X_val), BATCH_SIZE):
            batch = X_val[i : i + BATCH_SIZE]
            enc = tokenizer(
                batch,
                truncation=True,
                padding=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            )
            logits = model(**enc).logits
            preds.extend(torch.argmax(logits, dim=1).tolist())

    label2id = {v: k for k, v in id2label.items()}
    y_int = [label2id[y] for y in y_val]
    cm = confusion_matrix(y_int, preds, labels=label_list)

    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(cm, cmap="viridis", norm=matplotlib.colors.LogNorm())
    ax.set_xticks(range(len(label_list)), [id2label[l] for l in label_list], rotation=90, fontsize=8)
    ax.set_yticks(range(len(label_list)), [id2label[l] for l in label_list], fontsize=8)
    ax.set_xlabel("Predicted", fontsize=11)
    ax.set_ylabel("True", fontsize=11)
    ax.set_title(
        "Confusion Matrix — Production Stage 2/3 (29 classes, 500-sample stratified val subset)",
        fontsize=12,
    )
    fig.colorbar(im, ax=ax, label="Count (log scale)")

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print(f"Saved {OUT}")

    with open(ROOT / "results" / "confusion_matrix.json", "w") as f:
        json.dump(
            {
                "matrix": cm.tolist(),
                "labels": [id2label[l] for l in label_list],
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    main()
