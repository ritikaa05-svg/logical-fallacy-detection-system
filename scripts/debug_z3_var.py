import re

CONCLUSION_MARKERS = [
    "therefore",
    "hence",
    "thus",
    "so",
    "consequently",
    "it follows that",
    "we can conclude",
    "in conclusion",
]
IMPLICATION_MARKERS = [
    "leads to",
    "results in",
    "implies",
    "causes",
    "means that",
    "if",
    "when",
    "whenever",
    "since",
]
all_markers = set(CONCLUSION_MARKERS) | set(IMPLICATION_MARKERS)


def get_var(txt):
    # Normalize and extract first significant noun/verb
    txt = txt.lower()
    # Remove markers from the text itself
    for m in all_markers:
        txt = txt.replace(m, "")

    # Ignore negation for variable identity
    search_txt = (
        txt.replace("isn't", "").replace("not", "").replace("no ", "").replace("don't", "").replace("doesn't", "")
    )
    words = re.findall(r"[a-z]{3,}", search_txt)
    stops = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "they",
        "then",
        "will",
        "what",
        "when",
        "were",
        "are",
        "was",
        "has",
        "had",
        "all",
        "does",
        "did",
        "you",
        "your",
        "must",
        "been",
        "have",
    }

    stems = []
    for w in words:
        if w in stops or w in all_markers:
            continue
        # Moderate suffix stripping
        for suffix in ["ing", "ed", "es", "s"]:
            if w.endswith(suffix) and len(w) > 4:
                w = w[: -len(suffix)]
                break
        stems.append(w)

    # Use top 2 stems for more specific unification
    clean = "_".join(stems[:2]) if stems else "prop"
    return clean


print(f"'it rained' -> {get_var('it rained')}")
print(f"'the ground is wet' -> {get_var('the ground is wet')}")
print(f"'therefore the ground is wet' -> {get_var('therefore the ground is wet')}")
