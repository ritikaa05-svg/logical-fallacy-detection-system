import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_overlap(pred: str, gold: str) -> float:
    """Calculates word-level overlap (Jaccard similarity) between two strings."""
    if not pred or not gold:
        return 1.0 if not pred and not gold else 0.0

    pred_words = set(pred.lower().replace(".", "").replace(",", "").split())
    gold_words = set(gold.lower().replace(".", "").replace(",", "").split())

    if not gold_words:
        return 0.0

    intersection = pred_words.intersection(gold_words)
    union = pred_words.union(gold_words)

    return len(intersection) / len(union)


def calculate_set_overlap(pred_list: list[str], gold_list: list[str]) -> float:
    """Calculates best-match overlap between two sets of strings (premises)."""
    if not pred_list or not gold_list:
        return 1.0 if not pred_list and not gold_list else 0.0

    total_overlap = 0.0
    for gold in gold_list:
        best_match = max([calculate_overlap(pred, gold) for pred in pred_list]) if pred_list else 0.0
        total_overlap += best_match

    return total_overlap / len(gold_list)


async def evaluate_phase5():
    orchestrator = PipelineOrchestrator()

    eval_path = "data/phase5_eval.json"
    if not os.path.exists(eval_path):
        print(f"❌ Eval file not found: {eval_path}")
        return

    with open(eval_path) as f:
        test_cases = json.load(f)

    results = []

    print(f"🚀 Starting Phase 5 Evaluation on {len(test_cases)} cases...")

    for case in test_cases:
        text = case["text"]
        print(f"\nAnalyzing: {text}")

        # Run inference
        try:
            res = await orchestrator.analyze(text, skip_cache=True)
            struct = res.argument_structure
        except Exception as e:
            print(f"❌ Pipeline error: {e}")
            continue

        if not struct:
            print("❌ No argument structure returned.")
            continue

        # Metrics
        is_arg_correct = struct.is_argument == case["is_argument"]
        premise_score = calculate_set_overlap(struct.premises, case["premises"])
        conclusion_score = calculate_overlap(struct.conclusion, case["conclusion"])
        reasoning_correct = struct.reasoning_type.lower() == case["reasoning_type"].lower()

        results.append(
            {
                "is_arg_correct": is_arg_correct,
                "premise_score": premise_score,
                "conclusion_score": conclusion_score,
                "reasoning_correct": reasoning_correct,
            }
        )

        print(f"  - Argument Detection: {'✅' if is_arg_correct else '❌'}")
        print(f"  - Premise Score: {premise_score:.2f}")
        print(f"  - Conclusion Score: {conclusion_score:.2f}")
        print(f"  - Reasoning Type: {'✅' if reasoning_correct else '❌'} ({struct.reasoning_type})")

    if not results:
        print("No results to aggregate.")
        return

    # Aggregate
    avg_is_arg = sum(r["is_arg_correct"] for r in results) / len(results)
    avg_premise = sum(r["premise_score"] for r in results) / len(results)
    avg_conclusion = sum(r["conclusion_score"] for r in results) / len(results)
    avg_reasoning = sum(r["reasoning_correct"] for r in results) / len(results)

    print("\n" + "=" * 40)
    print("PHASE 5 AGGREGATE METRICS")
    print("=" * 40)
    print(f"Argument Detection Accuracy: {avg_is_arg:.2%}")
    print(f"Premise Extraction (Overlap): {avg_premise:.2%}")
    print(f"Conclusion Identification:   {avg_conclusion:.2%}")
    print(f"Reasoning Type Accuracy:     {avg_reasoning:.2%}")
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(evaluate_phase5())
