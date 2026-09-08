import json
from collections import Counter


def merge_v1_2(original_path, new_path, output_path):
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
            valid_new.append({"text": d["text"], "fallacy": d["fallacy"], "source": d["source"]})
            unique_texts.add(d["text"])

    final_data = original_data + valid_new

    with open(output_path, "w") as f:
        json.dump(final_data, f, indent=2)

    print(f"✅ Merged {len(valid_new)} new samples into dataset.")
    print(f"❌ Rejected {rejected_count} duplicates.")
    print(f"📊 Final Dataset Size: {len(final_data)}")

    print("\nBefore Class Distribution:")
    before = Counter(d["fallacy"] for d in original_data)
    for c, count in before.most_common():
        print(f"  {c:30}: {count}")

    print("\nAfter Class Distribution:")
    after = Counter(d["fallacy"] for d in final_data)
    for c, count in after.most_common():
        diff = count - before.get(c, 0)
        sign = "+" if diff > 0 else ""
        print(f"  {c:30}: {count} ({sign}{diff})")


if __name__ == "__main__":
    merge_v1_2(
        "data/unified_training_data_v1.1.json",
        "data/formal_hard_negatives_v1.2.json",
        "data/unified_training_data_v1.2.json",
    )
