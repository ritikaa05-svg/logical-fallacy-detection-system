"""
Logiscan Data Engine: Unified Dataset Compiler & Balancer
Patched Version: Bypasses legacy HF loading scripts, corrects LogiQA pathways,
and stabilizes data structures for long-tail multi-class training.
"""

import json
import os
from collections import Counter

import requests
from datasets import load_dataset

all_data = []

# ============================================================
# 1. CoCoLoFa (GitHub — EMNLP 2024 Contextual Comments)
# ============================================================
print("1. Processing CoCoLoFa...")
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
    print(f"   ✅ CoCoLoFa loaded. Total entries: {len(all_data)}")
except Exception as e:
    print(f"   ❌ CoCoLoFa Processing Failed: {e}")

# ============================================================
# 2. CoT Logic Reasoning (Broadened Keyword Boundaries)
# ============================================================
print("2. Processing CoT Logic Reasoning...")
FALLACY_KEYWORDS = {
    "false_cause": ["false cause", "post hoc", "causation", "causal", "correlation"],
    "ad_hominem": ["ad hominem", "personal attack", "insult"],
    "straw_man": ["straw man", "strawman", "misrepresent"],
    "slippery_slope": ["slippery slope"],
    "false_dilemma": ["false dilemma", "false dichotomy", "either or"],
    "begging_the_question": ["begging the question", "circular reasoning", "circular claim"],
    "appeal_to_emotion": ["appeal to emotion", "emotional appeal", "pity", "fear"],
    "appeal_to_authority": ["appeal to authority"],
    "bandwagon": ["bandwagon", "ad populum", "majority"],
    "hasty_generalization": ["hasty generalization", "overgeneraliz", "anecdotal"],
    "equivocation": ["equivocation", "ambiguity"],
    "red_herring": ["red herring", "distraction", "irrelevant"],
    "affirming_consequent": ["affirming the consequent", "affirming consequent", "consequent"],
    "denying_antecedent": ["denying the antecedent", "antecedent"],
}
try:
    ds = load_dataset("isaiahbjork/cot-logic-reasoning", split="train")
    cot_count = 0
    for item in ds:
        prompt = str(item.get("prompt", "")).lower()
        full_text = f"{item.get('prompt', '')} {item.get('response', '')}"[:1500]

        for label, keywords in FALLACY_KEYWORDS.items():
            if any(kw in prompt for kw in keywords):
                all_data.append({"text": full_text.strip(), "fallacy": label, "source": "cot_logic"})
                cot_count += 1
                break
    print(f"   ✅ CoT Logic Reasoning processed. Added {cot_count} targeted samples.")
except Exception as e:
    print(f"   ❌ CoT Logic Processing Failed: {e}")

# ============================================================
# 3. Navy0067 Contrastive Pairs
# ============================================================
print("3. Processing Navy0067 contrastive pairs...")
NAVY_LABELS = {
    "ad hominem": "ad_hominem",
    "false dilemma": "false_dilemma",
    "straw man": "straw_man",
    "slippery slope": "slippery_slope",
    "appeal to emotion": "appeal_to_emotion",
    "false cause": "false_cause",
    "hasty generalization": "hasty_generalization",
    "circular reasoning": "begging_the_question",
    "red_herring": "red_herring",
    "bandwagon": "bandwagon",
}
try:
    ds = load_dataset("Navy0067/contrastive-pairs-for-logical-fallacy", split="train")
    navy_count = 0
    for item in ds:
        text = str(item.get("text", ""))
        label = str(item.get("label", "")).lower().strip()
        cleaned = NAVY_LABELS.get(label, label)
        if text and len(text.split()) >= 3:
            all_data.append({"text": text, "fallacy": cleaned, "source": "navy0067"})
            navy_count += 1
    print(f"   ✅ Navy0067 processed. Added {navy_count} clean samples.")
except Exception as e:
    print(f"   ❌ Navy0067 Processing Failed: {e}")

# ============================================================
# 4. KingTechnician (logic + logic_climate configurations)
# ============================================================
print("4. Processing KingTechnician configs...")
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
        king_count = 0
        for item in ds:
            text = str(item.get("source_article", ""))
            label = str(item.get("updated_label", "")).lower().strip()
            cleaned = KING_LABELS.get(label, label)
            if text and len(text.split()) >= 3:
                all_data.append({"text": text, "fallacy": cleaned, "source": f"king_{config}"})
                king_count += 1
        print(f"   └─ Config [{config}]: Added {king_count} samples.")
    except Exception as e:
        print(f"   ⚠️ KingTechnician Config {config} Skipping: {e}")

# ============================================================
# 5. MrOvkill Base Fallacies
# ============================================================
print("5. Processing MrOvkill Base Dataset...")
try:
    ds = load_dataset("MrOvkill/fallacies-fallacy-base", split="train")
    mrov_count = 0
    for item in ds:
        text = f"{item.get('example', '')} {item.get('explanation', '')}".strip()
        label = str(item.get("name", "")).lower().replace(" ", "_").replace("-", "_")
        if len(text.split()) >= 3:
            all_data.append({"text": text, "fallacy": label, "source": "mrovkill"})
            mrov_count += 1
    print(f"   ✅ MrOvkill processed. Added {mrov_count} samples.")
except Exception as e:
    print(f"   ❌ MrOvkill Processing Failed: {e}")

# ============================================================
# 6. CAUSALNLP Integration (Bypassing custom script limitations)
# ============================================================
print("6. Processing causalNLP via parquet engine...")
CAUSALNLP_MAP = {
    "faulty generalization": "hasty_generalization",
    "ad hominem": "ad_hominem",
    "ad populum": "bandwagon",
    "false causality": "false_cause",
    "circular claim": "begging_the_question",
    "appeal to emotion": "appeal_to_emotion",
    "fallacy of relevance": "red_herring",
    "fallacy of extension": "straw_man",
    "false dilemma": "false_dilemma",
    "slippery slope": "slippery_slope",
    "appeal to authority": "appeal_to_authority",
    "equivocation": "equivocation",
}
try:
    # Read clean compiled outputs safely to protect pipeline execution
    ds_causal = load_dataset("eduardf/logical-fallacy-detection", split="train")
    causal_count = 0
    for item in ds_causal:
        text = item.get("text", item.get("source_article", ""))
        label = item.get("label", item.get("updated_label", "")).lower().strip()
        cleaned = CAUSALNLP_MAP.get(label, label)
        if text and cleaned in CAUSALNLP_MAP.values():
            all_data.append({"text": text, "fallacy": cleaned, "source": "causalnlp_patched"})
            causal_count += 1
    print(f"   ✅ Patched causalNLP integrated: Appended {causal_count} rows.")
except Exception as e:
    print(f"   ⚠️ Patched causalNLP bypass noted: {e}")

# ============================================================
# 7. FIXED: LogiQA (Corrected Pathway to Official Repository)
# ============================================================
print("7. Processing LogiQA Official Pathway...")
try:
    # Reconnected via correct HuggingFace Hub identifier string
    ds_logi = load_dataset("logiqa", split="train")
    logiqa_count = 0
    for item in ds_logi:
        full_problem = f"{item.get('context', '')} Q: {item.get('query', '')}"
        options = " ".join(item.get("options", []))
        combined_text = f"{full_problem} Options: {options}"[:1500]

        if "consist of" in combined_text.lower() or "part of" in combined_text.lower():
            all_data.append({"text": combined_text, "fallacy": "composition", "source": "logiqa_fixed"})
            all_data.append({"text": combined_text, "fallacy": "division", "source": "logiqa_fixed"})
            logiqa_count += 2
        elif "if" in combined_text.lower() and "then" in combined_text.lower():
            all_data.append({"text": combined_text, "fallacy": "affirming_consequent", "source": "logiqa_fixed"})
            logiqa_count += 1
    print(f"   ✅ LogiQA fixed repository processed. Added {logiqa_count} entries.")
except Exception as e:
    print(f"   ❌ LogiQA Pipeline Ingestion Error: {e}")

# ============================================================
# 8. TARGETED STRATEGIC INJECTION BOOSTERS (Pumping the long-tail)
# ============================================================
print("8. Pumping minority structural reasoning vectors...")
# Multiplying the structural baseline anchors to ensure safe gradient paths
for _ in range(15):
    all_data.append(
        {
            "fallacy": "composition",
            "text": "Every atom in this notebook is invisible. Therefore, the notebook itself is invisible.",
            "source": "booster",
        }
    )
    all_data.append(
        {
            "fallacy": "composition",
            "text": "Each singer in the group is amazing solo. Thus, the whole choir will sound perfect without practices.",
            "source": "booster",
        }
    )
    all_data.append(
        {
            "fallacy": "division",
            "text": "This team is incredibly heavy. Therefore, every player on this team is heavy.",
            "source": "booster",
        }
    )
    all_data.append(
        {
            "fallacy": "division",
            "text": "The puzzle is completely round. Consequently, every piece must be round.",
            "source": "booster",
        }
    )
    all_data.append(
        {
            "fallacy": "denying_antecedent",
            "text": "If it rains, the ground gets wet. It did not rain. Therefore, the ground is completely dry.",
            "source": "booster",
        }
    )
    all_data.append(
        {
            "fallacy": "denying_antecedent",
            "text": "If you go to Harvard you are rich. You did not go to Harvard. Therefore you are poor.",
            "source": "booster",
        }
    )

# ============================================================
# 9. POST-PROCESSING & COMPILATION
# ============================================================
print("9. Compiling optimization layers...")

VALID_CLASSES = {
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
    "affirming_consequent",
    "denying_antecedent",
    "composition",
    "division",
    "appeal_to_tradition",
}

filtered = [d for d in all_data if d["fallacy"] in VALID_CLASSES]

seen = set()
deduped = []
for d in filtered:
    key = d["text"][:150].lower().strip()
    if key not in seen:
        seen.add(key)
        deduped.append(d)

print(f"\n{'=' * 60}\n📊 LOGISCAN PIPELINE ENGINE: PATCHED REPORT\n{'=' * 60}")
print(f"Raw Combined Rows  : {len(all_data)} | Final Deduplicated: {len(deduped)}")

print("\nUpdated Fine-Grained Distributions:")
labels = Counter(d["fallacy"] for d in deduped)
for fallacy_name, current_count in labels.most_common():
    print(f"  🔹 {fallacy_name.ljust(25)}: {current_count} rows")

os.makedirs("data", exist_ok=True)
with open("data/merged_fallacies_mega.json", "w") as f:
    json.dump(deduped, f, indent=2)
print("\n💾 Optimization dataset written to 'data/merged_fallacies_mega.json'!")
