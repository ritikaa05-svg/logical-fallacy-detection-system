import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def audit():
    print("--- 1. AUDIT DATASET ---")
    data_path = "data/unified_training_data.json"
    if not Path(data_path).exists():
        print(f"Error: {data_path} not found.")
        return

    with open(data_path) as f:
        data = json.load(f)

    null_texts = 0
    empty_texts = 0
    missing_labels = 0
    invalid_labels = 0

    TAXONOMY = {
        "ad_hominem",
        "affirming_consequent",
        "appeal_to_authority",
        "appeal_to_emotion",
        "appeal_to_nature",
        "appeal_to_tradition",
        "bandwagon",
        "begging_the_question",
        "composition",
        "denying_antecedent",
        "division",
        "equivocation",
        "factual_statement",
        "false_cause",
        "false_dilemma",
        "hasty_generalization",
        "moving_goalposts",
        "no_true_scotsman",
        "red_herring",
        "slippery_slope",
        "straw_man",
        "tu_quoque",
        "tu_quoque_contextual",
        "valid_reasoning",
    }

    for i, d in enumerate(data):
        text = d.get("text")
        fallacy = d.get("fallacy")

        if text is None:
            null_texts += 1
        elif not str(text).strip():
            empty_texts += 1

        if fallacy is None:
            missing_labels += 1
        elif fallacy not in TAXONOMY:
            invalid_labels += 1

    print(f"Total samples: {len(data)}")
    print(f"Null texts: {null_texts}")
    print(f"Empty texts: {empty_texts}")
    print(f"Missing labels: {missing_labels}")
    print(f"Invalid labels: {invalid_labels}")

    print("\n--- 4-6. LABEL VALIDATION ---")
    label_list = sorted(list(set(d["fallacy"] for d in data if d.get("fallacy"))))
    label2id = {l: i for i, l in enumerate(label_list)}
    print(f"Label list length: {len(label_list)}")
    print(f"Label->ID Mapping: {json.dumps(label2id, indent=2)}")

    labels = [label2id[d["fallacy"]] for d in data if d.get("fallacy")]
    ids = sorted(list(set(labels)))
    is_contiguous = ids == list(range(len(ids)))
    print(f"Contiguous check (0 to N-1): {is_contiguous}")

    print("\n--- 2-3. CLASS WEIGHTS VALIDATION ---")
    label_counts = np.bincount(labels)
    print(f"Label counts: {label_counts}")

    weights = 1.0 / (label_counts + 1e-6)
    weights = weights / weights.sum() * len(label_list)
    print(f"Exact class weights: {weights}")

    print(f"Any NaN weights: {np.isnan(weights).any()}")
    print(f"Any Inf weights: {np.isinf(weights).any()}")
    print(f"Any Negative weights: {(weights < 0).any()}")
    print(f"Any Zero weights: {(weights == 0).any()}")

    print("\n--- 8-10. TOKENIZER & FORWARD PASS ---")
    MODEL_NAME = "microsoft/deberta-v3-small"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    # Check first 5 samples for tokenizer NaNs
    nan_found_in_tokenizer = False
    for i in range(5):
        encoding = tokenizer(data[i]["text"], return_tensors="pt")
        for k, v in encoding.items():
            if torch.isnan(v.float()).any():
                print(f"NaN found in tokenizer output '{k}' for sample {i}")
                nan_found_in_tokenizer = True
    if not nan_found_in_tokenizer:
        print("No NaN found in first 5 tokenizer outputs.")

    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=len(label_list))
    model.eval()

    # Create a single batch
    batch_text = [data[0]["text"]]
    batch_labels = torch.tensor([label2id[data[0]["fallacy"]]], dtype=torch.long)
    inputs = tokenizer(batch_text, return_tensors="pt", padding=True, truncation=True)

    print(f"Label IDs: {batch_labels.tolist()}")

    with torch.no_grad():
        print("Executing forward pass...")
        outputs = model(**inputs)
        logits = outputs.logits
        print(f"Logits min: {logits.min().item()}")
        print(f"Logits max: {logits.max().item()}")

        loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float))
        loss = loss_fn(logits, batch_labels)
        print(f"Loss value: {loss.item()}")

        if torch.isnan(logits).any():
            print("FIRST NAN DETECTED: Logits contain NaN")
        elif torch.isnan(loss):
            print("FIRST NAN DETECTED: Loss is NaN")
        else:
            print("No NaN detected in single forward pass.")


if __name__ == "__main__":
    audit()
