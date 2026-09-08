import json
from pathlib import Path


def decontaminate():
    print("🚀 Starting Data De-contamination")

    # Path to the primary source of core data (merged from sprint batches and initial pools)
    # Based on scripts/merge_training_data.py, it looks for data in various folders.
    # The most surgical place to clean is the merged output or the raw pools.

    merged_path = Path("data/unified_training_data.json")
    if not merged_path.exists():
        print("Error: unified_training_data.json not found. Run merge first.")
        return

    with open(merged_path) as f:
        data = json.load(f)

    # Patterns indicating personal attacks (Ad Hominem) that often poison False Cause
    ATTACK_PATTERNS = ["you are", "idiot", "stupid", "dumb", "your brain", "liar", "greedy", "scum", "loser", "shut up"]

    cleaned_data = []
    relabelled_count = 0

    for item in data:
        text_lower = item["text"].lower()

        # S01: False Cause Cleanup
        if item["fallacy"] == "false_cause":
            if any(p in text_lower for p in ATTACK_PATTERNS):
                # This is likely Ad Hominem, not False Cause
                item["fallacy"] = "ad_hominem"
                relabelled_count += 1

        # S02: Hasty Generalization Cleanup
        if item["fallacy"] == "hasty_generalization":
            if "because" in text_lower and ("then" in text_lower or "so" in text_lower):
                # If it has sequential causal links, it might be False Cause
                # But we'll be conservative and just flag for manual if we had a human.
                # For now, we'll focus on the obvious attack overlaps.
                pass

        cleaned_data.append(item)

    print(f"✅ Relabelled {relabelled_count} samples from False Cause to Ad Hominem.")

    # Save back
    with open(merged_path, "w") as f:
        json.dump(cleaned_data, f, indent=2)
    print(f"📁 Saved cleaned dataset to {merged_path}")


if __name__ == "__main__":
    decontaminate()
