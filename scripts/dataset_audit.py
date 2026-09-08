import json
import re
from collections import Counter


def calculate_ttr(text_list):
    """Calculate Type-Token Ratio for diversity."""
    all_text = " ".join(text_list).lower()
    words = re.findall(r"\b\w{3,}\b", all_text)
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def get_structural_diversity(text_list):
    """Estimate structural diversity via unique sentence patterns (simplistic)."""
    patterns = []
    for text in text_list:
        # Replace nouns/verbs with generic markers to see underlying structure
        pattern = re.sub(r"\b(if|then|therefore|because|since|so|but|and|or|not)\b", r" \1 ", text.lower())
        # Keep only markers
        markers = re.findall(r"\b(if|then|therefore|because|since|so|but|and|or|not)\b", pattern)
        patterns.append("-".join(markers))
    return len(set(patterns)) / max(len(patterns), 1)


def audit_dataset(path):
    with open(path) as f:
        data = json.load(f)

    classes = sorted(list(set(d["fallacy"] for d in data)))
    results = {}

    # Common discourse markers
    DISCOURSE_MARKERS = [
        "actually",
        "basically",
        "note that",
        "well",
        "i think",
        "someone once said",
        "in my opinion",
        "studies suggest",
        "experts say",
    ]

    for cls in classes:
        cls_data = [d for d in data if d["fallacy"] == cls]
        texts = [d["text"] for d in cls_data]

        count = len(cls_data)
        synthetic_count = sum(
            1 for d in cls_data if d.get("source") in ["synthetic", "synthetic_multiturn", "template_generator_v1"]
        )
        human_count = count - synthetic_count

        dupes = count - len(set(texts))
        avg_len = sum(len(t.split()) for t in texts) / count

        # Discourse dependence
        marker_counts = Counter()
        for t in texts:
            t_low = t.lower()
            for m in DISCOURSE_MARKERS:
                if m in t_low:
                    marker_counts[m] += 1

        top_markers = marker_counts.most_common(3)
        marker_dep = sum(marker_counts.values()) / count if count > 0 else 0

        results[cls] = {
            "total": count,
            "ratio_human": human_count / count if count > 0 else 0,
            "lexical_diversity": calculate_ttr(texts),
            "structural_diversity": get_structural_diversity(texts),
            "duplicate_rate": dupes / count if count > 0 else 0,
            "avg_length": avg_len,
            "discourse_marker_dependence": marker_dep,
            "top_markers": top_markers,
        }

    return results


if __name__ == "__main__":
    audit_results = audit_dataset("data/unified_training_data.json")
    print(json.dumps(audit_results, indent=2))
