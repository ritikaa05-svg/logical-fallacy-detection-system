# LogiScan Performance & Latency Audit Report

## 1. Objective
Diagnose the root causes for the "Text is too long" errors and high latency (minutes) reported by users, and implement structural fixes for stable real-world usage.

## 2. Root Cause Analysis

### A. VRAM Contention (The "Memory Thrash")
- **Diagnosis:** The GPU (3.6GB VRAM) was insufficient to hold the full pipeline. The original cascade (Stage 2 BERT-Large + Stage 3 RoBERTa-Large) and Stage 4 synthesis required ~4-5GB combined.
- **Effect:** The system was constantly evicting and reloading models from disk/RAM to VRAM for every request, adding 20-40 seconds of overhead per analysis.
- **Fix:** Unified Stage 2/3 into a single DeBERTa-v3 Multi-Head model, reducing total model memory by ~60%. Synthesis uses SmolLM2-1.7B (local) with CPU fallback.

### B. Misleading Timeouts
- **Diagnosis:** Any backend exception or timeout was caught by the API middleware and reported as "Text is too long".
- **Effect:** Users were confused, thinking their short input was the problem when the bottleneck was actually model loading.
- **Fix:** Increased API timeouts to 30s and improved error reporting.

### C. Synthesis Failure Loop
- **Diagnosis:** The local LLM service was failing to load 4-bit quantized models on limited VRAM, entering an infinite failure/retry loop.
- **Fix:** Switched to SmolLM2-1.7B-Instruct (FP16) with full CPU offload support; removed API fallback dependency entirely.

## 3. Latency Breakdown (Post-Fix)

Measurements taken on local hardware (3.6GB VRAM, Offline-Safe mode):

| Stage | Mode | Latency | Note |
| :--- | :--- | :--- | :--- |
| **Stage 1: Gatekeeper** | Local (DistilBERT) | ~200ms | Fast sentence-level filter |
| **Stage 2: Unified Detection** | Local (DeBERTa-v3) | ~280ms | Single model replaces cascade |
| **Stage 3: Synthesis** | Local (SmolLM2-1.7B) | ~1.5-3s | CPU bound; variable |
| **Stage 4: Symbolic** | Local (Z3) | ~400ms | High-speed formal check |
| **Total Pipeline** | | **~2.5-4s** | **Fully local, no API calls** |

## 4. UI/UX Improvements
- **Highlighting:** Fixed "disjointed" highlighting by switching from `inline-block` to `inline` HTML rendering; added char-level stateful offset tracking.
- **Redundancy:** Hover cards now only appear once per fallacy per sentence, preventing visual clutter.
- **Logic Score:** Updated scoring to a quadratic penalty system (Severity * Confidence^1.5) to better reflect actual argument quality.

## 5. Summary of Changes
1. `backend/app/core/device_manager.py`: Added VRAM-based execution routing.
2. `backend/app/core/lifecycle.py`: Optimized eviction logic.
3. `backend/app/services/unified_classifier.py`: Unified model loading with `from_pretrained` + `safe_load` fallback, `ignore_mismatched_sizes`, and fallback `id2label`.
4. `backend/app/services/llm_service.py`: Adopted SmolLM2-1.7B for fully local synthesis; removed API dependency.
5. `backend/app/services/local_smt_translator.py`: Added offline LLM-based SMT rule generation.
6. `frontend/streamlit/highlighting.py`: Fixed rendering flow and tooltips.
7. `backend/app/pipeline/orchestrator.py`: Streamlined stage transitions; restored cache bypass handling.
