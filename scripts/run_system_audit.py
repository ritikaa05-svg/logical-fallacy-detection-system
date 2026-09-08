import asyncio
import json
import time

import numpy as np
from sklearn.metrics import f1_score, precision_recall_fscore_support

from backend.app.pipeline.orchestrator import pipeline_orchestrator


async def run_audit():
    # 1. Load Datasets
    with open("data/merged_fallacies.json") as f:
        fallacy_data = json.load(f)

    # Reduced sample size for OOM prevention
    audit_samples = fallacy_data[:15]

    # Add non-fallacies
    non_fallacies = [
        "I like to eat apples.",
        "The sky is blue today.",
        "2 + 2 = 4.",
        "The capital of France is Paris.",
        "Water boils at 100 degrees Celsius.",
    ]

    all_test_data = []
    for s in audit_samples:
        all_test_data.append({"text": s["text"], "is_fallacy": True, "label": s["fallacy"]})
    for s in non_fallacies:
        all_test_data.append({"text": s, "is_fallacy": False, "label": "none"})

    # 2. Run Audit
    print(f"--- STARTING SYSTEM AUDIT ({len(all_test_data)} samples) ---")

    s1_preds, s1_true = [], []
    _s2_preds, _s2_true = [], []
    s3_preds, s3_true = [], []
    s4_status = []
    latencies = []

    # Mock LLM Synthesis to avoid OOM
    from unittest.mock import patch

    with (
        patch("backend.app.services.llm_service.llm_synthesis_service.generate") as mock_gen,
        patch("backend.app.services.llm_service.llm_synthesis_service.generate_unified_breakdown") as mock_ub,
        patch("backend.app.services.llm_service.llm_synthesis_service.generate_compact_explanation") as mock_ce,
    ):
        mock_gen.return_value = ("Mock Strategy", 1.0)
        mock_ub.return_value = []
        mock_ce.return_value = "Mock Explanation"

        for item in all_test_data:
            print(f"Analyzing: {item['text'][:30]}...")
            start_time = time.perf_counter()
            result = await pipeline_orchestrator.analyze(item["text"], skip_cache=True)
            latency = (time.perf_counter() - start_time) * 1000
            latencies.append(latency)

            # Stage 1: Gatekeeper
            s1_true.append(item["is_fallacy"])
            s1_preds.append(result.is_logical_claim)

            if item["is_fallacy"] and result.is_logical_claim:
                # Stage 3: Fine
                s3_true.append(item["label"])
                if result.fine_labels:
                    s3_preds.append(result.fine_labels[0])
                else:
                    s3_preds.append("none")

                # Stage 4: Z3
                if result.z3_status:
                    s4_status.append(result.z3_status)

    # 3. Calculate Metrics
    print("\n--- STAGE 1: GATEKEEPER ---")
    p, r, f, _ = precision_recall_fscore_support(s1_true, s1_preds, average="binary")
    print(f"Precision: {p:.2f}")
    print(f"Recall:    {r:.2f}")
    print(f"F1 Score:  {f:.2f}")

    print("\n--- STAGE 3: FINE-GRAINED ---")
    if s3_true:
        # Align lengths if needed
        min_len = min(len(s3_true), len(s3_preds))
        macro_f1 = f1_score(s3_true[:min_len], s3_preds[:min_len], average="macro", zero_division=0)
        print(f"Macro F1:  {macro_f1:.2f}")
        # Show some sample mismatches
        for i in range(min(5, min_len)):
            if s3_true[i] != s3_preds[i]:
                print(f"  Mismatch: True='{s3_true[i]}' vs Pred='{s3_preds[i]}'")

    print("\n--- PERFORMANCE ---")
    print(f"Avg Latency: {np.mean(latencies):.2f}ms")
    print(f"P95 Latency: {np.percentile(latencies, 95):.2f}ms")

    print("\n--- STAGE 4: FORMAL REASONING ---")
    if s4_status:
        sat_count = s4_status.count("sat")
        unsat_count = s4_status.count("unsat")
        err_count = s4_status.count("error")
        print(f"SAT (Invalid):   {sat_count}")
        print(f"UNSAT (Valid):   {unsat_count}")
        print(f"ERRORS:          {err_count}")


if __name__ == "__main__":
    # Ensure LOGISCAN_MOCK_MODE=false to test real models if possible,
    # but the environment might require mock.
    # We will try to run with real models first.
    # os.environ["LOGISCAN_MOCK_MODE"] = "false"
    asyncio.run(run_audit())
