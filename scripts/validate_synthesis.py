import asyncio

from backend.app.services.llm_service import llm_synthesis_service


async def validate_synthesis():
    test_cases = [
        {
            "text": "You cannot trust his climate argument because he is not a scientist.",
            "fallacy": "ad_hominem",
            "category": "Informal (Relevance)",
        },
        {
            "text": "If it rains, the ground is wet. The ground is wet. Therefore it rained.",
            "fallacy": "affirming_consequent",
            "category": "Formal",
        },
        {"text": "I enjoy pizza on Fridays.", "fallacy": "Non-Fallacious", "category": "None"},
    ]

    print("--- SYNTHESIS VALIDATION ---")
    for case in test_cases:
        print(f"\n[INPUT]: {case['text']}")
        print(f"[TYPE]:  {case['fallacy']}")

        # 1. Test full strategy generation
        strategy, latency = await llm_synthesis_service.generate(
            case["text"], case["category"], [case["fallacy"]], "unknown"
        )
        print(f"[STRATEGY ({latency:.1f}ms)]: {strategy}")

        # 2. Test compact explanation
        compact = await llm_synthesis_service.generate_compact_explanation(
            case["fallacy"], case["fallacy"].title(), case["text"][:10], case["text"]
        )
        print(f"[COMPACT]: {compact}")


if __name__ == "__main__":
    # Note: This requires models or API access.
    # If using local venv, we need to ensure device target is set correctly.
    # Force mock-like behavior if API token missing, or let it try local
    asyncio.run(validate_synthesis())
