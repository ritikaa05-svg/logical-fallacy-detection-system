import json
import os
import sys
import time

import torch

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.config import settings
from backend.app.core.lifecycle import lifecycle_manager
from backend.app.schemas.inference import InferenceResult
from backend.app.services.unified_classifier import unified_classifier


async def run_audit():
    print("🚀 Starting Production Latency Audit...")

    # 1. Check Configuration
    print(f"   - Authoritative Model Path: {settings.STAGE2_MODEL_PATH}")
    print(f"   - Shadow Mode Enabled: {settings.ENABLE_SHADOW_MODE}")
    print(f"   - Shadow Model Path: {settings.SHADOW_MODEL_PATH}")

    # Force load
    svc = lifecycle_manager.get_or_load("unified_classifier", unified_classifier._load)

    # Check for legacy model presence in memory
    legacy_loaded = svc.model_s2 is not None or svc.model_s3 is not None
    print(f"   - Legacy Fallback Models Loaded: {legacy_loaded}")

    test_text = "If it rains, the ground gets wet. The ground is wet, therefore it rained."

    # --- Measure Latency ---

    # Tokenization
    start = time.perf_counter()
    inputs = svc.tokenizer(test_text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(svc.device)
    tokenization_ms = (time.perf_counter() - start) * 1000

    # Model Inference
    start = time.perf_counter()
    with torch.no_grad():
        outputs = svc.model(**inputs)
        if svc.is_single_head:
            pass
        else:
            outputs.get("coarse_logits")
            outputs.get("fine_logits")
    inference_ms = (time.perf_counter() - start) * 1000

    # Attribution / Explainability
    target_class = 0  # ad_hominem or similar
    from backend.app.services.explainability import compute_attributions

    start = time.perf_counter()
    try:
        _ = compute_attributions(svc.model, svc.tokenizer, test_text, target_class)
        attribution_ms = (time.perf_counter() - start) * 1000
    except Exception as e:
        print(f"   - Attribution failed: {e}")
        attribution_ms = 0.0

    # Post-processing (Label mapping, sorting)
    start = time.perf_counter()
    if svc.is_single_head:
        f_probs = torch.softmax(outputs.logits, dim=-1)[0]
        id2label = {int(k): v for k, v in svc.model.config.id2label.items()}
        top_idx = torch.argmax(f_probs).item()
        top_label = id2label[top_idx]
        svc.SHADOW_COARSE_MAP.get(top_label, "Unknown")
        c_probs = torch.zeros(len(svc.coarse_labels), device=svc.device)
    else:
        c_probs = torch.softmax(outputs.get("coarse_logits"), dim=-1)[0]
        f_probs = torch.softmax(outputs.get("fine_logits"), dim=-1)[0]

    # Rest of process_logits minus attribution
    c_idx = torch.argmax(c_probs).item()
    f_scores, f_indices = torch.sort(f_probs, descending=True)
    _ = {
        "coarse_label": svc.coarse_labels[c_idx] if c_idx < len(svc.coarse_labels) else "Unknown",
        "coarse_confidence": c_probs[c_idx].item(),
        "fine_labels": [svc.fine_labels[i.item()] for i in f_indices[:3]],
        "fine_confidences": [s.item() for s in f_scores[:3]],
    }
    post_processing_ms = (time.perf_counter() - start) * 1000

    # Pipeline Orchestration (predict call overhead)
    start = time.perf_counter()
    _ = await unified_classifier.predict(test_text)
    total_predict_ms = (time.perf_counter() - start) * 1000
    orchestration_ms = max(0, total_predict_ms - (tokenization_ms + inference_ms + attribution_ms + post_processing_ms))

    # API Serialization
    # Create a full mock result
    full_result = {
        "input_text": test_text,
        "is_logical_claim": True,
        "salience_score": 0.95,
        "coarse_category": "Formal",
        "fine_labels": ["affirming_consequent"],
        "confidence_scores": [0.96],
        "salient_tokens": [{"token": "If", "score": 0.5, "start": 0, "end": 2}],
        "logic_score": 0.5,
        "total_latency_ms": total_predict_ms,
    }
    obj = InferenceResult.model_validate(full_result)
    start = time.perf_counter()
    _ = obj.model_dump_json()
    serialization_ms = (time.perf_counter() - start) * 1000

    # --- Results ---

    total = tokenization_ms + inference_ms + attribution_ms + post_processing_ms + orchestration_ms + serialization_ms

    breakdown = [
        ("Tokenization", tokenization_ms),
        ("Model Inference", inference_ms),
        ("Attribution/Explainability", attribution_ms),
        ("Post-processing", post_processing_ms),
        ("Pipeline Orchestration", orchestration_ms),
        ("API Serialization", serialization_ms),
    ]

    # Identify largest contributor
    largest_contributor = max(breakdown, key=lambda x: x[1])

    report = {
        "legacy_model_status": "LOADED" if legacy_loaded else "NOT LOADED",
        "shadow_mode_active": settings.ENABLE_SHADOW_MODE,
        "latency_breakdown": [],
        "largest_contributor": largest_contributor[0],
        "total_measured_latency_ms": total,
    }

    cumulative = 0.0
    for name, ms in breakdown:
        cumulative += ms
        report["latency_breakdown"].append(
            {
                "component": name,
                "latency_ms": ms,
                "percentage": (ms / total) * 100 if total > 0 else 0,
                "cumulative_ms": cumulative,
            }
        )

    print("\n--- Latency Breakdown ---")
    print(f"{'Component':<30} | {'ms':<10} | {'%':<5} | {'Cumulative':<10}")
    print("-" * 65)
    for entry in report["latency_breakdown"]:
        print(
            f"{entry['component']:<30} | {entry['latency_ms']:<10.2f} | {entry['percentage']:<5.1f}% | {entry['cumulative_ms']:<10.2f}"
        )

    print(f"\nLargest Contributor: {report['largest_contributor']}")
    print(f"Legacy Model Loaded: {report['legacy_model_status']}")
    print(f"Shadow Mode Active: {report['shadow_mode_active']}")

    with open("docs/LATENCY_AUDIT_REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\n✅ Audit complete. Report saved to docs/LATENCY_AUDIT_REPORT.json")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_audit())
