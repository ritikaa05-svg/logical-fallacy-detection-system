"""Per-fallacy evidence extraction audit using benchmark_dataset.json."""

import asyncio
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import _extract_quote_offline


def compute_iou(s1: str, s2: str) -> float:
    set1 = set(s1.lower().split())
    set2 = set(s2.lower().split())
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


async def audit_evidence_extraction():
    with open("backend/tests/benchmarks/benchmark_dataset.json") as f:
        data = json.load(f)

    samples = [d for d in data if d["type"] == "argument" and "expected_quote" in d]

    print(f"Evidence extraction audit on {len(samples)} argument samples from benchmark_dataset.json\n")

    by_fallacy: dict[str, list[dict]] = defaultdict(list)

    for item in samples:
        text = item["text"]
        fallacy = item["expected_fallacy"]
        expected_quote = item["expected_quote"]

        extracted, _, _ = _extract_quote_offline(text, fallacy, [])

        exact = extracted.strip().lower() == expected_quote.strip().lower()
        iou = compute_iou(extracted, expected_quote)
        whole_text = extracted.strip() == text.strip()

        by_fallacy[fallacy].append(
            {
                "id": item["id"],
                "exact_match": exact,
                "iou": iou,
                "whole_text_fallback": whole_text,
            }
        )

    fallacies = sorted(by_fallacy.keys())

    print(f"{'Fallacy':<25} {'Count':>5} {'Exact%':>7} {'Avg IoU':>7} {'Whole%':>7}")
    print("-" * 55)

    all_exact = []
    all_iou = []
    all_whole = []

    for fallacy in fallacies:
        entries = by_fallacy[fallacy]
        n = len(entries)
        exact_rate = np.mean([e["exact_match"] for e in entries])
        avg_iou = np.mean([e["iou"] for e in entries])
        whole_rate = np.mean([e["whole_text_fallback"] for e in entries])

        print(f"{fallacy:<25} {n:>5} {exact_rate:>7.1%} {avg_iou:>7.1%} {whole_rate:>7.1%}")
        all_exact.extend(e["exact_match"] for e in entries)
        all_iou.extend(e["iou"] for e in entries)
        all_whole.extend(e["whole_text_fallback"] for e in entries)

    print("-" * 55)
    print(
        f"{'OVERALL':<25} {len(all_exact):>5} "
        f"{np.mean(all_exact):>7.1%} {np.mean(all_iou):>7.1%} "
        f"{np.mean(all_whole):>7.1%}"
    )

    failures = [(e["id"], fallacy) for fallacy in fallacies for e in by_fallacy[fallacy] if not e["exact_match"]]
    if failures:
        print(f"\nFailed samples ({len(failures)}):")
        for fid, fl in failures:
            print(f"  {fid} ({fl})")
    else:
        print(f"\nAll {len(all_exact)} samples passed exact match!")


if __name__ == "__main__":
    asyncio.run(audit_evidence_extraction())
