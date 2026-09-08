import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.stage1_gatekeeper import gatekeeper_service
from backend.app.services.unified_classifier import unified_classifier

logging.basicConfig(level=logging.INFO)


async def test_full_onnx():
    print("Testing Full ONNX Pipeline (Stage 1 & 2)...")
    text = "If it rains, the ground is wet. The ground is wet, therefore it rained."

    # 1. Warmup / Initial Load
    print("\n--- Warmup / Loading ---")
    # Load through lifecycle manager to simulate production residency
    from backend.app.core.lifecycle import lifecycle_manager

    lifecycle_manager.get_or_load("stage1", gatekeeper_service._load)
    lifecycle_manager.get_or_load("unified_classifier", unified_classifier._load)

    # Perform a warmup inference to prime the ONNX sessions
    print("Performing warmup inference...")
    gatekeeper_service.predict(text)
    await unified_classifier.predict(text)
    print("Warmup complete.")

    # 2. Steady-State Measurement
    print("\n--- Steady-State Measurement ---")

    # Stage 1
    is_logical, salience, s1_latency = gatekeeper_service.predict(text)
    print(f"Stage 1 Salience: {salience:.3f} (Latency: {s1_latency:.2f}ms)")

    # Stage 2
    result = await unified_classifier.predict(text)
    print(f"Stage 2 Result: {result['fine_labels'][0]} ({result['coarse_label']})")
    print(f"Stage 2 Latency: {result['latency_ms']:.2f}ms")

    total_latency = s1_latency + result["latency_ms"]
    print(f"\nTotal Pipeline Latency (Stage 1 + 2): {total_latency:.2f}ms")


if __name__ == "__main__":
    asyncio.run(test_full_onnx())
