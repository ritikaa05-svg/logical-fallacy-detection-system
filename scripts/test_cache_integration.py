import asyncio
import time

from backend.app.pipeline.orchestrator import pipeline_orchestrator
from backend.app.services.cache_service import cache_service


async def test_cache():
    # Ensure cache is connected for the test
    await cache_service.connect()

    if not cache_service.is_available:
        print("Redis not available. Skipping cache test.")
        return

    text = "The sun is hot, therefore it is a star."

    # 1. First run (Cache Miss)
    print("--- First Run (Expect Miss) ---")
    start = time.perf_counter()
    result1 = await pipeline_orchestrator.analyze(text, skip_cache=False)
    latency1 = (time.perf_counter() - start) * 1000
    print(f"Cached: {result1.cached}")
    print(f"Latency: {latency1:.2f}ms")

    # Wait a bit for Redis
    await asyncio.sleep(0.5)

    # 2. Second run (Cache Hit)
    print("\n--- Second Run (Expect Hit) ---")
    start = time.perf_counter()
    result2 = await pipeline_orchestrator.analyze(text, skip_cache=False)
    latency2 = (time.perf_counter() - start) * 1000
    print(f"Cached: {result2.cached}")
    print(f"Latency: {latency2:.2f}ms")

    # 3. Third run (Skip Cache)
    print("\n--- Third Run (Skip Cache) ---")
    start = time.perf_counter()
    result3 = await pipeline_orchestrator.analyze(text, skip_cache=True)
    latency3 = (time.perf_counter() - start) * 1000
    print(f"Cached: {result3.cached}")
    print(f"Latency: {latency3:.2f}ms")

    # Cleanup
    await cache_service.disconnect()


if __name__ == "__main__":
    # We use Mock mode to avoid loading heavy models during this test
    import os

    os.environ["LOGISCAN_MOCK_MODE"] = "true"
    asyncio.run(test_cache())
