import asyncio
import json
import os
import sys

from sklearn.metrics import classification_report

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.services.unified_classifier import unified_classifier
from backend.app.services.z3_service import z3_service

TARGET_FALLACIES = [
    "affirming_consequent",
    "denying_antecedent",
    "begging_the_question",
    "false_cause",
    "valid_reasoning",
    "factual_statement",
]


async def evaluate_phase_4_1():
    print("🚀 Starting Phase 4.1 Evaluation (Robustness & Integrity)...")

    # 1. Load Data
    with open("data/phase4_1_eval.json") as f:
        data = json.load(f)

    # 2. Warmup & Load
    print("Warmup & Loading models...")
    unified_classifier.load("models/stage3_v13_classifier")
    await unified_classifier.predict("Warmup text")
    print("Models ready.")

    y_true = []
    y_pred_ml = []

    # Track Z3 status for formal classes
    z3_results = []

    print(f"Running inference on {len(data)} samples...")
    for item in data:
        text = item["text"]
        true_label = item["fallacy"]
        y_true.append(true_label)

        # ML Inference
        res = await unified_classifier.predict(text)
        ml_label = res["fine_labels"][0] if res["fine_labels"] else "Unknown"
        y_pred_ml.append(ml_label)

        # Symbolic Inference (for Formal/Causal targets)
        z3_status = "not_run"

        # Determine if we should run Z3
        is_formal_true = true_label in ["affirming_consequent", "denying_antecedent"]
        is_formal_pred = ml_label in ["affirming_consequent", "denying_antecedent"]
        has_formal_structure = any(m in text.lower() for m in ["if", "therefore", "hence", "since", "so"])

        if is_formal_true or is_formal_pred or has_formal_structure:
            try:
                z3_res = await z3_service.analyze(text)
                z3_status = z3_res.status
            except Exception:
                z3_status = "error"

        z3_results.append({"text": text, "true": true_label, "ml": ml_label, "z3": z3_status})

    # 3. Metrics
    print("\n--- ML Classification Report (Phase 4.1 Targets) ---")
    print(classification_report(y_true, y_pred_ml, labels=TARGET_FALLACIES))

    # 4. Formal Logic Recall Audit (Z3 Impact)
    print("\n--- Formal Logic & Symbolic Impact Audit ---")
    for target in ["affirming_consequent", "denying_antecedent"]:
        target_samples = [r for r in z3_results if r["true"] == target]
        if not target_samples:
            continue

        ml_recall = sum(1 for r in target_samples if r["ml"] == target) / len(target_samples)
        # Z3 'sat' means invalid argument, which is correct for these fallacies
        z3_invalid_det = sum(1 for r in target_samples if r["z3"] == "sat") / len(target_samples)

        # Improved Recall potential: ML Correct OR Z3 correctly detected invalidity
        combined_recall = sum(1 for r in target_samples if r["ml"] == target or r["z3"] == "sat") / len(target_samples)

        print(
            f"  {target:20}: ML Recall={ml_recall:.2f}, Z3 Invalid Det={z3_invalid_det:.2f}, Potential Recall={combined_recall:.2f}"
        )

    # 5. Error Pattern Analysis for Weakest Classes
    print("\n--- Top Error Patterns (Weakest Targets) ---")
    errors = [r for r in z3_results if r["true"] != r["ml"]]
    pattern_counts = {}
    for err in errors:
        if err["true"] in TARGET_FALLACIES:
            pattern = f"{err['true']} -> {err['ml']}"
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
    for pattern, count in sorted_patterns[:15]:
        print(f"  {pattern}: {count}")

    # 6. Ranked Dataset Improvement Recommendations
    print("\n--- Ranked Dataset Improvement Needs ---")
    weak_classes = []
    report_dict = classification_report(y_true, y_pred_ml, labels=TARGET_FALLACIES, output_dict=True)
    for cls in TARGET_FALLACIES:
        f1 = report_dict[cls]["f1-score"]
        recall = report_dict[cls]["recall"]
        weak_classes.append((cls, f1, recall))

    # Sort by F1 (lowest first)
    weak_classes.sort(key=lambda x: x[1])
    for cls, f1, rec in weak_classes:
        impact = "High" if f1 < 0.7 else "Medium" if f1 < 0.85 else "Low"
        print(f"  {cls:20}: F1={f1:.2f}, Recall={rec:.2f} -> Priority: {impact}")


if __name__ == "__main__":
    asyncio.run(evaluate_phase_4_1())
