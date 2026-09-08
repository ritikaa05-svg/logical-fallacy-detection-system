import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.services.z3_service import z3_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Mock LLM to force regex fallback
async def mock_llm_to_smt(text):
    return "", 0.0


# Temporarily replace llm_to_smt in z3_service to test regex logic
import backend.app.services.z3_service

backend.app.services.z3_service.llm_to_smt = mock_llm_to_smt

test_cases = [
    {
        "name": "Affirming the Consequent (Standard)",
        "text": "If it rains, the ground is wet. The ground is wet, therefore it rained.",
        "expected_status": "sat",  # Z3 'sat' means invalid argument (counter-example exists)
    },
    {
        "name": "Denying the Antecedent (Standard)",
        "text": "If it rains, the ground is wet. It is not raining, therefore the ground is not wet.",
        "expected_status": "sat",
    },
    {
        "name": "Valid Syllogism (Modus Ponens)",
        "text": "If it rains, the ground is wet. It is raining, therefore the ground is wet.",
        "expected_status": "unsat",  # Z3 'unsat' means valid argument (no counter-example)
    },
    {
        "name": "Affirming Consequent (Varied Phrasing)",
        "text": "Success leads to happiness. John is happy, so he must be successful.",
        "expected_status": "sat",
    },
    {
        "name": "Denying Antecedent (Varied Phrasing)",
        "text": "If you study hard, you will pass. You didn't study hard, so you won't pass.",
        "expected_status": "sat",
    },
    {
        "name": "Circular Reasoning (Begging the Question)",
        "text": "God exists because the Bible says so, and the Bible is true because God wrote it.",
        "expected_status": "sat",  # Or unknown, regex might struggle here
    },
    {
        "name": "False Cause (Temporal)",
        "text": "I wore my lucky socks and we won the game. Therefore, the socks caused the win.",
        "expected_status": "sat",
    },
]


async def audit_formal_logic():
    print("🚀 Auditing Regex-based Formal Logic Integrity...")
    print("-" * 50)

    for case in test_cases:
        print(f"\nCase: {case['name']}")
        print(f"Text: {case['text']}")

        result = await z3_service.analyze(case["text"])

        print(f"Status: {result.status}")
        print(f"Confidence: {result.parsing_confidence:.2f}")
        if result.smt_script:
            print("SMT Script:")
            print(result.smt_script)

        match = "✅" if result.status == case["expected_status"] else "❌"
        print(f"Result Match: {match} (Expected: {case['expected_status']})")


if __name__ == "__main__":
    asyncio.run(audit_formal_logic())
