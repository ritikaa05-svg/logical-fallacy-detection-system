import argparse
import json


def validate(input_file):
    with open(input_file) as f:
        data = json.load(f)

    errors = []
    stats = {"valid_arg": 0, "factual": 0, "citation": 0, "definition": 0}

    for i, entry in enumerate(data):
        # 1. Schema check
        if "metadata" not in entry:
            errors.append(f"Entry {i}: Missing structured metadata.")
            continue

        meta = entry["metadata"]
        # 2. Reasoning Validation
        if not meta.get("premise_1") or not meta.get("conclusion"):
            errors.append(f"Entry {i}: Missing reasoning components.")

        # 3. Quality Filters (heuristics for classification)
        text = entry["text"].lower()
        if any(word in text for word in ["according to", "study shows that", "research says"]):
            stats["factual"] += 1
        elif len(text.split()) > 10 and "therefore" in text:
            stats["valid_arg"] += 1
        else:
            stats["factual"] += 1

    return errors, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    args = parser.parse_args()

    errors, stats = validate(args.input_file)
    print(f"Validation Stats: {stats}")
    if errors:
        print("Validation errors found:", len(errors))
    else:
        print("Validation PASSED.")


if __name__ == "__main__":
    main()
