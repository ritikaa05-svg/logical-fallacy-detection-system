"""
Train Stage 1: Binary Argument Gate (DistilBERT) on the stage1_splits dataset.

Kaggle-ready replacement for the degenerate `models/stage1_v12` checkpoint
(which outputs salience=1.000 for every input). Key properties:

- Reads `data/stage1_splits.json` (fixed train/val/test: 10,584 / 1,155 / 1,155).
- Base model `distilbert-base-uncased`, 2 labels: 0 = non-argument, 1 = argument.
  The backend maps `softmax(logits)[1]` -> salience (stage1_gatekeeper.py), so
  class index 1 MUST be "argument" — this script configures id2label accordingly.
- Best-val-macro-F1 checkpointing, linear warmup (10%), AdamW, grad clipping.
- Exports ONNX (non-fatal on failure) with dynamic sequence length.

Usage:
    python cloud_training/scripts/train_stage1_v13.py \
        --data data/stage1_splits.json \
        --output-dir models/stage1_v13_classifier \
        --epochs 3 --batch-size 32 --lr 3e-5
"""
import argparse
import json
import logging
import shutil
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, classification_report, f1_score
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
LABEL_NAMES = {0: "non_argument", 1: "argument"}


class ArgumentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(self.labels[idx], dtype=torch.long),
        }


def load_data(path: Path):
    with open(path) as f:
        splits = json.load(f)
    out = {}
    for key in ("train", "val", "test"):
        records = splits[key]
        out[key] = ([d["text"] for d in records], [d["label"] for d in records])
    return out


def evaluate(model, loader) -> dict:
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in loader:
            outputs = model(
                batch["input_ids"].to(DEVICE), attention_mask=batch["attention_mask"].to(DEVICE)
            )
            preds = torch.argmax(outputs.logits, dim=1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(batch["labels"].tolist())
    return {
        "accuracy": accuracy_score(all_labels, all_preds),
        "macro_f1": f1_score(all_labels, all_preds, average="macro", zero_division=0),
        "preds": all_preds,
        "labels": all_labels,
    }


def export_onnx(model, tokenizer, output_dir):
    logger.info("Exporting to ONNX...")
    model.eval()
    dummy = tokenizer(
        "test input", return_tensors="pt", padding="max_length", truncation=True, max_length=256
    )
    dummy_ids = dummy["input_ids"].to(DEVICE)
    dummy_mask = dummy["attention_mask"].to(DEVICE)

    onnx_path = output_dir / "model.onnx"
    torch.onnx.export(
        model,
        (dummy_ids, dummy_mask),
        onnx_path,
        opset_version=14,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "logits": {0: "batch"},
        },
    )
    logger.info(f"ONNX export complete: {onnx_path.name} ({onnx_path.stat().st_size / (1024**2):.1f} MB)")
    with open(output_dir / "model_config_onnx.json", "w") as f:
        json.dump({"labels": LABEL_NAMES, "num_labels": 2}, f, indent=2)
    zip_path = shutil.make_archive(str(output_dir.parent / output_dir.name), "zip", output_dir)
    logger.info(f"Package ready: {zip_path}")


def train(args):
    logger.info(f"Using device: {DEVICE} ({torch.cuda.get_device_name(0) if DEVICE.type == 'cuda' else 'cpu'})")
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Data not found at {data_path}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_data(data_path)
    X_train, y_train = data["train"]
    X_val, y_val = data["val"]
    X_test, y_test = data["test"]
    logger.info(
        f"Train: {len(X_train)} / Val: {len(X_val)} / Test: {len(X_test)} "
        f"(positives: {sum(y_train)})"
    )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    train_ds = ArgumentDataset(X_train, y_train, tokenizer, max_length=args.max_length)
    val_ds = ArgumentDataset(X_val, y_val, tokenizer, max_length=args.max_length)
    test_ds = ArgumentDataset(X_test, y_test, tokenizer, max_length=args.max_length)
    n_gpus = torch.cuda.device_count() if DEVICE.type == "cuda" else 0
    loader_batch = args.batch_size * n_gpus if n_gpus > 1 else args.batch_size
    train_loader = DataLoader(train_ds, batch_size=loader_batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=loader_batch * 2)
    test_loader = DataLoader(test_ds, batch_size=loader_batch * 2)

    config = AutoConfig.from_pretrained(args.base_model)
    config.num_labels = 2
    config.id2label = {str(k): v for k, v in LABEL_NAMES.items()}
    config.label2id = {v: k for k, v in LABEL_NAMES.items()}

    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model, config=config
    ).to(DEVICE)
    logger.info(f"Model params: {sum(p.numel() for p in model.parameters()):,}")

    use_dp = n_gpus > 1
    if use_dp:
        torch.backends.cudnn.benchmark = True
        model = nn.DataParallel(model)
        logger.info(
            f"DataParallel active across {n_gpus} GPUs; effective per-GPU batch = {args.batch_size}"
        )

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=total_steps // 10, num_training_steps=total_steps
    )
    scaler = torch.amp.GradScaler("cuda") if DEVICE.type == "cuda" else None
    loss_fn = nn.CrossEntropyLoss()

    best_f1 = 0.0
    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch + 1}/{args.epochs}")
        for batch in pbar:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels_batch = batch["labels"].to(DEVICE)

            if scaler:
                with torch.amp.autocast(device_type="cuda"):
                    outputs = model(input_ids, attention_mask=attention_mask)
                    loss = loss_fn(outputs.logits, labels_batch)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                outputs = model(input_ids, attention_mask=attention_mask)
                loss = loss_fn(outputs.logits, labels_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            scheduler.step()
            train_loss += loss.item()
            pbar.set_postfix({"loss": f"{loss.item():.4f}"})

        val_metrics = evaluate(model, val_loader)
        f1 = val_metrics["macro_f1"]
        logger.info(
            f"Epoch {epoch + 1}: loss={train_loss / len(train_loader):.4f}, "
            f"val_acc={val_metrics['accuracy']:.4f}, val_macro_f1={f1:.4f}"
        )
        if f1 > best_f1:
            best_f1 = f1
            logger.info(f"New best macro F1: {f1:.4f}. Saving checkpoint...")
            save_model = model.module if isinstance(model, nn.DataParallel) else model
            save_model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
            with open(output_dir / "labels.json", "w") as f:
                json.dump(LABEL_NAMES, f, indent=2)

    logger.info("=== Final evaluation (best checkpoint) ===")
    best_model = AutoModelForSequenceClassification.from_pretrained(str(output_dir)).to(DEVICE)
    for name, loader, labels in (
        ("train", train_loader, y_train),
        ("val", val_loader, y_val),
        ("test", test_loader, y_test),
    ):
        m = evaluate(best_model, loader)
        report = classification_report(
            m["labels"], m["preds"], target_names=list(LABEL_NAMES.values()), zero_division=0, digits=3
        )
        logger.info(f"--- {name} (n={len(labels)}) ---\n{report}")

    if args.export_onnx:
        try:
            export_onnx(best_model, tokenizer, output_dir)
        except Exception as e:  # pragma: no cover - export is best-effort
            logger.warning(f"ONNX export failed (non-fatal): {e}")

    logger.info(f"Training complete. Best val macro F1: {best_f1:.4f}")
    return float(best_f1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Stage 1 binary argument gate on stage1_splits.")
    parser.add_argument("--data", default="data/stage1_splits.json")
    parser.add_argument("--output-dir", default="models/stage1_v13_classifier")
    parser.add_argument("--base-model", default="distilbert-base-uncased")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--export-onnx", action="store_true", default=True)
    args = parser.parse_args()
    train(args)
