"""Merge all WORKING fallacy datasets into one training file."""

import json
from collections import Counter

import requests
from datasets import load_dataset

all_data = []

# ============================================================
# 1. CoCoLoFa (GitHub — 7,706 comments, EMNLP 2024)
# ============================================================
print("1. CoCoLoFa...")
COCOLOFA_LABELS = {
    "appeal to authority": "appeal_to_authority",
    "appeal to majority": "bandwagon",
    "appeal to nature": "appeal_to_nature",
    "appeal to tradition": "appeal_to_tradition",
    "appeal to worse problems": "red_herring",
    "false dilemma": "false_dilemma",
    "hasty generalization": "hasty_generalization",
    "slippery slope": "slippery_slope",
}
try:
    for split in ["train", "dev", "test"]:
        url = f"https://raw.githubusercontent.com/Crowd-AI-Lab/cocolofa/main/{split}.json"
        r = requests.get(url, timeout=30)
        for article in r.json():
            for c in article.get("comments", []):
                if c.get("fallacy") and c["fallacy"] != "none":
                    all_data.append(
                        {
                            "text": c["comment"].strip(),
                            "fallacy": COCOLOFA_LABELS.get(c["fallacy"], c["fallacy"]),
                            "source": "cocolofa",
                        }
                    )
    print(f"   ✅ {len(all_data)} total so far")
except Exception as e:
    print(f"   ❌ {e}")

# ============================================================
# 2. CoT Logic Reasoning (10,500 samples — extract fallacy type from text)
# ============================================================
print("2. CoT Logic Reasoning...")
FALLACY_KEYWORDS = {
    "false_cause": ["false cause", "post hoc", "causation", "causal"],
    "ad_hominem": ["ad hominem", "personal attack"],
    "straw_man": ["straw man", "strawman", "misrepresent"],
    "slippery_slope": ["slippery slope"],
    "false_dilemma": ["false dilemma", "false dichotomy", "either or"],
    "begging_the_question": ["begging the question", "circular reasoning"],
    "appeal_to_emotion": ["appeal to emotion", "emotional appeal"],
    "appeal_to_authority": ["appeal to authority"],
    "bandwagon": ["bandwagon", "ad populum"],
    "hasty_generalization": ["hasty generalization", "overgeneraliz"],
    "equivocation": ["equivocation", "ambiguity"],
    "red_herring": ["red herring", "irrelevant"],
    "affirming_consequent": ["affirming the consequent", "affirming consequent"],
    "denying_antecedent": ["denying the antecedent"],
    "tu_quoque": ["tu quoque", "whatabout", "you too"],
}
try:
    ds = load_dataset("isaiahbjork/cot-logic-reasoning", split="train")
    for item in ds:
        prompt = str(item.get("prompt", "")).lower()
        response = str(item.get("response", "")).lower()
        full_text = f"{item.get('prompt', '')} {item.get('response', '')}"[:1500]

        # Find fallacy type in prompt
        found = False
        for label, keywords in FALLACY_KEYWORDS.items():
            if any(kw in prompt for kw in keywords):
                all_data.append({"text": full_text.strip(), "fallacy": label, "source": "cot_logic"})
                found = True
                break
        if not found and "fallacy" in prompt:
            all_data.append({"text": full_text.strip(), "fallacy": "logical_fallacy", "source": "cot_logic"})
    print(f"   ✅ {len(all_data)} total so far")
except Exception as e:
    print(f"   ❌ {e}")

# ============================================================
# 3. Navy0067 contrastive pairs (1,406 clean samples)
# ============================================================
print("3. Navy0067 contrastive pairs...")
NAVY_LABELS = {
    "ad hominem": "ad_hominem",
    "false dilemma": "false_dilemma",
    "straw man": "straw_man",
    "slippery slope": "slippery_slope",
    "appeal to emotion": "appeal_to_emotion",
    "false cause": "false_cause",
    "hasty generalization": "hasty_generalization",
    "circular reasoning": "begging_the_question",
    "red herring": "red_herring",
    "bandwagon": "bandwagon",
}
try:
    ds = load_dataset("Navy0067/contrastive-pairs-for-logical-fallacy", split="train")
    for item in ds:
        text = str(item.get("text", ""))
        label = str(item.get("label", "")).lower().strip()
        cleaned = NAVY_LABELS.get(label, label)
        if text and len(text.split()) >= 3:
            all_data.append({"text": text, "fallacy": cleaned, "source": "navy0067"})
    print(f"   ✅ {len(all_data)} total so far")
except Exception as e:
    print(f"   ❌ {e}")

# ============================================================
# 4. KingTechnician (logic + logic_climate configs)
# ============================================================
print("4. KingTechnician...")
KING_LABELS = {
    "ad hominem": "ad_hominem",
    "appeal to emotion": "appeal_to_emotion",
    "false causality": "false_cause",
    "circular reasoning": "begging_the_question",
    "faulty generalization": "hasty_generalization",
    "false dilemma": "false_dilemma",
    "ad populum": "bandwagon",
    "fallacy of relevance": "red_herring",
    "fallacy of extension": "straw_man",
    "fallacy of logic": "affirming_consequent",
    "equivocation": "equivocation",
}
for config in ["logic", "logic_climate"]:
    try:
        ds = load_dataset("KingTechnician/logical-fallacy", config, split="train")
        for item in ds:
            text = str(item.get("source_article", ""))
            label = str(item.get("updated_label", "")).lower().strip()
            cleaned = KING_LABELS.get(label, label)
            if text and len(text.split()) >= 3:
                all_data.append({"text": text, "fallacy": cleaned, "source": f"king_{config}"})
    except Exception as e:
        print(f"   {config}: {e}")
print(f"   ✅ {len(all_data)} total so far")

# ============================================================
# 5. MrOvkill (already working)
# ============================================================
print("5. MrOvkill...")
try:
    ds = load_dataset("MrOvkill/fallacies-fallacy-base", split="train")
    for item in ds:
        text = f"{item.get('example', '')} {item.get('explanation', '')}".strip()
        label = str(item.get("name", "")).lower().replace(" ", "_").replace("-", "_")
        cleaned = KING_LABELS.get(label, label)
        if len(text.split()) >= 3:
            all_data.append({"text": text, "fallacy": cleaned, "source": "mrovkill"})
    print(f"   ✅ {len(all_data)} total so far")
except Exception as e:
    print(f"   ❌ {e}")

# ============================================================
# Final cleanup
# ============================================================
VALID = {
    "ad_hominem",
    "straw_man",
    "false_dilemma",
    "slippery_slope",
    "appeal_to_emotion",
    "appeal_to_authority",
    "appeal_to_nature",
    "false_cause",
    "begging_the_question",
    "hasty_generalization",
    "red_herring",
    "bandwagon",
    "equivocation",
    "tu_quoque",
    "affirming_consequent",
    "denying_antecedent",
    "composition",
    "division",
    "appeal_to_tradition",
}

filtered = [d for d in all_data if d["fallacy"] in VALID or d["fallacy"] == "logical_fallacy"]

# Deduplicate
seen = set()
deduped = []
for d in filtered:
    key = d["text"][:150]
    if key not in seen:
        seen.add(key)
        deduped.append(d)

# Report
print(f"\n{'=' * 50}")
print(f"Raw: {len(all_data)} | Filtered: {len(filtered)} | Deduped: {len(deduped)}")
labels = Counter(d["fallacy"] for d in deduped)
for l, c in labels.most_common(20):
    print(f"  {l}: {c}")

with open("data/merged_fallacies.json", "w") as f:
    json.dump(deduped, f, indent=2)
print(f"\n✅ Saved {len(deduped)} samples")
