import asyncio
import json
import logging
import os
import sys
import time

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import _extract_quote_offline
from scripts.prototype_tier2_segmenter import prototype_segmenter

logging.basicConfig(level=logging.ERROR)


def calculate_iou(start1, end1, start2, end2):
    """Calculates Intersection over Union for two spans."""
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0


async def run_benchmark():
    # 1. Load Gold Set
    with open("data/evidence_gold_set.json") as f:
        gold_set = json.load(f)

    print("🚀 Running Evidence Extraction Benchmark (200 samples)...")

    benchmark_results = []

    for item in gold_set:
        text = item["text"]
        fallacy = item["fallacy"]
        exp_start = item["expected_start"]
        exp_end = item["expected_end"]
        exp_quote = item["expected_quote"]

        # --- Current Extractor ---
        start_curr = time.perf_counter()
        quote_curr = _extract_quote_offline(text, fallacy, [])
        latency_curr = (time.perf_counter() - start_curr) * 1000

        c_start = text.find(quote_curr)
        c_end = c_start + len(quote_curr) if c_start != -1 else -1

        # --- Prototype Segmenter ---
        start_proto = time.perf_counter()
        quote_proto, p_start, p_end = prototype_segmenter.extract_evidence(text, fallacy)
        latency_proto = (time.perf_counter() - start_proto) * 1000

        # Metrics
        iou_curr = calculate_iou(exp_start, exp_end, c_start, c_end)
        iou_proto = calculate_iou(exp_start, exp_end, p_start, p_end)

        exact_curr = quote_curr.strip().lower() == exp_quote.strip().lower()
        exact_proto = quote_proto.strip().lower() == exp_quote.strip().lower()

        # Span Precision (Percent of predicted span that is in expected span)
        def get_span_prec(p_s, p_e, e_s, e_e):
            intersection = max(0, min(p_e, e_e) - max(p_s, e_s))
            pred_len = p_e - p_s
            return intersection / pred_len if pred_len > 0 else 0.0

        benchmark_results.append(
            {
                "fallacy": fallacy,
                "iou_curr": iou_curr,
                "iou_proto": iou_proto,
                "exact_curr": exact_curr,
                "exact_proto": exact_proto,
                "prec_curr": get_span_prec(c_start, c_end, exp_start, exp_end),
                "prec_proto": get_span_prec(p_start, p_end, exp_start, exp_end),
                "latency_curr": latency_curr,
                "latency_proto": latency_proto,
            }
        )

    df = pd.DataFrame(benchmark_results)

    print("\n" + "=" * 50)
    print("BENCHMARK REPORT: CURRENT VS PROTOTYPE")
    print("=" * 50)

    metrics = [
        ("IoU", "iou_curr", "iou_proto"),
        ("Exact Match", "exact_curr", "exact_proto"),
        ("Span Precision", "prec_curr", "prec_proto"),
        ("Latency (ms)", "latency_curr", "latency_proto"),
    ]

    for label, curr_col, proto_col in metrics:
        curr_avg = df[curr_col].mean()
        proto_avg = df[proto_col].mean()
        diff = ((proto_avg - curr_avg) / curr_avg) * 100 if curr_avg > 0 else 0
        print(f"{label:15}: Current={curr_avg:.3f} | Proto={proto_avg:.3f} ({diff:+.1f}%)")

    print("\n--- Per-Fallacy Precision Improvement ---")
    for fallacy in df["fallacy"].unique():
        f_df = df[df["fallacy"] == fallacy]
        c_p = f_df["prec_curr"].mean()
        p_p = f_df["prec_proto"].mean()
        print(f"  {fallacy:20}: {c_p:.2f} -> {p_p:.2f} ({p_p - c_p:+.2f})")

    # Deployment Check
    overall_prec = df["prec_proto"].mean()
    print("\nFinal Assessment:")
    print(f"  Overall Precision: {overall_prec:.1%}")

    regressions = []
    for fallacy in df["fallacy"].unique():
        f_df = df[df["fallacy"] == fallacy]
        if f_df["prec_proto"].mean() < f_df["prec_curr"].mean() - 0.05:
            regressions.append(fallacy)

    print(f"  Class Regressions (>5%): {', '.join(regressions) if regressions else 'NONE'}")

    if overall_prec > 0.80 and not regressions:
        print("\n✅ DEPLOYMENT RECOMMENDED: Meets precision and stability criteria.")
    else:
        print("\n❌ DEPLOYMENT DEFERRED: Thresholds not met.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
