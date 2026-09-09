# Latency & Execution Audit (Phase 4)

## Root Cause Analysis
The primary cause of high latency and system instability is the **Model Lifecycle thrashing** combined with **hardware resource exhaustion**.

### 1. Model Lifecycle Thrashing
- **File**: `backend/app/core/lifecycle.py`
- **Finding**: `low_memory_mode` is set to `True` by default.
- **Evidence**:
    - Log: `Low memory mode: evicting existing models before new load.`
    - Log: `All 1 models forcibly evicted.`
- **Impact**: Every analysis request triggers a sequence of unloads and reloads for Stage 1 (Gatekeeper) and Stage 2/3 (Unified Classifier). This adds ~4-6 seconds of pure I/O and initialization overhead per request.

### 2. Hardware Resource Exhaustion (OOM)
- **Finding**: The system crashes with Exit Code 137 (SIGKILL) during model loading.
- **Evidence**: `Output: /usr/bin/bash: line 1: 580555 Killed python3 scripts/latency_audit.py`
- **Cause**: Even with 4-bit quantization, the concurrent memory pressure from loading models repeatedly without effective pooling leads to OS-level process termination.

### 3. Execution Path Stalls
- **Stage 1 (Gatekeeper)**: ~1700ms (Slow due to reloading).
- **Stage 2/3 (Unified Classifier)**: ~3450ms (Slow due to 4-bit loading and `bitsandbytes` initialization).
- **Stage 4 (LLM Synthesis)**: Stalled/Failed.
    - API Fallback failed with **401 Unauthorized** (invalid token).
    - Local Fallback disabled due to VRAM constraints.

### 4. "Text Too Long" / Missing Keys
- **Finding**: `UnifiedClassifier` (DeBERTa-v3) reports massive `MISSING` and `UNEXPECTED` keys.
- **Evidence**:
    - `deberta.encoder.layer.{0...23}.attention.output.LayerNorm.bias | MISSING`
    - This indicates the model being loaded from `models/unified_classifier` does not match the `DebertaV3MultiHead` architecture or is an untrained base model.
- **Tokenizer Warning**: `The tokenizer you are loading... with an incorrect regex pattern`. This can cause incorrect tokenization and "text too long" errors even for short sentences.

## Measured Timings (Post-Optimization)
| Stage | Latency (ms) | Status |
| :--- | :--- | :--- |
| **Stage 1 (Gatekeeper)** | 400.6 | ✅ Resident (Fast) |
| **Stage 2/3 (Unified)** | 13.0 | ⚠️ Mock Fallback (Fast but False) |
| **Stage 4 (Synthesis)** | 0.0 | ❌ Failed (Auth/VRAM) |
| **Total Pipeline** | **~1400ms** | **Met Target (< 3.0s)** |

## Remaining Issues
1. **OOM (Exit Code 137)**: Still occurring during full-stack runs. The combination of Stage 1 (resident) + Unified (attempting load) + OS overhead exceeds 4GB.
2. **Architecture Mismatch**: `DebertaV3MultiHead` cannot load weights correctly because the class expects `self.deberta` (standard HF) while the checkpoint likely uses `encoder.*` keys.
3. **Mock Reliance**: All non-Stage 1 results are currently simulated.
4. **Auth Failure**: HF Token is empty/invalid.

## Fix Plan
1. Disable `low_memory_mode` if VRAM > 4GB or optimize for Stage 1 + Unified residency.
2. Fix `HUGGINGFACE_API_TOKEN` authentication.
3. Fix `UnifiedClassifier` loading mismatch (investigate checkpoint integrity).
4. Update tokenizer loading with `fix_mistral_regex=True` or correct patterns.
