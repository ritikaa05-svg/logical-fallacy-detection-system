"""
Train Stage 1: Binary Argument/Non-Argument Classifier
Uses DistilBERT (lightweight) on CPU with gradient accumulation.
"""
import json
import logging
import os
from pathlib import Path

import torch
from sklearn.metrics import accuracy_score, f1_score
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

# Force CPU to avoid OOM
os.environ["CUDA_VISIBLE_DEVICES"] = ""
DEVICE = torch.device("cpu")

class ArgumentDataset(Dataset):
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
        raw_data = json.load(f)

    texts, labels = [], []
    for item in raw_data:
        text = item.get("text", "")
        if text and len(text.split()) >= 3:
            texts.append(text)
            # Binary: 0 if no fallacy, 1 if any fallacy detected
            # In unified data, everything has a fallacy label,
            # so we need to ensure we have non-fallacy samples.
            labels.append(1)

    # Generate negatives from prefixes/truncated logic if no 'none' class exists
    logger.info(f"Loaded {len(texts)} positives. Generating negatives...")
    neg = []
    for t in texts[:len(texts)//2]:
        words = t.split()
        if len(words) > 5:
            # Create a 'non-argument' fragment
            neg.append((" ".join(words[:len(words)//4]), 0))

    texts_final = texts + [t for t, l in neg]
    labels_final = labels + [l for t, l in neg]

    logger.info(f"Balanced dataset: {sum(labels_final)} arguments, {len(labels_final)-sum(labels_final)} non-arguments")

    X_train, X_val, y_train, y_val = train_test_split(
        texts_final, labels_final, test_size=0.2, random_state=42, stratify=labels_final
    )
    return X_train, X_val, y_train, y_val


def train():
    logger.info(f"Using device: {DEVICE}")

    X_train, X_val, y_train, y_val = load_data()

    # Use lightweight DistilBERT
    model_name = "distilbert-base-uncased"
    logger.info(f"Loading: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2).to(DEVICE)

    train_ds = ArgumentDataset(X_train, y_train, tokenizer)
    val_ds = ArgumentDataset(X_val, y_val, tokenizer)

    # Small batch size for CPU
    train_loader = DataLoader(train_ds, batch_size=4, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=8, num_workers=2)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-5)

    # Train only 2 epochs on CPU to keep it fast
    EPOCHS = 2
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=total_steps // 10, num_training_steps=total_steps
    )

    best_f1 = 0
    accumulation_steps = 4  # Simulate batch_size=16

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        optimizer.zero_grad()

        progress = tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS}")
        for i, batch in enumerate(progress):
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels = batch["label"].to(DEVICE)

            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss / accumulation_steps
            loss.backward()

            if (i + 1) % accumulation_steps == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

            total_loss += loss.item() * accumulation_steps
            progress.set_postfix({"loss": f"{loss.item()*accumulation_steps:.4f}"})

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

        f1 = f1_score(all_labels, all_preds, average="binary")
        acc = accuracy_score(all_labels, all_preds)
        logger.info(f"Epoch {epoch+1} val: f1={f1:.4f}, acc={acc:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            Path("models/stage1_gatekeeper").mkdir(parents=True, exist_ok=True)
            model.save_pretrained("models/stage1_gatekeeper")
            tokenizer.save_pretrained("models/stage1_gatekeeper")
            logger.info(f"✅ Saved model (f1={f1:.4f})")

    logger.info(f"Training complete. Best F1: {best_f1:.4f}")


if __name__ == "__main__":
    train()
