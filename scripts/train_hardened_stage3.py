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
logger.info(f"Using device: {DEVICE}")


def load_data(path):
    with open(path) as f:
        data = json.load(f)
    texts = [d["text"] for d in data]
    label_list = sorted(list(set(d["fallacy"] for d in data)))
    label2id = {l: i for i, l in enumerate(label_list)}
    id2label = {i: l for l, i in label2id.items()}
    labels = [label2id[d["fallacy"]] for d in data]
    return texts, labels, label_list, id2label, label2id


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


def train():
    data_path = Path("data/unified_training_data_v1.1.json")
    if not data_path.exists():
        alt = Path("unified_training_data_v1.1.json")
        if alt.exists():
            data_path = alt
        else:
            logger.error(f"Training data not found at {data_path}")
            logger.error("Upload unified_training_data_v1.1.json to the working directory.")
            return

    output_dir = Path("models/new/stage3_fine_classifier")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading data from {data_path}...")
    texts, labels, label_list, id2label, label2id = load_data(data_path)
    logger.info(f"Loaded {len(texts)} samples, {len(label_list)} classes.")

    model_name = "microsoft/deberta-v3-small"
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    X_train, X_val, y_train, y_val = train_test_split(texts, labels, test_size=0.1, random_state=42, stratify=labels)

    train_ds = FallacyDataset(X_train, y_train, tokenizer)
    val_ds = FallacyDataset(X_val, y_val, tokenizer)

    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32)

    label_counts = np.bincount(labels)
    weights = 1.0 / (np.sqrt(label_counts) + 1e-6)
    weights = weights / weights.sum() * len(label_list)
    class_weights = torch.tensor(weights, dtype=torch.float).to(DEVICE)
    logger.info(f"Weight imbalance ratio (max/min): {weights.max() / weights.min():.2f}:1")

    config = AutoConfig.from_pretrained(model_name)
    config.num_labels = len(label_list)
    config.id2label = id2label
    config.label2id = label2id
    config.output_hidden_states = True

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        config=config,
        torch_dtype=torch.float32,
        ignore_mismatched_sizes=True,
    ).to(DEVICE)
    logger.info(f"Model params: {sum(p.numel() for p in model.parameters()):,}")

    epochs = 6
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=total_steps // 10, num_training_steps=total_steps
    )
    scaler = torch.amp.GradScaler("cuda") if DEVICE.type == "cuda" else None
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)

    best_f1 = 0.0

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch + 1}/{epochs}")

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
        logger.info(f"\n{classification_report(all_labels, all_preds, target_names=label_list, zero_division=0)}")

        if f1 > best_f1:
            best_f1 = f1
            logger.info(f"New best F1: {f1:.4f}. Saving model...")
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
            with open(output_dir / "labels.json", "w") as f:
                json.dump(label_list, f)

    logger.info(f"Training complete. Best macro F1: {best_f1:.4f}")

    model_size = sum(f.stat().st_size for f in output_dir.glob("*") if f.is_file())
    logger.info(f"Model folder size: {model_size / (1024**2):.2f} MB")
    if model_size < 50 * 1024 * 1024:
        logger.error("Model size unusually small (<50MB). Something may be wrong.")
    else:
        zip_path = shutil.make_archive(str(output_dir.parent / "stage3_fine_classifier"), "zip", output_dir)
        logger.info(f"Package ready: {zip_path}")

    export_onnx(model, tokenizer, output_dir, label_list)


def export_onnx(model, tokenizer, output_dir, label_list):
    logger.info("Exporting to ONNX...")
    model.eval()
    device = next(model.parameters()).device

    dummy = tokenizer(
        "test input",
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=256,
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
    onnx_size = onnx_path.stat().st_size
    logger.info(f"ONNX export complete: {onnx_path.name} ({onnx_size / (1024**2):.1f} MB)")

    if onnx_size < 50 * 1024 * 1024:
        external_data = list(output_dir.glob("*.onnx.data"))
        if external_data:
            total = onnx_size + sum(f.stat().st_size for f in external_data)
            logger.info(f"External data files found. Total ONNX size: {total / (1024**2):.1f} MB")
        else:
            logger.warning(
                f"ONNX file is only {onnx_size / (1024**2):.1f} MB. Weights may not be embedded. Use the PyTorch model for inference."
            )

    with open(output_dir / "model_config_onnx.json", "w") as f:
        json.dump({"fine_labels": label_list, "num_labels": len(label_list)}, f, indent=2)


if __name__ == "__main__":
    train()
