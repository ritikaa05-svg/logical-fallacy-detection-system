import json
import random
from pathlib import Path


def rebalance_dataset():
    input_path = Path("data/unified_training_data.json")
    output_path = Path("data/balanced_training_data.json")

    if not input_path.exists():
        print(f"Error: {input_path} not found.")
        return

    with open(input_path) as f:
        data = json.load(f)

    print(f"Original Dataset Size: {len(data)}")

    # 1. Merge Classes
    for item in data:
        if item["fallacy"] == "tu_quoque_contextual":
            item["fallacy"] = "tu_quoque"

    # 2. Group by fallacy
    grouped = {}
    for item in data:
        f = item["fallacy"]
        if f not in grouped:
            grouped[f] = []
        grouped[f].append(item)

    # 3. Apply Cap & Floor
    CAP = 500
    FLOOR = 150
    balanced_data = []

    print("\n--- Rebalancing Report ---")
    print(f"{'Fallacy':<25} | {'Old':<6} | {'New':<6} | {'Action'}")
    print("-" * 55)

    all_fallacies = sorted(grouped.keys())
    for f in all_fallacies:
        samples = grouped[f]
        old_count = len(samples)

        if old_count > CAP:
            # Undersample
            action = "Undersample"
            new_samples = random.sample(samples, CAP)
        elif old_count < FLOOR:
            # Oversample (Duplication)
            action = "Oversample"
            multiplier = (FLOOR // old_count) + 1
            new_samples = (samples * multiplier)[:FLOOR]
        else:
            # Keep
            action = "Keep"
            new_samples = samples

        new_count = len(new_samples)
        print(f"{f:<25} | {old_count:<6} | {new_count:<6} | {action}")
        balanced_data.extend(new_samples)

    # 4. Final Shuffle
    random.shuffle(balanced_data)

    # 5. Save
    with open(output_path, "w") as f:
        json.dump(balanced_data, f, indent=2, ensure_ascii=False)

    print("-" * 55)
    print(f"✅ Balanced Dataset Saved: {output_path}")
    print(f"Final Size: {len(balanced_data)} samples")


if __name__ == "__main__":
    # For reproducibility
    random.seed(42)
    rebalance_dataset()
