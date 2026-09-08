import json
import random
from collections import Counter


def build_gold_set(input_path, output_path, size=500):
    with open(input_path) as f:
        data = json.load(f)

    # Filter out synthetic sources if possible, or at least prefer real-world ones
    # Common real-world sources in merged_fallacies: cocolofa, navy0067, king_logic, mrovkill, logical-fallacy
    real_world_sources = ["cocolofa", "navy0067", "king_logic", "mrovkill", "logical-fallacy", "king_logic_climate"]

    real_data = [d for d in data if d.get("source") in real_world_sources]

    if len(real_data) < size:
        print(f"Warning: Only {len(real_data)} real-world samples found. Adding others to reach {size}.")
        other_data = [d for d in data if d.get("source") not in real_world_sources]
        random.shuffle(other_data)
        real_data.extend(other_data[: (size - len(real_data))])

    # Stratify by fallacy type
    fallacies = sorted(list(set(d["fallacy"] for d in real_data)))
    samples_per_fallacy = size // len(fallacies)

    gold_set = []
    for f_type in fallacies:
        f_samples = [d for d in real_data if d["fallacy"] == f_type]
        random.shuffle(f_samples)
        gold_set.extend(f_samples[: max(1, samples_per_fallacy)])

    # Fill remaining to reach exact size
    if len(gold_set) < size:
        remaining = [d for d in real_data if d not in gold_set]
        random.shuffle(remaining)
        gold_set.extend(remaining[: (size - len(gold_set))])

    random.shuffle(gold_set)
    gold_set = gold_set[:size]

    with open(output_path, "w") as f:
        json.dump(gold_set, f, indent=2)

    print(f"✅ Created gold-standard set with {len(gold_set)} samples.")
    print("Class distribution:")
    counts = Counter(d["fallacy"] for d in gold_set)
    for f_type, count in counts.most_common():
        print(f"  {f_type}: {count}")


if __name__ == "__main__":
    build_gold_set("data/merged_fallacies.json", "data/gold_standard_eval.json", size=500)
