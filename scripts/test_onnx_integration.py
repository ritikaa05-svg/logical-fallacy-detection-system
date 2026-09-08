import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.services.unified_classifier import unified_classifier

logging.basicConfig(level=logging.INFO)


async def test_onnx():
    print("Testing ONNX Integration...")
    text = "If it rains, the ground is wet. The ground is wet, therefore it rained."

    # Force load
    unified_classifier.load("models/stage3_v13_classifier")

    if unified_classifier.use_onnx:
        print("✅ ONNX loaded successfully!")
    else:
        print("❌ ONNX NOT loaded.")
        return

    result = await unified_classifier.predict(text)
    print(f"Result: {result['fine_labels'][0]} ({result['coarse_label']})")
    print(f"Latency: {result['latency_ms']:.2f}ms")


if __name__ == "__main__":
    asyncio.run(test_onnx())
