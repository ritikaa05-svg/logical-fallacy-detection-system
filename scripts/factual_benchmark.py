import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.stage1_gatekeeper import gatekeeper_service

# Technical / Documentation descriptions that should NOT trigger a logical claim
FACTUAL_DESCRIPTIONS = [
    "LogiScan uses a 4-stage neuro-symbolic pipeline to detect logical fallacies in text.",
    "The software architecture includes a FastAPI backend and a Streamlit frontend.",
    "This model was trained on 10,786 samples using the DeBERTa-v3-small architecture.",
    "The system documentation is available in the docs folder of the repository.",
    "User authentication is managed via OAuth 2.0 with JWT tokens.",
    "The database schema consists of three tables: users, reports, and logs.",
    "Click the blue button to start the installation process.",
    "The server is currently running on port 8000.",
    "This script exports the trained model to ONNX format for efficient CPU inference.",
    "Version 1.2.0 includes several performance optimizations and bug fixes.",
]


async def run_benchmark():
    print("🚀 Running Factual Description Benchmark (Stage 1)...")
    print("-" * 50)

    triggers = 0
    total = len(FACTUAL_DESCRIPTIONS)

    for text in FACTUAL_DESCRIPTIONS:
        is_logical, salience, _ = gatekeeper_service.predict(text)
        status = "❌ TRIGGERED" if is_logical else "✅ PASSED"
        if is_logical:
            triggers += 1
        print(f"[{status}] Salience: {salience:.4f} | Text: {text[:60]}...")

    fpr = (triggers / total) * 100
    print("-" * 50)
    print(f"Results: {triggers}/{total} factual descriptions triggered a logical claim.")
    print(f"Factual False Positive Rate (FPR): {fpr:.1f}%")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
