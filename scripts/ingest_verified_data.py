#!/usr/bin/env python3
"""
LogiScan Data Engineering Pipeline: Schema-Aligned Ingestion
"""

import json
import os
import sys
from collections import Counter

BASELINE_FILE = "data/merged_fallacies.json"
TRAIN_SPLIT_FILE = "data/stage1_train.json"
SYNTHETIC_VERIFIED_DIR = "data/verified_batches/"
BACKUP_DIR = "data/backups/"


def normalize_text(text: str) -> str:
    """Standardizes string formatting to guarantee clean deduplication."""
    text = text.strip().lower()
    text = text.strip('"`*')
    return " ".join(text.split())


def run_aligned_ingestion():
    print("========== STARTING ADAPTED LOGISCAN INGESTION ==========")

    if not os.path.exists(BASELINE_FILE) or not os.path.exists(TRAIN_SPLIT_FILE):
        print("❌ Error: Baseline files missing.")
        sys.exit(1)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(SYNTHETIC_VERIFIED_DIR, exist_ok=True)

    # 1. Map existing text to prevent duplication leakage
    print("📋 Hashing baseline data entries...")
    seen_hashes = set()

    with open(BASELINE_FILE, encoding="utf-8") as f:
        baseline_data = json.load(f)
        for item in baseline_data:
            seen_hashes.add(normalize_text(item["text"]))

    with open(TRAIN_SPLIT_FILE, encoding="utf-8") as f:
        train_split_data = json.load(f)
        for item in train_split_data:
            seen_hashes.add(normalize_text(item["text"]))

    # 2. Process Team Batch Exports
    synthetic_files = [f for f in os.listdir(SYNTHETIC_VERIFIED_DIR) if f.endswith(".json")]
    if not synthetic_files:
        print(f"ℹ️ Drop zone clear. Place verified team JSON files into '{SYNTHETIC_VERIFIED_DIR}'")
        return

    valid_new_records = []
    skipped_duplicates = 0

    for filename in synthetic_files:
        file_path = os.path.join(SYNTHETIC_VERIFIED_DIR, filename)
        try:
            with open(file_path, encoding="utf-8") as f:
                items = json.load(f)

            for item in items:
                raw_text = item.get("text", "").strip()
                norm_text = normalize_text(raw_text)
                # Fallback lookups to catch any user typing variations in spreadsheet exports
                fallacy_name = item.get("fallacy", item.get("fallacy_type", "unknown"))

                # Check for duplications
                if norm_text in seen_hashes:
                    skipped_duplicates += 1
                    continue

                seen_hashes.add(norm_text)

                # STRICT SCHEMA ALIGNMENT MATCHING YOUR LOGISCAN BASELINE
                clean_record = {"text": raw_text, "fallacy": fallacy_name, "source": "synthetic_boost_sprint"}

                # Optional Stage 4 passthrough metadata if Team 1 added Z3 mappings
                if "z3_formulation" in item:
                    clean_record["z3_formulation"] = item["z3_formulation"]

                valid_new_records.append(clean_record)

        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse file {filename}: {e}")

    print(f"📊 Filtering complete. Safe new samples: {len(valid_new_records)} | Duplicates cut: {skipped_duplicates}")

    if not valid_new_records:
        print("⏹️ Ingestion complete. No new unique elements added.")
        return

    # 3. Secure Safe-Point Backup
    with open(os.path.join(BACKUP_DIR, "stage1_train.json.bak"), "w", encoding="utf-8") as bkp:
        json.dump(train_split_data, bkp, indent=2)

    # 4. Append to Training State File Only
    train_split_data.extend(valid_new_records)

    with open(TRAIN_SPLIT_FILE, "w", encoding="utf-8") as f:
        json.dump(train_split_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Ingestion successful. Total rows in training file: {len(train_split_data)}")

    # Show updated distribution profile
    distribution = Counter([item["fallacy"] for item in train_split_data if "fallacy" in item])
    print("\n📈 Top Updated Categories:")
    for fallacy, count in distribution.most_common(5):
        print(f"   - {fallacy}: {count}")


if __name__ == "__main__":
    run_aligned_ingestion()
