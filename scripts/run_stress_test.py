import asyncio
import json
from collections import Counter
from pathlib import Path

import aiohttp

API_URL = "http://localhost:8000/api/v1/analyze"


async def analyze_text(session, text):
    try:
        async with session.post(API_URL, json={"text": text, "skip_cache": True}) as response:
            if response.status == 200:
                return await response.json()
            return None
    except Exception as e:
        print(f"Error analyzing text: {e}")
        return None


async def run_test():
    data_path = Path("data/adversarial_stress_test.json")
    if not data_path.exists():
        print(f"Error: {data_path} not found. Run build_stress_test.py first.")
        return

    with open(data_path) as f:
        examples = json.load(f)

    print(f"🚀 Running LogiScan Stress Test on {len(examples)} examples...")

    results = []
    async with aiohttp.ClientSession() as session:
        # Run in batches to avoid overwhelming the server
        batch_size = 5
        for i in range(0, len(examples), batch_size):
            batch = examples[i : i + batch_size]
            tasks = [analyze_text(session, ex["text"]) for ex in batch]
            batch_results = await asyncio.gather(*tasks)

            for ex, res in zip(batch, batch_results):
                if res:
                    results.append({"example": ex, "prediction": res})
            print(f"Progress: {min(i + batch_size, len(examples))}/{len(examples)}")

    # Analysis
    stats = {}
    total_fp = 0

    for res in results:
        ex = res["example"]
        pred = res["prediction"]
        cat = ex["category"]

        if cat not in stats:
            stats[cat] = {"total": 0, "fp": 0, "confidences": []}

        stats[cat]["total"] += 1

        # A false positive is when Stage 3 returns any fallacy label with confidence > threshold (e.g. 0.5)
        is_fp = False
        if pred.get("fine_labels"):
            # Check if top prediction has significant confidence
            if pred.get("confidence_scores") and pred["confidence_scores"][0] > 0.5:
                is_fp = True

        if is_fp:
            stats[cat]["fp"] += 1
            total_fp += 1

        # Record confidence of the "fallacy" detection
        if pred.get("confidence_scores"):
            stats[cat]["confidences"].append(pred["confidence_scores"][0])
        else:
            stats[cat]["confidences"].append(0.0)

    # Report
    print("\n" + "=" * 50)
    print("LOGISCAN ADVERSARIAL STRESS TEST REPORT")
    print("=" * 50)
    print(f"Total Examples: {len(results)}")
    print(f"Overall False Positive Rate: {total_fp / len(results):.2%}")
    print("\nBreakdown by Category:")

    for cat, data in stats.items():
        fp_rate = data["fp"] / data["total"]
        avg_conf = sum(data["confidences"]) / len(data["confidences"])
        mimics = next(ex["mimicked_fallacy"] for ex in examples if ex["category"] == cat)

        print(f"\n[{cat.upper()}] (Mimics: {mimics})")
        print(f"  FP Rate:      {fp_rate:.2%}")
        print(f"  Avg FP Conf:  {avg_conf:.2%}")
        print(f"  Valid Ratio:  {1 - fp_rate:.2%}")

    # Identify stage contributions to errors
    print("\n" + "=" * 50)
    print("ERROR DIAGNOSIS")
    print("=" * 50)

    fp_examples = [
        r for r in results if r["prediction"].get("fine_labels") and r["prediction"]["confidence_scores"][0] > 0.5
    ]
    if fp_examples:
        print(f"Analyzing {len(fp_examples)} False Positives...")
        stage_errors = Counter()
        for res in fp_examples:
            pred = res["prediction"]
            # If Stage 2 predicted a fallacy but it's valid
            if pred.get("coarse_category") and pred["coarse_category"] != "Non-Fallacious":
                stage_errors["Stage 2 (Coarse)"] += 1
            # If Z3 flagged it as SAT (invalid) but it's actually valid
            if pred.get("z3_status") == "sat":
                stage_errors["Stage 4 (Z3)"] += 1
            # Stage 3 is always the one providing the fine labels
            stage_errors["Stage 3 (Fine)"] += 1

        for stage, count in stage_errors.items():
            print(f"  {stage} contributed to {count} errors")
    else:
        print("No significant false positives detected. Excellent!")


if __name__ == "__main__":
    asyncio.run(run_test())
