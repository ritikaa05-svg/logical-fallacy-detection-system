import json
from pathlib import Path


def run_audit():
    print("🚀 Starting Phase 4 Training Readiness Audit...")

    # 1. Load Data
    data_path = Path("data/unified_training_data.json")
    if not data_path.exists():
        print("❌ FAIL: unified_training_data.json not found.")
        return

    with open(data_path) as f:
        data = json.load(f)

    # 2. Define Taxonomy (Canonical)
    EXPECTED_LABELS = {
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

    # 3. Perform Checks
    total = len(data)
    label_counts = {}
    missing_labels = set()
    invalid_formats = 0
    empty_texts = 0

    for item in data:
        text = item.get("text", "")
        fallacy = item.get("fallacy", "")

        if not text or len(text.strip()) < 5:
            empty_texts += 1

        if fallacy not in EXPECTED_LABELS:
            missing_labels.add(fallacy)

        label_counts[fallacy] = label_counts.get(fallacy, 0) + 1

        if not isinstance(text, str) or not isinstance(fallacy, str):
            invalid_formats += 1

    # 4. Reporting
    print(f"Total Samples: {total}")
    print(f"Unique Labels in Data: {len(label_counts)}")
    print(f"Expected Labels: {len(EXPECTED_LABELS)}")

    if missing_labels:
        print(f"❌ FAIL: Found labels not in taxonomy: {missing_labels}")
    else:
        print("✅ PASS: All labels match canonical taxonomy.")

    if empty_texts > 0:
        print(f"⚠️ WARNING: Found {empty_texts} short or empty texts.")
    else:
        print("✅ PASS: No empty texts found.")

    if invalid_formats > 0:
        print(f"❌ FAIL: Found {invalid_formats} items with invalid data types.")
    else:
        print("✅ PASS: All data types are valid.")

    # Check for coverage of all expected labels
    unrepresented = EXPECTED_LABELS - set(label_counts.keys())
    if unrepresented:
        print(f"⚠️ WARNING: Labels with ZERO samples: {unrepresented}")
    else:
        print("✅ PASS: All taxonomy labels are represented in the dataset.")

    # 5. Readiness Score
    readiness_score = 100
    if missing_labels:
        readiness_score -= 30
    if unrepresented:
        readiness_score -= 20
    if invalid_formats:
        readiness_score -= 20
    if total < 5000:
        readiness_score -= 30

    print(f"\nFINAL READINESS SCORE: {readiness_score}/100")

    if readiness_score >= 80:
        print("🟢 STATUS: READY FOR RETRAINING")
    else:
        print("🔴 STATUS: NOT READY")


if __name__ == "__main__":
    run_audit()
