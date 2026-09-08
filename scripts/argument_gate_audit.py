import asyncio
import json
import logging
import os
import sys

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.services.structural_parser import structural_parser

logging.basicConfig(level=logging.ERROR)


async def audit_gate_impact():
    orchestrator = PipelineOrchestrator()

    # 1. Failure Case Investigation
    texts = [
        "Person A: We should build more bike lanes. Person B: So you want to ban all cars and force everyone to walk?",
        "If we let refugees into the country, then crime will skyrocket.",
        "You are just saying that because you are a corporate shill.",
    ]

    print("🔍 Auditing Targeted Failure Cases...")
    for text in texts:
        res = await orchestrator.analyze(text, skip_cache=True)
        print(f"\nText: {text[:60]}...")
        print(f"  is_argument: {res.argument_structure.is_argument if res.argument_structure else 'None'}")
        print(f"  Pred label:  {res.fine_labels[0] if res.fine_labels else 'None'}")
        print(f"  Reason:      {res.correction_strategy[:60]}...")

    # 2. Dataset Distribution Audit
    with open("data/gold_standard_eval.json") as f:
        data = json.load(f)

    print(f"\n🚀 Running Gate Audit on {len(data)} gold samples...")

    results = []
    for item in data:
        text = item["text"]
        true_label = item["fallacy"]

        # We need to trace WHY the parser failed
        # Current parser returns ArgumentIntelligenceResult even on failure
        # with is_argument=False

        # We'll use a modified trace to detect the failure type
        start_time = asyncio.get_event_loop().time()
        struct = await structural_parser.parse_argument(text, True)  # Force True for audit
        latency = (asyncio.get_event_loop().time() - start_time) * 1000

        res = await orchestrator.analyze(text, skip_cache=True)
        pred_label = res.fine_labels[0] if res.fine_labels else "None"

        results.append(
            {
                "text": text,
                "true": true_label,
                "pred": pred_label,
                "is_argument": struct.is_argument,
                "has_premises": len(struct.premises) > 0,
                "has_conclusion": bool(struct.conclusion),
                "latency": latency,
            }
        )

    df = pd.DataFrame(results)

    # 3. Distribution Metrics
    print("\n" + "=" * 50)
    print("GATE IMPACT METRICS")
    print("=" * 50)

    total = len(df)
    bypassed = len(df[df["pred"] == "factual_statement"])
    print(f"Total Samples: {total}")
    print(f"Samples Bypassed (factual_statement): {bypassed} ({bypassed / total:.1%})")

    # Analysis of is_argument=False reasons
    # Since we know local LLM/API is failing in this env:
    fail_rate = len(df[df["is_argument"] == False])
    print(f"Parser 'is_argument=False' rate: {fail_rate / total:.1%}")

    # 4. Fallacy Masking Report
    print("\n--- Fallacy Masking (False Negatives) ---")
    masking = (
        df[df["true"] != "factual_statement"]
        .groupby("true")["pred"]
        .apply(lambda x: (x == "factual_statement").mean())
        .sort_values(ascending=False)
    )
    print("Percent of true fallacies masked by Gate:")
    print(masking.head(10))

    # 5. Logic Score Audit
    print("\n--- Logic Score Default Audit ---")
    print(f"Avg Logic Score when bypassed: {df[df['pred'] == 'factual_statement'].index.size > 0}")

    print("\n✅ Audit Complete.")


if __name__ == "__main__":
    asyncio.run(audit_gate_impact())
