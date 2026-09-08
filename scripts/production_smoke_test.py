import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.core.lifecycle import lifecycle_manager
from backend.app.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.ERROR)

TEST_CASES = [
    {
        "id": "Case A - Product Description",
        "text": "LogiScan uses a 4-stage neuro-symbolic pipeline to detect logical fallacies in text.",
    },
    {"id": "Case B - Definition", "text": "A logical fallacy is a flaw in reasoning that weakens an argument."},
    {
        "id": "Case C - Straw Man",
        "text": "Person A: We should build more bike lanes. Person B: So you want to ban all cars and force everyone to walk?",
    },
    {"id": "Case D - Ad Hominem", "text": "You're wrong because you're an idiot."},
    {
        "id": "Case E - Valid Reasoning",
        "text": "If it rains, the ground gets wet. It is raining. Therefore the ground gets wet.",
    },
]


async def run_smoke_test():
    # Force clear models
    print("🧹 Clearing lifecycle cache...")
    lifecycle_manager.evict_all()

    orchestrator = PipelineOrchestrator()
    results = {}

    print("🚀 Running Production Smoke Test...")

    for case in TEST_CASES:
        print(f"\n--- {case['id']} ---")
        res = await orchestrator.analyze(case["text"], skip_cache=True)

        # Extract key fields for summary

        print(f"  Salience: {res.salience_score:.4f}")
        print(f"  Coarse:   {res.coarse_category}")
        print(f"  Fine:     {res.fine_labels[0] if res.fine_labels else 'None'}")

        # Convert to serializable dict
        results[case["id"]] = res.model_dump(mode="json")

    with open("docs/PRODUCTION_SMOKE_TEST_RESULTS.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n✅ Smoke test complete. Results saved to docs/PRODUCTION_SMOKE_TEST_RESULTS.json")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
