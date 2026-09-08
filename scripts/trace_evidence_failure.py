import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from scripts.prototype_tier2_segmenter import prototype_segmenter


async def trace_failure():
    with open("data/evidence_gold_set.json") as f:
        gold_set = json.load(f)

    fc_samples = [d for d in gold_set if d["fallacy"] == "false_cause"]

    for item in fc_samples[:5]:
        text = item["text"]
        exp = item["expected_quote"]
        pred, p_s, p_e = prototype_segmenter.extract_evidence(text, "false_cause")

        print(f"\nText: {text[:100]}...")
        print(f"Expected: {exp}")
        print(f"Predicted: {pred}")
        if exp.strip().lower() not in pred.strip().lower() and pred.strip().lower() not in exp.strip().lower():
            print("❌ COMPLETE MISMATCH")


if __name__ == "__main__":
    asyncio.run(trace_failure())
