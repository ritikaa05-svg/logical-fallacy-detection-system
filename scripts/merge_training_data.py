import json
import os
import re
from pathlib import Path


def normalize_label(label: str) -> str:
    if not label:
        return "unknown"
    return label.strip().lower().replace("-", "_").replace(" ", "_")


def is_junk(text: str) -> bool:
    if not text:
        return True
    # 5+ words
    words = text.split()
    if len(words) < 5:
        return True
    # Not a number sequence
    if re.search(r"^[0-9\s.,]+$", text):
        return True
    # Not a URL
    if re.search(r"https?://\S+|www\.\S+", text):
        return True
    return False


def merge_data():
    sources = [
        {"path": "data/merged_fallacies.json", "type": "file", "source_name": "core"},
        {"path": "data/synthetic/", "type": "dir", "source_name": "synthetic"},
        {"path": "data/synthetic_multiturn/", "type": "dir", "source_name": "synthetic_multiturn"},
        {"path": "data/raw_generation_pools/", "type": "dir", "source_name": "raw_pool"},
    ]

    unified_data = []
    seen_keys = set()
    counts = {}

    for src in sources:
        path = Path(src["path"])
        if not path.exists():
            print(f"⚠️ Source not found: {path}")
            continue

        files = []
        if src["type"] == "file":
            files = [path]
        else:
            files = list(path.glob("*.json"))

        src_total = 0
        for f in files:
            with open(f, encoding="utf-8") as f_in:
                try:
                    data = json.load(f_in)
                except Exception as e:
                    print(f"❌ Error reading {f}: {e}")
                    continue

                # Ensure it's a list
                if not isinstance(data, list):
                    data = [data]

                # Determine fallacy from filename for raw_pools or synthetic if needed
                filename_fallacy = normalize_label(f.stem.replace("raw_", "").replace("_pool", ""))

                for item in data:
                    text = item.get("text") or item.get("content") or ""
                    if not isinstance(text, str):
                        text = str(text)

                    if is_junk(text):
                        continue

                    # Determine label
                    fallacy = item.get("fallacy")
                    if not fallacy or fallacy == "unknown":
                        fallacy = filename_fallacy

                    fallacy = normalize_label(fallacy)

                    # Deduplicate (first 150 chars)
                    dedup_key = re.sub(r"\s+", "", text[:150]).lower()
                    if dedup_key in seen_keys:
                        continue

                    seen_keys.add(dedup_key)

                    unified_data.append({"text": text.strip(), "fallacy": fallacy, "source": src["source_name"]})
                    src_total += 1

        counts[src["source_name"]] = src_total
        print(f"✅ {src['source_name']}: {src_total} samples")

    output_path = "data/unified_training_data.json"
    os.makedirs("data", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f_out:
        json.dump(unified_data, f_out, indent=2, ensure_ascii=False)

    print("-" * 30)
    print(f"🚀 FINAL TOTAL: {len(unified_data)} samples")
    print(f"📁 Saved to: {output_path}")


if __name__ == "__main__":
    merge_data()
