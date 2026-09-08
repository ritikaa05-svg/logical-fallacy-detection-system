import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def run_diagnostics():
    print("--- 7. DATASET SCAN ---")
    data_path = Path("data/unified_training_data.json")
    with open(data_path) as f:
        data = json.load(f)

    label_list = sorted(list(set(d["fallacy"] for d in data)))
    label2id = {l: i for i, l in enumerate(label_list)}

    print("--- 5. LABEL->ID MAPPING ---")
    print(json.dumps(label2id, indent=2))

    print("--- 4. NUM_LABELS VERIFICATION ---")
    print(f"Derived Label Count: {len(label_list)}")

    print("--- 6. CONTIGUOUS CHECK ---")
    ids = sorted(label2id.values())
    is_contiguous = ids == list(range(len(ids)))
    print(f"IDs are contiguous 0 to N-1: {is_contiguous}")

    null_text = 0
    empty_text = 0
    missing_label = 0
    invalid_label = 0

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

    labels_in_data = []
    for i, d in enumerate(data):
        text = d.get("text")
        label = d.get("fallacy")

        if text is None:
            null_text += 1
        elif not str(text).strip():
            empty_text += 1

        if not label:
            missing_label += 1
        elif label not in TAXONOMY:
            invalid_label += 1

        labels_in_data.append(label2id.get(label))

    print(f"Null text: {null_text}")
    print(f"Empty text: {empty_text}")
    print(f"Missing labels: {missing_label}")
    print(f"Invalid labels: {invalid_label}")

    print("--- 2. CLASS WEIGHTS ---")
    label_counts = np.bincount(labels_in_data)
    weights = 1.0 / (label_counts + 1e-6)
    weights = weights / weights.sum() * len(label_list)
    print(f"Weights: {weights}")

    print("--- 3. WEIGHT VERIFICATION ---")
    print(f"Any NaN: {np.isnan(weights).any()}")
    print(f"Any Inf: {np.isinf(weights).any()}")
    print(f"Any Negative: {(weights < 0).any()}")
    print(f"Any Zero: {(weights == 0).any()}")

    print("--- 8. TOKENIZER NAN CHECK ---")
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    sample_text = data[0]["text"]
    encoding = tokenizer(sample_text, return_tensors="pt")
    print(f"Input IDs contains NaN: {torch.isnan(encoding['input_ids'].float()).any()}")
    print(f"Attention Mask contains NaN: {torch.isnan(encoding['attention_mask'].float()).any()}")

    print("--- 9. FORWARD PASS ---")
    model = AutoModelForSequenceClassification.from_pretrained("distilbert-base-uncased", num_labels=len(label_list))
    model.eval()

    # Batch of size 1
    input_ids = encoding["input_ids"]
    attention_mask = encoding["attention_mask"]
    target_label = torch.tensor([labels_in_data[0]], dtype=torch.long)

    with torch.no_grad():
        outputs = model(input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float))
        loss = loss_fn(logits, target_label)

    print(f"Logits min: {logits.min().item()}")
    print(f"Logits max: {logits.max().item()}")
    print(f"Loss: {loss.item()}")
    print(f"Label IDs: {target_label.tolist()}")

    print("--- 10. IDENTIFY FIRST NAN ---")
    if torch.isnan(logits).any():
        print("Logits contain NaN")
    elif torch.isnan(loss).any():
        print("Loss is NaN")
    else:
        print("No NaN found in diagnostic single pass.")


if __name__ == "__main__":
    run_diagnostics()
