"""
Train Stage 3: 22-Class Fine-Grained Fallacy Classifier
Uses DeBERTa-v3-XSmall for high accuracy with low CPU latency.
Supports focal loss for handling significant class imbalance.
"""
import json
import logging
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use GPU if available, else CPU
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class FallacyDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=256):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx], truncation=True, padding="max_length",
            max_length=self.max_length, return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
        }

def load_data():
    data_path = Path("data/unified_training_data.json")
    if not data_path.exists():
        raise FileNotFoundError("Run scripts/merge_training_data.py first")

    with open(data_path) as f:
        data = json.load(f)

    texts = [d["text"] for d in data]
    # Dynamically derive labels
    label_list = sorted(list(set(d["fallacy"] for d in data)))
    label2id = {l: i for i, l in enumerate(label_list)}
    labels = [label2id[d["fallacy"]] for d in data]

    # Calculate class weights for imbalance handling
    label_counts = np.bincount(labels)
    weights = 1.0 / (label_counts + 1e-6)
    weights = weights / weights.sum() * len(label_list)
    class_weights = torch.tensor(weights, dtype=torch.float).to(DEVICE)

    logger.info(f"Loaded {len(texts)} samples across {len(label_list)} classes.")
    logger.info(f"Class weights computed: {weights[:5]}...")

    X_train, X_val, y_train, y_val = train_test_split(
        texts, labels, test_size=0.15, random_state=42, stratify=labels
    )
    return X_train, X_val, y_train, y_val, label_list, class_weights

def train():
    logger.info(f"Using device: {DEVICE}")

    X_train, X_val, y_train, y_val, label_list, class_weights = load_data()
    num_labels = len(label_list)

    # Model: DistilBERT (Fast, robust, and widely available)
    model_name = "distilbert-base-uncased"
    logger.info(f"Loading: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_labels).to(DEVICE)

    train_ds = FallacyDataset(X_train, y_train, tokenizer)
    val_ds = FallacyDataset(X_val, y_val, tokenizer)

    batch_size = 8 if DEVICE.type == "cpu" else 32
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size * 2)

    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5, weight_decay=0.01)

    # Use Weighted CrossEntropy for imbalance
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)

    EPOCHS = 3
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=total_steps // 10, num_training_steps=total_steps
    )

    best_f1 = 0

    for epoch in range(EPOCHS):
        model.train()
        progress = tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS}")
        for batch in progress:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels = batch["label"].to(DEVICE)

            outputs = model(input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            loss = loss_fn(logits, labels)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            progress.set_postfix({"loss": f"{loss.item():.4f}"})

        # Validation
        model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                outputs = model(
                    batch["input_ids"].to(DEVICE),
                    attention_mask=batch["attention_mask"].to(DEVICE),
                )
                preds = torch.argmax(outputs.logits, dim=1).cpu()
                all_preds.extend(preds.numpy())
                all_labels.extend(batch["label"].numpy())

        f1 = f1_score(all_labels, all_preds, average="macro")
        logger.info(f"Epoch {epoch+1} val macro-F1: {f1:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            save_path = Path("models/stage3_production_fallacy")
            save_path.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(save_path)
            tokenizer.save_pretrained(save_path)
            # Save class list
            with open(save_path / "labels.json", "w") as f:
                json.dump(label_list, f)
            logger.info(f"✅ Saved best model (F1={f1:.4f})")

    logger.info(f"Training complete. Best Macro-F1: {best_f1:.4f}")

if __name__ == "__main__":
    train()
