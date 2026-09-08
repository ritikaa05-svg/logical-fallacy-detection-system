import asyncio
import json
import logging

from backend.app.core.logger import setup_logging
from backend.app.pipeline.orchestrator import pipeline_orchestrator


async def test_pipeline():
    setup_logging()
    logger = logging.getLogger(__name__)

    test_text = "If it rains, the ground gets wet. The ground is wet, therefore it rained."
    logger.info(f"Testing pipeline with: {test_text}")

    try:
        result = await pipeline_orchestrator.analyze(test_text)
        print("\nPipeline Result:")
        print(json.dumps(result.model_dump(), indent=2))

        # Test multi-turn
        history = [
            {"role": "user", "text": "All scientists believe in gravity."},
            {"role": "assistant", "text": "That is generally true."},
            {"role": "user", "text": "Well, no TRUE scientist would doubt it."},
        ]
        logger.info("Testing pipeline with history...")
        result_history = await pipeline_orchestrator.analyze(
            text="Well, no TRUE scientist would doubt it.", history=history
        )
        print("\nPipeline Result with History:")
        print(json.dumps(result_history.model_dump(), indent=2))

    except Exception as e:
        logger.error(f"Pipeline test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_pipeline())
