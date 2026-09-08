import json
import os
import re
import xml.etree.ElementTree as ET

import requests

# Try to import datasets, with fallback
try:
    from datasets import load_dataset

    HAS_DATASETS = True
except ImportError:
    HAS_DATASETS = False
    print("Warning: 'datasets' library not found. Wikipedia and DailyDialog will be skipped.")

# Configuration
MIN_WORDS = 8
TARGET_WIKI_DAILY = 5000
TARGET_ARXIV = 500
OUTPUT_FILE = "data/stage1_negatives_wiki.json"

# Discourse markers to avoid in negatives (to ensure they aren't arguments)
ARGUMENT_MARKERS = [
    "therefore",
    "hence",
    "thus",
    "consequently",
    "so",
    "it follows that",
    "because",
    "since",
    "due to",
    "as a result",
    "clearly",
    "obviously",
    "prove",
    "evidence",
]


def is_clean_negative(text: str) -> bool:
    """Check if text is likely a non-argument."""
    words = text.split()
    if len(words) < MIN_WORDS:
        return False

    text_lower = text.lower()
    # If it contains strong argument markers, skip it for now
    if any(f" {marker} " in f" {text_lower} " for marker in ARGUMENT_MARKERS):
        return False

    # Avoid quotes and dialogue for Wikipedia if possible, but keep for DailyDialog
    return True


def get_arxiv_abstracts(query: str = "cat:cs.CL", max_results: int = 1000) -> list[str]:
    """Fetch scientific abstracts from arXiv."""
    print(f"Fetching {max_results} abstracts from arXiv for {query}...")
    url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_results}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        abstracts = []
        # XML namespace for arXiv
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            summary = entry.find("atom:summary", ns).text
            # Clean up newlines and spaces
            summary = " ".join(summary.split())
            # Split into sentences (simple)
            sentences = re.split(r"(?<=[.!?])\s+", summary)
            for s in sentences:
                if len(s.split()) >= MIN_WORDS:
                    abstracts.append(s.strip())

        return abstracts
    except Exception as e:
        print(f"Error fetching arXiv data: {e}")
        return []


def load_positives() -> set[str]:
    """Load existing Stage 1 positives for deduplication."""
    positives = set()
    if os.path.exists("data/merged_fallacies.json"):
        with open("data/merged_fallacies.json") as f:
            data = json.load(f)
            for item in data:
                positives.add(item.get("text", "").strip().lower())
    return positives


def collect_data():
    positives = load_positives()
    all_negatives = []

    # 1. Wikipedia & DailyDialog (via HuggingFace Datasets)
    if HAS_DATASETS:
        print("Loading Wikipedia...")
        try:
            wiki = load_dataset("wikipedia", "20220301.en", split="train", streaming=True)
            count = 0
            for article in wiki:
                # Get the first few sentences of each article
                text = article["text"]
                sentences = re.split(r"(?<=[.!?])\s+", text[:2000])
                for s in sentences:
                    s_clean = s.strip()
                    if is_clean_negative(s_clean) and s_clean.lower() not in positives:
                        all_negatives.append({"text": s_clean, "label": 0, "source": "wikipedia"})
                        count += 1
                if count >= TARGET_WIKI_DAILY // 2:
                    break
            print(f"Collected {count} Wikipedia samples.")
        except Exception as e:
            print(f"Wikipedia failed: {e}")

        print("Loading DailyDialog...")
        try:
            dd = load_dataset("daily_dialog", split="train")
            count = 0
            for item in dd:
                for utterance in item["dialog"]:
                    u_clean = utterance.strip()
                    if len(u_clean.split()) >= MIN_WORDS and u_clean.lower() not in positives:
                        all_negatives.append({"text": u_clean, "label": 0, "source": "daily_dialog"})
                        count += 1
                if count >= TARGET_WIKI_DAILY // 2:
                    break
            print(f"Collected {count} DailyDialog samples.")
        except Exception as e:
            print(f"DailyDialog failed: {e}")
    else:
        # Emergency fallback if datasets is not available: use a small local set or skip
        print("Skipping Wiki/DailyDialog as 'datasets' is not installed.")

    # 2. arXiv Scientific Abstracts (Hard Negatives)
    arxiv_sentences = get_arxiv_abstracts(max_results=500)
    count = 0
    for s in arxiv_sentences:
        if s.lower() not in positives:
            all_negatives.append({"text": s, "label": 0, "source": "scientific_abstract"})
            count += 1
        if count >= TARGET_ARXIV:
            break
    print(f"Collected {count} arXiv samples.")

    # Deduplicate within collected data
    unique_negatives = []
    seen = set()
    for item in all_negatives:
        if item["text"].lower() not in seen:
            seen.add(item["text"].lower())
            unique_negatives.append(item)

    # Save output
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(unique_negatives, f, indent=2)

    print(f"\n✅ Pipeline complete. Saved {len(unique_negatives)} negatives to {OUTPUT_FILE}")

    # Print diversity stats
    sources = [item["source"] for item in unique_negatives]
    from collections import Counter

    print("\nSource distribution:")
    for source, count in Counter(sources).items():
        print(f"  {source}: {count}")


if __name__ == "__main__":
    collect_data()
