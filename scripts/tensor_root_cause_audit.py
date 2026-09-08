import json

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer


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
            self.texts[idx], truncation=True, padding="max_length", max_length=self.max_length, return_tensors="pt"
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
            "idx": idx,
        }


def run_audit():
    device = torch.device("cpu")
    DATA_PATH = "data/unified_training_data.json"
    with open(DATA_PATH) as f:
        data = json.load(f)

    label_list = sorted(list(set(d["fallacy"] for d in data)))
    label2id = {l: i for i, l in enumerate(label_list)}
    labels = [label2id[d["fallacy"]] for d in data]

    label_counts = np.bincount(labels)
    weights = 1.0 / (label_counts + 1e-6)
    weights = weights / weights.sum() * len(label_list)
    class_weights = torch.tensor(weights, dtype=torch.float32)

    MODEL_NAME = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(label_list), low_cpu_mem_usage=True
    )

    loss_fn = nn.CrossEntropyLoss(weight=class_weights)
    dataset = FallacyDataset([d["text"] for d in data], labels, tokenizer)
    # Use larger batch to speed up scan, but small enough to avoid OOM
    dataloader = DataLoader(dataset, batch_size=8, shuffle=False)

    print("Scanning dataset for gradient/loss NaNs...")

    first_nan = {"found": False}

    for batch in tqdm(dataloader):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        target_labels = batch["label"].to(device)

        # We need gradients to check for explosion
        model.zero_grad()
        outputs = model(input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        loss = loss_fn(logits, target_labels)

        if torch.isnan(loss):
            print("\n--- NAN LOSS DETECTED ---")
            print(f"Batch indices: {batch['idx'].tolist()}")
            print(f"Labels: {target_labels.tolist()}")
            first_nan["found"] = True
            break

        loss.backward()

        # Check gradients
        for name, param in model.named_parameters():
            if param.grad is not None and (torch.isnan(param.grad).any() or torch.isinf(param.grad).any()):
                print("\n--- NAN GRADIENT DETECTED ---")
                print(f"Parameter: {name}")
                print(f"Batch indices: {batch['idx'].tolist()}")
                print(f"Labels: {target_labels.tolist()}")
                print(f"Class weights for these labels: {[weights[l].item() for l in target_labels]}")
                first_nan["found"] = True
                break

        if first_nan["found"]:
            break

    if not first_nan["found"]:
        print("\nSUCCESS: No NaNs found in one full epoch pass (without weight updates).")
        print("This implies NaN is caused by the ACCUMULATED WEIGHT UPDATES (Learning Rate).")


if __name__ == "__main__":
    run_audit()
