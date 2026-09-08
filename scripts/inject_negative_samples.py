import json


def inject_negative_samples(data_path="data/augmented_training_data.json"):
    with open(data_path) as f:
        data = json.load(f)

    # Trigger words identified as potential sources of shortcut bias
    # We will generate negative examples (valid reasoning) using these terms
    trigger_words = ["natural", "people", "just", "like", "think", "true", "right"]

    # Create valid examples for each trigger word
    new_data = []
    for word in trigger_words:
        new_data.append(
            {
                "text": f"It is a {word} fact that evidence should be evaluated based on the available data.",
                "fallacy": "none",
                "source": "synthetic_negative",
            }
        )
        new_data.append(
            {
                "text": f"We should {word} consider all viewpoints to reach a rational conclusion.",
                "fallacy": "none",
                "source": "synthetic_negative",
            }
        )
        new_data.append(
            {
                "text": f"Logic is {word} when it follows from the premises.",
                "fallacy": "none",
                "source": "synthetic_negative",
            }
        )

    # Combine
    combined_data = data + new_data

    with open("data/final_training_data.json", "w") as f:
        json.dump(combined_data, f, indent=2)

    print(f"Negative sampling complete. Added {len(new_data)} samples.")


if __name__ == "__main__":
    inject_negative_samples()
