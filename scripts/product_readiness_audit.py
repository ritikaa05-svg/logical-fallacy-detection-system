import asyncio
import json
import logging
import os
import sys

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.ERROR)


async def audit_product_quality():
    orchestrator = PipelineOrchestrator()

    # 1. Load Gold Set (500 samples)
    with open("data/gold_standard_eval.json") as f:
        data = json.load(f)

    print(f"🚀 Running Product Readiness Audit on {len(data)} samples...")

    audit_results = []
    for item in data[:100]:  # Sample 100 for precision audit
        text = item["text"]
        true_label = item["fallacy"]

        # Fresh inference with explanations enabled to audit highlighting
        res = await orchestrator.analyze(text, skip_cache=True, include_explanations=True)

        # 1. Quote Precision Audit
        # Check if the extracted "fallacy quote" actually contains the offending claim
        # Since we don't have human ground truth for "perfect quote", we check for:
        # a) Is it empty? b) Is it the whole text (failed extraction)? c) Does it align with salient spans?

        extracted_fallacy = res.fallacies[0] if res.fallacies else None
        quote = extracted_fallacy.quote if extracted_fallacy else ""

        # 2. Highlighting Alignment Audit
        # Verify if returned span offsets align with the original text
        highlight_errors = []
        for ann in res.annotations:
            for span in ann.spans:
                actual_text_at_offsets = text[span.start : span.end]
                if span.text.lower() not in actual_text_at_offsets.lower():
                    highlight_errors.append(f"Mismatch: '{span.text}' vs '{actual_text_at_offsets}'")

        audit_results.append(
            {
                "text": text,
                "true_label": true_label,
                "pred_label": res.fine_labels[0] if res.fine_labels else "None",
                "quote": quote,
                "quote_len": len(quote),
                "text_len": len(text),
                "is_whole_text": quote == text,
                "is_empty": not quote,
                "highlight_error_count": len(highlight_errors),
                "annotations_count": len(res.annotations),
            }
        )

    df = pd.DataFrame(audit_results)

    print("\n" + "=" * 50)
    print("PRODUCT READINESS: QUOTE & HIGHLIGHT AUDIT")
    print("=" * 50)

    # Quote Precision
    print(f"Total Samples Audited: {len(df)}")
    print(f"Successful Quote Extraction: {len(df[~df['is_whole_text'] & ~df['is_empty']])}")
    print(
        f"Failed Extraction (Whole Text): {len(df[df['is_whole_text']])} ({len(df[df['is_whole_text']]) / len(df):.1%})"
    )
    print(f"Failed Extraction (Empty): {len(df[df['is_empty']])} ({len(df[df['is_empty']]) / len(df):.1%})")

    # Highlight Integrity
    total_errors = df["highlight_error_count"].sum()
    print(f"Total Highlight Alignment Errors: {total_errors}")
    samples_with_errors = len(df[df["highlight_error_count"] > 0])
    print(f"Samples with Broken Highlighting: {samples_with_errors} ({samples_with_errors / len(df):.1%})")

    # Explanation Quality (Static vs Dynamic)
    print("\n--- Feature availability ---")
    print(f"Avg Annotations per sample: {df['annotations_count'].mean():.2f}")

    # Trace specific broken example if exists
    if samples_with_errors > 0:
        err_case = df[df["highlight_error_count"] > 0].iloc[0]
        print("\n--- Broken Highlight Trace ---")
        print(f"Text:  {err_case['text'][:100]}...")
        print("Error: Highlighting offsets are misaligned.")

    print("\n✅ Audit Complete.")


if __name__ == "__main__":
    asyncio.run(audit_product_quality())
