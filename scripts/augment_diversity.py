import json


def augment_dataset(data_path="data/cleaned_training_data.json"):
    with open(data_path) as f:
        data = json.load(f)

    # Define domain-shifting templates
    # These replace common biased nouns with varied contexts
    shifts = {
        "composition": [
            ("metal", "software"),
            ("heavy", "complex"),
            ("long", "expensive"),
            ("book", "module"),
            ("microscopic", "feature"),
            ("machine", "system"),
        ],
        "division": [
            ("metal", "team"),
            ("heavy", "skilled"),
            ("long", "fast"),
            ("book", "project"),
            ("microscopic", "granular"),
            ("machine", "organization"),
        ],
    }

    augmented_data = []
    for entry in data:
        augmented_data.append(entry)

        # Augment only specific classes
        if entry["fallacy"] in shifts:
            text = entry["text"]
            for old, new in shifts[entry["fallacy"]]:
                text = text.replace(old, new)

            # Add augmented version
            new_entry = entry.copy()
            new_entry["text"] = text
            new_entry["source"] = "synthetic_augmented"
            augmented_data.append(new_entry)

    # Save augmented
    with open("data/augmented_training_data.json", "w") as f:
        json.dump(augmented_data, f, indent=2)

    print(f"Augmentation complete. Initial: {len(data)}, New: {len(augmented_data)}")


if __name__ == "__main__":
    augment_dataset()
