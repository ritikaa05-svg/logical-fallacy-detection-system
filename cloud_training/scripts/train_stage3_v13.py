"""
Train Stage 3: 29-Class Fine-Grained Fallacy Classifier on the v1.3 dataset.

Runs on Kaggle (T4/P100 GPU) or locally. Key differences vs the legacy
train_stage3.py / train_hardened_stage3.py:

- Reads `data/unified_training_data_v1.3.json` (17,938 samples).
- Filters out the 996 near-miss hard-negative samples (schema lacks the
  `fallacy` key; those belong to the Stage 1 gatekeeper, not the Stage 3
  fine head) -> 16,942 labeled samples across 29 classes.
- Base model matches production (`microsoft/deberta-v3-small`, single-head,
  same architecture as `models/phase4_final_model`).
- sqrt-inverse-frequency class weighting (1/sqrt(count), renormalized).
- Per-class classification report with formal classes highlighted so the
  Phase 8 #5/#8 validation is a one-glance check.
- Multi-GPU via `nn.DataParallel` when >1 CUDA device is visible; the loader
  batch is auto-scaled (batch_size x n_gpus) so the effective batch per GPU
  stays at `--batch-size`.

Usage:
    python cloud_training/scripts/train_stage3_v13.py --data data/unified_training_data_v1.3.json
    # Kaggle T4x2 (16/GPU): --batch-size 16
"""
import argparse
import json
import logging
import shutil
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
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
FORMAL_CLASSES = {
    "affirming_consequent",
    "denying_antecedent",
    "undistributed_middle",
    "illicit_major",
    "illicit_minor",
    "exclusive_premises",
    "existential_fallacy",
}


class FallacyDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=256):
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
    """Load v1.3 JSON, keep only samples with a `fallacy` label."""
    with open(path) as f:
        data = json.load(f)

    labeled = [d for d in data if "fallacy" in d]
    dropped = len(data) - len(labeled)
    if dropped:
        logger.info(f"Dropped {dropped} unlabeled near-miss samples (Stage 1 data).")

    texts = [d["text"] for d in labeled]
    label_list = sorted(set(d["fallacy"] for d in labeled))
    label2id = {l: i for i, l in enumerate(label_list)}
    labels = [label2id[d["fallacy"]] for d in labeled]
    return texts, labels, label_list


def compute_class_weights(labels: list[int], num_labels: int) -> torch.Tensor:
    counts = np.bincount(labels, minlength=num_labels)
    weights = 1.0 / (np.sqrt(counts) + 1e-6)
    weights = weights / weights.sum() * num_labels
    logger.info(f"Class imbalance ratio (max/min count): {counts.max() / counts.min():.1f}:1")
    return torch.tensor(weights, dtype=torch.float).to(DEVICE)


def train(args):
    logger.info(f"Using device: {DEVICE} ({torch.cuda.get_device_name(0) if DEVICE.type == 'cuda' else 'cpu'})")

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Training data not found at {data_path}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    texts, labels, label_list = load_data(data_path)
    num_labels = len(label_list)
    logger.info(f"Loaded {len(texts)} samples across {num_labels} classes.")

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    X_train, X_val, y_train, y_val = train_test_split(
        texts, labels, test_size=args.val_split, random_state=args.seed, stratify=labels
    )
    logger.info(f"Train: {len(X_train)} / Val: {len(X_val)}")

    model_name = args.base_model
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    train_ds = FallacyDataset(X_train, y_train, tokenizer, max_length=args.max_length)
    val_ds = FallacyDataset(X_val, y_val, tokenizer, max_length=args.max_length)

    n_gpus = torch.cuda.device_count() if DEVICE.type == "cuda" else 0
    loader_batch = args.batch_size * n_gpus if n_gpus > 1 else args.batch_size
    train_loader = DataLoader(train_ds, batch_size=loader_batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=loader_batch * 2)

    class_weights = compute_class_weights(y_train, num_labels)

    config = AutoConfig.from_pretrained(model_name)
    config.num_labels = num_labels
    config.id2label = {i: l for i, l in enumerate(label_list)}
    config.label2id = {l: i for i, l in enumerate(label_list)}
    config.output_hidden_states = True

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, config=config, torch_dtype=torch.float32, ignore_mismatched_sizes=True
    ).to(DEVICE)
    logger.info(f"Model params: {sum(p.numel() for p in model.parameters()):,}")

    n_gpus = torch.cuda.device_count() if DEVICE.type == "cuda" else 0
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
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)

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

        model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                outputs = model(
                    batch["input_ids"].to(DEVICE),
                    attention_mask=batch["attention_mask"].to(DEVICE),
                )
                preds = torch.argmax(outputs.logits, dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(batch["labels"].numpy())

        f1 = f1_score(all_labels, all_preds, average="macro")
        logger.info(f"\nEpoch {epoch + 1}: loss={train_loss / len(train_loader):.4f}, val_macro_f1={f1:.4f}")
        print(classification_report(all_labels, all_preds, target_names=label_list, zero_division=0, digits=3))

        formal = [l for l in label_list if l in FORMAL_CLASSES]
        if formal:
            formal_f1s = {
                l: f1_score(
                    [1 if y == label_list.index(l) else 0 for y in all_labels],
                    [1 if p == label_list.index(l) else 0 for p in all_preds],
                    zero_division=0,
                )
                for l in formal
            }
            logger.info(f"Formal-class F1: {formal_f1s}")

        if f1 > best_f1:
            best_f1 = f1
            logger.info(f"New best F1: {f1:.4f}. Saving model...")
            save_model = model.module if isinstance(model, nn.DataParallel) else model
            save_model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
            with open(output_dir / "labels.json", "w") as f:
                json.dump(label_list, f, indent=2)

    logger.info(f"Training complete. Best macro F1: {best_f1:.4f}")

    model_size = sum(f.stat().st_size for f in output_dir.glob("*") if f.is_file())
    logger.info(f"Model folder size: {model_size / (1024**2):.2f} MB")
    if args.export_onnx:
        try:
            export_onnx(save_model, tokenizer, output_dir, label_list)
        except Exception as e:  # pragma: no cover - export is best-effort
            logger.warning(f"ONNX export failed (non-fatal): {e}")

    return best_f1


def export_onnx(model, tokenizer, output_dir, label_list):
    logger.info("Exporting to ONNX...")
    model.eval()
    device = next(model.parameters()).device

    dummy = tokenizer(
        "test input", return_tensors="pt", padding="max_length", truncation=True, max_length=256
    )
    dummy_ids = dummy["input_ids"].to(device)
    dummy_mask = dummy["attention_mask"].to(device)

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
        json.dump({"fine_labels": label_list, "num_labels": len(label_list)}, f, indent=2)

    zip_path = shutil.make_archive(str(output_dir.parent / output_dir.name), "zip", output_dir)
    logger.info(f"Package ready: {zip_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Stage 3 fine classifier on v1.3 dataset.")
    parser.add_argument("--data", default="data/unified_training_data_v1.3.json")
    parser.add_argument("--output-dir", default="models/stage3_v13_classifier")
    parser.add_argument("--base-model", default="microsoft/deberta-v3-small")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=16, help="effective per-GPU batch (loader batch = batch_size x n_gpus under DataParallel)")
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--export-onnx", action="store_true", default=True)
    args = parser.parse_args()
    train(args)
