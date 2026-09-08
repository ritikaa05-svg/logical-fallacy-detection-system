import json
from collections import Counter


def merge_and_validate(original_path, new_path, output_path):
    with open(original_path) as f:
        original_data = json.load(f)
    with open(new_path) as f:
        new_data = json.load(f)

    unique_texts = set(d["text"] for d in original_data)
    rejected_count = 0
    valid_new = []

    for d in new_data:
        if d["text"] in unique_texts:
            rejected_count += 1
        else:
            valid_new.append(d)
            unique_texts.add(d["text"])

    final_data = original_data + valid_new

    with open(output_path, "w") as f:
        json.dump(final_data, f, indent=2)

    print(f"✅ Merged {len(valid_new)} new samples into dataset.")
    print(f"❌ Rejected {rejected_count} duplicates.")
    print(f"📊 Final Dataset Size: {len(final_data)}")

    print("\nNew Class Distribution:")
    counts = Counter(d["fallacy"] for d in final_data)
    for c, count in counts.most_common():
        print(f"  {c:20}: {count}")


if __name__ == "__main__":
    merge_and_validate(
        "data/unified_training_data.json", "data/hard_negatives_phase4_4.json", "data/unified_training_data_v1.1.json"
    )
