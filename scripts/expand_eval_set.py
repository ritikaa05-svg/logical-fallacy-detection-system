import json
import random
from collections import Counter


def expand_gold_set(input_path, output_path, target_fallacies):
    with open(input_path) as f:
        data = json.load(f)

    # Load unified training data for synthetic/core fallbacks
    with open("data/unified_training_data.json") as f:
        unified_data = json.load(f)

    real_world_sources = ["cocolofa", "navy0067", "king_logic", "mrovkill", "logical-fallacy", "king_logic_climate"]

    real_data = [d for d in data if d.get("source") in real_world_sources]

    expanded_set = []

    # 1. Prioritize targeted fallacies
    for fallacy in target_fallacies:
        f_samples = [d for d in real_data if d["fallacy"] == fallacy]
        if len(f_samples) < 100:
            print(f"  {fallacy}: Only {len(f_samples)} real-world samples. Padding with unified data...")
            pad_samples = [d for d in unified_data if d["fallacy"] == fallacy]
            random.shuffle(pad_samples)
            f_samples.extend(pad_samples[: (100 - len(f_samples))])

        random.shuffle(f_samples)
        expanded_set.extend(f_samples[:100])
        print(f"  {fallacy}: added {len(f_samples[:100])} samples")

    # 2. Add 'valid_reasoning' and 'factual_statement'
    for valid_type in ["valid_reasoning", "factual_statement"]:
        v_samples = [d for d in unified_data if d["fallacy"] == valid_type]
        random.shuffle(v_samples)
        expanded_set.extend(v_samples[:100])
        print(f"  {valid_type}: added {len(v_samples[:100])} samples")

    # 3. Add random other fallacies
    other_samples = [
        d
        for d in real_data
        if d["fallacy"] not in target_fallacies and d["fallacy"] not in ["valid_reasoning", "factual_statement"]
    ]
    random.shuffle(other_samples)
    expanded_set.extend(other_samples[:100])
    print("  Other Real-world Fallacies: added 100 samples")

    random.shuffle(expanded_set)

    with open(output_path, "w") as f:
        json.dump(expanded_set, f, indent=2)

    print(f"\n✅ Created Phase 4.1 evaluation set with {len(expanded_set)} samples.")
    counts = Counter(d["fallacy"] for d in expanded_set)
    for f_type, count in counts.most_common(10):
        print(f"    {f_type}: {count}")


if __name__ == "__main__":
    TARGETS = ["affirming_consequent", "denying_antecedent", "begging_the_question", "false_cause"]
    expand_gold_set("data/merged_fallacies.json", "data/phase4_1_eval.json", TARGETS)
