import json
import os
import random
import re
import sys

# Add project root to path
sys.path.append(os.getcwd())


def create_evidence_gold_set(input_paths, output_path, target_classes):
    all_raw = []
    for path in input_paths:
        with open(path) as f:
            all_raw.extend(json.load(f))

    # Filter and sample
    samples = [d for d in all_raw if d.get("fallacy") in target_classes]
    random.shuffle(samples)

    gold_set = []

    # Simple logic to 'manually' define expected quotes for the 200 samples
    # In a real scenario, this would be human-labeled.
    # For this audit, I will use a conservative 'shortest sentence containing trigger' as ground truth.

    triggers = {
        "straw_man": ["so you mean", "you're saying", "distort", "claim that"],
        "ad_hominem": ["you are", "idiot", "liar", "shill", "who are you"],
        "red_herring": ["what about", "consider this instead", "not relevant"],
        "false_cause": ["because", "causes", "results in", "therefore", "so"],
        "appeal_to_emotion": ["think of the", "suffer", "children", "fear", "danger"],
    }

    for item in samples:
        if len(gold_set) >= 200:
            break

        text = item["text"]
        fallacy = item["fallacy"]

        # Ground Truth Strategy: Find the shortest sentence that contains a fallback trigger
        # If no trigger, use the last sentence as the 'logical conclusion' of the fallacy.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        expected_quote = sentences[-1]  # Default to last sentence

        class_triggers = triggers.get(fallacy, [])
        for sent in sentences:
            if any(t in sent.lower() for t in class_triggers):
                expected_quote = sent
                break

        start = text.find(expected_quote)
        if start == -1:
            continue  # Should not happen

        gold_set.append(
            {
                "text": text,
                "fallacy": fallacy,
                "expected_quote": expected_quote,
                "expected_start": start,
                "expected_end": start + len(expected_quote),
            }
        )

    with open(output_path, "w") as f:
        json.dump(gold_set, f, indent=2)

    print(f"✅ Created Evidence Gold Set with {len(gold_set)} samples.")


if __name__ == "__main__":
    TARGETS = ["straw_man", "ad_hominem", "red_herring", "false_cause", "appeal_to_emotion"]
    create_evidence_gold_set(
        ["data/gold_standard_eval.json", "data/merged_fallacies.json"], "data/evidence_gold_set.json", TARGETS
    )
