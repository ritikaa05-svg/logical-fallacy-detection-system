import asyncio
import json
import logging
import os
import re
import sys

import pandas as pd
from sklearn.metrics import classification_report

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.pipeline.stage1_gatekeeper import gatekeeper_service
from backend.app.services.structural_parser import structural_parser
from backend.app.services.unified_classifier import unified_classifier

logging.basicConfig(level=logging.ERROR)


async def audit_consistency():
    PipelineOrchestrator()

    # 1. Audit the failing example directly
    input_text = "LogiScan uses a 4-stage neuro-symbolic pipeline to detect logical fallacies in text."
    print(f"🔍 Auditing Failure Case: '{input_text}'")

    # Stage 1 Details
    is_claim, salience, _ = gatekeeper_service.predict(input_text)
    print("\n[Stage 1 Gatekeeper]")
    print(f"  is_logical_claim: {is_claim}")
    print(f"  salience_score:   {salience:.4f}")

    # Structural Parser Details
    struct = await structural_parser.parse_argument(input_text, is_claim)
    print("\n[Structural Parser]")
    print(f"  is_argument: {struct.is_argument}")
    print(f"  premises:    {struct.premises}")
    print(f"  conclusion:  '{struct.conclusion}'")

    # Classifier Details
    res = await unified_classifier.predict(input_text)
    print("\n[Classification Layer]")
    for i in range(min(3, len(res["fine_labels"]))):
        print(f"  {res['fine_labels'][i]}: {res['fine_confidences'][i]:.2%}")

    # 2. Large Scale Consistency Audit
    # We'll use the gold standard eval set + some known factual statements
    with open("data/gold_standard_eval.json") as f:
        data = json.load(f)

    print(f"\n🚀 Running Consistency Audit on {len(data)} samples...")

    audit_results = []
    for item in data:
        text = item["text"]
        true_label = item["fallacy"]

        # Run full pipeline components manually to trace
        is_claim, salience, _ = gatekeeper_service.predict(text)
        struct = await structural_parser.parse_argument(text, is_claim)
        class_res = await unified_classifier.predict(text)

        pred_label = class_res["fine_labels"][0] if class_res["fine_labels"] else "Unknown"

        audit_results.append(
            {
                "text": text,
                "true": true_label,
                "is_claim": is_claim,
                "salience": salience,
                "is_argument": struct.is_argument,
                "has_structure": len(struct.premises) > 0 or struct.conclusion != "",
                "pred": pred_label,
                "prob": class_res["fine_confidences"][0] if class_res["fine_confidences"] else 0.0,
            }
        )

    df = pd.DataFrame(audit_results)

    # 3. Pipeline Contradiction Report
    print("\n" + "=" * 50)
    print("PIPELINE CONTRADICTION REPORT")
    print("=" * 50)

    # Forced Positive Case: Argument=True but Structure=[]
    forced_positives = df[(df["is_argument"] == True) & (df["has_structure"] == False)]
    print(
        f"Samples with is_argument=True AND premises/conclusion=[]: {len(forced_positives)} ({len(forced_positives) / len(df):.1%})"
    )

    # Fallacy classification on missing structure
    fallacy_no_struct = df[
        (df["has_structure"] == False) & (df["pred"] != "factual_statement") & (df["pred"] != "valid_reasoning")
    ]
    print(
        f"Fallacy predicted DESPITE missing structure: {len(fallacy_no_struct)} ({len(fallacy_no_struct) / len(df):.1%})"
    )

    # 4. Calibration & Confusion
    print("\n--- Confusion: factual_statement vs false_cause ---")
    f_vs_c = df[
        ((df["true"] == "factual_statement") & (df["pred"] == "false_cause"))
        | ((df["true"] == "false_cause") & (df["pred"] == "factual_statement"))
    ]
    print(f"Direct Factual/Causal Confusion cases: {len(f_vs_c)}")

    # 5. Decision Policy Evaluation
    print("\n" + "=" * 50)
    print("DECISION POLICY EVALUATION")
    print("=" * 50)

    # Policy: IF no structure THEN factual_statement
    df["pred_policy"] = df.apply(lambda row: "factual_statement" if not row["has_structure"] else row["pred"], axis=1)

    print("Baseline (Original):")
    print(classification_report(df["true"], df["pred"], labels=["factual_statement", "false_cause"], zero_division=0))

    print("\nPolicy Applied (IF no structure THEN factual):")
    print(
        classification_report(
            df["true"], df["pred_policy"], labels=["factual_statement", "false_cause"], zero_division=0
        )
    )

    # 6. Top 50 False Positives for false_cause
    print("\n--- Top False Cause Lexical Triggers (Potential) ---")
    fp_causal = df[(df["true"] != "false_cause") & (df["pred"] == "false_cause")].sort_values("prob", ascending=False)

    # Simple word freq in FPs
    words = []
    for t in fp_causal["text"].head(50):
        words.extend(re.findall(r"\b\w{4,}\b", t.lower()))

    from collections import Counter

    common_fp_words = Counter(words).most_common(10)
    print("Common words in False Cause FPs:")
    for word, count in common_fp_words:
        print(f"  {word}: {count}")

    print("\n✅ Audit Complete.")


if __name__ == "__main__":
    asyncio.run(audit_consistency())
