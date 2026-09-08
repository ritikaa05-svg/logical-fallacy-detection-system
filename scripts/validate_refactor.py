import asyncio
import json
import os

from backend.app.services.unified_classifier import unified_classifier


async def validate_refactor():
    with open("docs/PHASE2_ITEM1_BASELINE.json") as f:
        baseline = json.load(f)

    print("--- REFACTOR VALIDATION ---")
    match_count = 0
    total = len(baseline)

    for text, expected in baseline.items():
        print(f"\nTesting: {text[:40]}...")
        actual = unified_classifier.predict(text)
        actual.pop("latency_ms", None)  # Don't compare latency

        # Check if actual matches expected (deep compare)
        if json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True):
            print("✅ MATCH")
            match_count += 1
        else:
            print("❌ MISMATCH")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")

    print(f"\nResult: {match_count}/{total} cases matched.")
    if match_count == total:
        print("REFACOR SUCCESSFUL")
    else:
        print("REFACTOR FAILED: Behavior divergence detected.")


if __name__ == "__main__":
    os.environ["LOGISCAN_MOCK_MODE"] = "true"
    asyncio.run(validate_refactor())
