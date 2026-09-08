import asyncio
import json

from sklearn.metrics import classification_report

from backend.app.services.unified_classifier import unified_classifier


async def eval_audit():
    # 1. Load Data
    with open("data/unified_training_data.json") as f:
        data = json.load(f)

    # Stratified-like sampling for audit (sample 20 per class if possible, total ~400)
    audit_data = []
    classes = sorted(list(set(d["fallacy"] for d in data)))
    for c in classes:
        c_samples = [d for d in data if d["fallacy"] == c]
        audit_data.extend(c_samples[:20])

    print(f"--- EVALUATION AUDIT ({len(audit_data)} samples) ---")

    y_true = [d["fallacy"] for d in audit_data]
    y_pred = []

    # 2. Predict using current model
    for i, item in enumerate(audit_data):
        if i % 50 == 0:
            print(f"Processing {i}...")
        # Use predict directly to bypass orchestrator logic and get Stage 3 only
        res = unified_classifier.predict(item["text"])
        if res.get("fine_labels"):
            y_pred.append(res["fine_labels"][0])
        else:
            y_pred.append("unknown")

    # 3. Report
    # Note: Current model only knows 20 classes, so it WILL fail on the 2 new ones.
    print("\n--- PER-CLASS PERFORMANCE ---")
    print(classification_report(y_true, y_pred, zero_division=0))


if __name__ == "__main__":
    # Ensure it uses the real model if available, else fallback
    # We want to see how the deployed model behaves
    asyncio.run(eval_audit())
