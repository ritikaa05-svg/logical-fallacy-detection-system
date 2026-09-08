import asyncio
import json

from backend.app.services.unified_classifier import unified_classifier


async def capture_baseline():
    test_cases = [
        "If it rains, the ground is wet. The ground is wet, therefore it rained.",
        "You are wrong because you are a bad person.",
        "I enjoy eating apples in the morning.",
        "All men are mortal. Socrates is a man. Therefore Socrates is mortal.",
    ]

    print("--- BASELINE CAPTURE ---")
    baseline = {}
    for text in test_cases:
        res = unified_classifier.predict(text)
        # Remove latency for comparison
        res.pop("latency_ms", None)
        baseline[text] = res
        print(f"Captured: {text[:30]}...")

    with open("docs/PHASE2_ITEM1_BASELINE.json", "w") as f:
        json.dump(baseline, f, indent=2)
    print("Baseline saved to docs/PHASE2_ITEM1_BASELINE.json")


if __name__ == "__main__":
    import os

    os.environ["LOGISCAN_MOCK_MODE"] = "true"  # Use mock for speed if models not present
    asyncio.run(capture_baseline())
