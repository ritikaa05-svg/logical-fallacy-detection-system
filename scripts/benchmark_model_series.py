"""Old-vs-new model series benchmark for the defense record.

Compares the retired model generation (stage1_v12, stage3_v12, phase4_final_model)
against the current deployment (stage1_v13_classifier, stage3_v13_classifier) on
the standardized splits used throughout the evaluation:

  - Stage 1 (binary): data/stage1_splits.json val split (n=1,155)
  - Stage 2/3 (29 classes): stratified 90/10 split of v1.3, seed 42 (n=1,695),
    identical to scripts/eval_zero_shot.py
  - Phase 4 (24 classes): same seed-42 val split filtered to the 24 labels that
    phase4_final_model supports (excludes the 5 rescued formal classes); the
    current 29-class model is evaluated on the SAME subset for a fair comparison.

Run BEFORE deleting the legacy models so the statistics can be archived in
docs/MODEL_COMPARISON.md.

Usage:
    venv/bin/python scripts/benchmark_model_series.py
"""
import json
import time
from pathlib import Path

import torch
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
RESULTS_PATH = ROOT / "results" / "model_series_benchmark.json"

MODELS = {
    "stage1_old": ROOT / "models" / "stage1_v12",
    "stage1_new": ROOT / "models" / "stage1_v13_classifier",
    "stage23_old": ROOT / "models" / "stage3_v12",
    "stage23_new": ROOT / "models" / "stage3_v13_classifier",
    "phase4_old": ROOT / "models" / "phase4_final_model",
}


def load_split(seed):
    with open(ROOT / "data" / "unified_training_data_v1.3.json") as f:
        data = json.load(f)
    labeled = [d for d in data if "fallacy" in d]
    texts = [d["text"] for d in labeled]
    label_list = sorted({d["fallacy"] for d in labeled})
    labels = [label_list.index(d["fallacy"]) for d in labeled]
    _, X_val, _, y_val = train_test_split(
        texts, labels, test_size=0.1, random_state=seed, stratify=labels
    )
    return X_val, y_val, label_list


def load_stage1_val():
    with open(ROOT / "data" / "stage1_splits.json") as f:
        splits = json.load(f)
    return [d["text"] for d in splits["val"]], [d["label"] for d in splits["val"]]


def predict_model(model_path, texts, max_length, batch_size=32):
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path), local_files_only=True
    ).to(DEVICE)
    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = tokenizer(
                batch, truncation=True, padding=True, max_length=max_length, return_tensors="pt"
            )
            enc = {k: v.to(DEVICE) for k, v in enc.items()}
            logits = model(**enc).logits
            preds.extend(torch.argmax(logits, dim=1).cpu().tolist())
    del model
    torch.cuda.empty_cache() if DEVICE.type == "cuda" else None
    return preds


def map_preds_to_label_list(preds, config, label_list):
    id2label = config["id2label"] if "id2label" in config else {
        str(i): str(i) for i in range(int(config.get("num_labels", 2)))
    }
    names_true = set(label_list)
    return [
        (n if (n := id2label.get(str(p), str(p))) in names_true else "__other__")
        for p in preds
    ]


def evaluate(path, texts, labels, label_names, max_length, name):
    t0 = time.time()
    preds = predict_model(path, texts, max_length)
    if label_names is not None:
        preds = map_preds_to_label_list(preds, json.loads(Path(path, "config.json").read_text()), label_names)
    f1 = f1_score(labels, preds, average="macro", zero_division=0)
    acc = accuracy_score(labels, preds)
    print(f"  {name:16s} macro-F1={f1:.4f} acc={acc:.4f}  ({time.time()-t0:.0f}s)")
    return round(f1, 4), round(acc, 4)


def main():
    missing = [k for k, p in MODELS.items() if not (p / "config.json").exists()]
    if missing:
        print(
            "Legacy models already retired: " + ", ".join(missing)
            + "\nThis script is the pre-retirement record — results are archived in"
            " results/model_series_benchmark.json and docs/MODEL_COMPARISON.md."
        )
        raise SystemExit(1)
    out = {"device": str(DEVICE), "date": time.strftime("%Y-%m-%d"), "results": {}}
    print(f"device: {DEVICE}")

    print("\n=== Stage 1 (binary gate, val n=1,155) ===")
    texts, labels = load_stage1_val()
    out["stage1_val"] = {"samples": len(texts)}
    for key, label in [("old_stage1_v12", "stage1_old"), ("new_stage1_v13", "stage1_new")]:
        f1v, acc = evaluate(MODELS[label], texts, labels, None, 512, key)
        out["stage1_val"][key] = {"macro_f1": f1v, "accuracy": acc}

    print("\n=== Stage 2/3 (29 classes, seed-42 val n=1,695) ===")
    X_val, y_val, label_list = load_split(42)
    y_val_names = [label_list[i] for i in y_val]
    out["stage23_val"] = {"samples": len(X_val), "n_classes": len(label_list)}
    for key, label in [("old_stage3_v12", "stage23_old"), ("new_stage3_v13", "stage23_new")]:
        f1v, acc = evaluate(MODELS[label], X_val, y_val_names, label_list, 256, key)
        out["stage23_val"][key] = {"macro_f1": f1v, "accuracy": acc}

    print("\n=== Phase 4 comparison (24 shared classes, same seed-42 val) ===")
    p4 = json.loads((MODELS["phase4_old"] / "config.json").read_text())
    p4_labels = sorted(p4["id2label"].values())
    keep_rows = [r for r, v in enumerate(y_val) if label_list[v] in p4_labels]
    X_sub = [X_val[r] for r in keep_rows]
    y_sub = [label_list[y_val[r]] for r in keep_rows]
    sub_list = sorted(p4_labels)
    out["phase4_subset"] = {
        "samples": len(X_sub), "n_classes": len(sub_list),
        "excluded_formal_classes": sorted(set(label_list) - set(p4_labels)),
    }
    for key, label in [("old_phase4_24", "phase4_old"), ("new_stage3_v13", "stage23_new")]:
        f1v, acc = evaluate(MODELS[label], X_sub, y_sub, sub_list, 256, key)
        out["phase4_subset"][key] = {"macro_f1": f1v, "accuracy": acc}

    s1 = out["stage1_val"]; s23 = out["stage23_val"]; p4s = out["phase4_subset"]
    ok = (
        s1["new_stage1_v13"]["macro_f1"] >= s1["old_stage1_v12"]["macro_f1"]
        and s23["new_stage3_v13"]["macro_f1"] >= s23["old_stage3_v12"]["macro_f1"]
        and p4s["new_stage3_v13"]["macro_f1"] >= p4s["old_phase4_24"]["macro_f1"]
    )
    out["verification"] = {"new_beats_old": ok}
    print(f"\nVERIFICATION (new >= old in all three comparisons): {'PASS' if ok else 'FAIL'}")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved {RESULTS_PATH}")


if __name__ == "__main__":
    main()
