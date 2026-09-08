import asyncio

from backend.app.services.z3_service import z3_service


async def validate_z3():
    test_cases = [
        {"name": "Valid Syllogism", "text": "All men are mortal. Socrates is a man. Therefore Socrates is mortal."},
        {
            "name": "Invalid (Affirming Consequent)",
            "text": "If it rains, the ground is wet. The ground is wet. Therefore it rained.",
        },
        {
            "name": "Invalid (Denying Antecedent)",
            "text": "If it rains, the ground is wet. It's not raining. Therefore the ground isn't wet.",
        },
        {
            "name": "Simple Implication (Valid)",
            "text": "If the button is pressed, the light turns on. The button is pressed. Therefore the light is on.",
        },
    ]

    print("--- Z3 VALIDATION ---")
    for case in test_cases:
        print(f"\n[TEST]: {case['name']}")
        print(f"[TEXT]: {case['text']}")

        # We'll likely hit regex fallback in this environment
        result = await z3_service.analyze(case["text"])

        print(f"[STATUS]: {result.status}")
        print(f"[CONFIDENCE]: {result.parsing_confidence:.2f}")
        if result.smt_script:
            print("[SMT SCRIPT]:")
            print(result.smt_script)
        if result.error_message:
            print(f"[ERROR]: {result.error_message}")


if __name__ == "__main__":
    asyncio.run(validate_z3())
