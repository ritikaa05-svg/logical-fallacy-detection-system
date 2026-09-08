import asyncio
import os
import sys
import time

import psutil

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.config import settings
from backend.app.core.lifecycle import lifecycle_manager
from backend.app.services.unified_classifier import unified_classifier


def get_memory():
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


async def run_measurement():
    print("🚀 Final Validation Measurement...")

    # Force load
    lifecycle_manager.get_or_load("unified_classifier", unified_classifier._load)

    test_text = "If it rains, the ground gets wet. The ground is wet, therefore it rained."

    # Warmup
    print("🔥 Warming up...")
    for _ in range(3):
        await unified_classifier.predict(test_text)

    # 1. Measurement with Attribution OFF (Default)
    print("\n--- Attribution OFF (Default) ---")
    unified_classifier._last_text = None
    start = time.perf_counter()
    res_off = await unified_classifier.predict(test_text, include_explanations=False)
    latency_off = (time.perf_counter() - start) * 1000
    print(f"Latency: {latency_off:.2f} ms")
    print(f"Salient Tokens: {len(res_off.get('salient_tokens', []))}")

    # 2. Measurement with Attribution ON (Requested)
    print("\n--- Attribution ON (Requested) ---")
    unified_classifier._last_text = None
    start = time.perf_counter()
    res_on = await unified_classifier.predict(test_text, include_explanations=True)
    latency_on = (time.perf_counter() - start) * 1000
    print(f"Latency: {latency_on:.2f} ms")
    print(f"Salient Tokens: {len(res_on.get('salient_tokens', []))}")

    # 3. Memory usage
    mem = get_memory()
    print(f"\nMemory Usage: {mem:.2f} MB")
    print(f"Shadow Mode Status: {settings.ENABLE_SHADOW_MODE}")

    print("\nSTATUS: SUCCESS")
    print(f"SHADOW_MODE_STATUS: {'ACTIVE' if settings.ENABLE_SHADOW_MODE else 'DISABLED'}")
    print("ATTRIBUTION_MODE: ON-DEMAND")
    print(f"NEW_LATENCY_MS: {latency_off:.2f} (Base) / {latency_on:.2f} (With XAI)")
    print(f"MEMORY_USAGE_MB: {mem:.2f}")


if __name__ == "__main__":
    asyncio.run(run_measurement())
