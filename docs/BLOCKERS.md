# LogiScan Development Blockers

## Current Blockers

| Blocker | Severity | Description | Resolution Path |
| :--- | :---: | :--- | :--- |
| **Formal Recall Gap** | High | 61% of `affirming_consequent` errors missed in V1. Hard negative expansion completed (1.6K+ samples). Formal class expansion added 4,500 samples (v1.3 dataset at 17,938). | Stage 3 retraining on v1.3 dataset required. |
| **Pipeline Mismatch** | High | Only Stage 3 retrained on 12.4K data; Stages 1 & 2 use older distributions | See resolved blockers below |

## Resolved Blockers

| Blocker | Resolution | Date |
| :--- | :--- | :--- |
| **HF Auth Failure** | Token rotated and .env removed from git tracking. | 2026-06-29 |
| **Phase 5 Extraction** | Enabled local LLM fallback and corrected API model IDs. | 2026-06-15 |
| **Phase 5 Structural Parser** | Rewritten with 4-strategy regex chain; Jaccard improved 40% → ~92%. | 2026-07-20 |
| **Debate Agent Training Lock** | `LOGISCAN_ENV` flag forces inference mode in production. | 2026-07-20 |
| **Unbounded Translation Cache** | Replaced raw dict with `lru_cache(maxsize=1000)`. | 2026-07-20 |
| **Coarse Confidence Inflation** | Derived from fine-label distribution instead of one-hot. | 2026-07-20 |
| **Z3 Temp File Leak** | `try/finally` guard on temp file cleanup. | 2026-07-20 |
| **Device Selection Bypass** | Uses `DeviceManager.get_device()` instead of direct CUDA check. | 2026-07-20 |
| **Health Tracker Race** | Switched to in-memory + threading lock. | 2026-07-20 |
| **Extension Settings Lost** | `chrome.storage.local` propagated to all three entry points. | 2026-07-20 |
| **VRAM Overflow** | Converted Stage 1 & 2 to ONNX (CPU inference). | 2026-06-12 |
| **Daemon Leak** | Converted Model Eviction Timer to daemon mode. | 2026-06-12 |
| **Latency Discrepancy** | Identified cold-start vs steady-state measurement. | 2026-06-12 |
| **Offset Drift** | Implemented `OffsetMapper` for history translation. | 2026-06-08 |
| **Cache Bypass** | Restored Redis caching and hit/miss behavior. | 2026-06-07 |
| **Model Key Overlap** | Verified `models/phase4_final_model` has 100% key overlap. See `docs/CHECKPOINT_VERIFICATION.md`. | 2026-07-21 |
| **Quote Extraction 0% EM** | Overhauled `_extract_quote_offline` with structural parser Tier 0.5, expanded signatures (8 new fallacy types), semantic sentence selection. Benchmark: 100% exact match, 0% whole-text fallback, 1.0 avg IoU. | 2026-07-21 |
| **_initialize_bnb CUDA Assert** | Dummy pass used `torch.zeros` triggering device-side assert on RoBERTa. Fixed to use pad tokens + single BOS token. | 2026-07-23 |
| **RateLimiter KeyError** | In-memory fallback raised `KeyError` on first client request. Fixed with `.get(client_ip, [])`. | 2026-07-23 |
| **Frontend Peer Dependency Conflict** | `vite@6.3.2` / `vitest@3.1.2` incompatible with plugins. Updated to `vite@8.1.5` / `vitest@4.1.10`. | 2026-07-23 |
| **npm ci Lockfile Mismatch** | Lockfile out of sync with package.json; replaced with `npm install`. | 2026-07-23 |
| **Test Files Blocking Build** | Added `exclude` to `tsconfig.app.json` for `src/__tests__/`. | 2026-07-23 |
| **Pipeline Mismatch** | All three stages retrained (v12, Jul 21) and deployed via `.env`. | 2026-07-25 |
| **Script `cd` State Leak** | Failed `npm ci` left script in wrong directory; wrapped in subshells. | 2026-07-23 |
| **LLM Unavailability Cascade** | `generate_unified_breakdown` crashed with `'NoneType' object has no attribute '_model'` when `STAGE4_IS_LOCAL_PATH=False`. | 2026-07-25 |
| **Log Levels at INFO** | ~22 routing/progress messages at `INFO` level polluting production logs; downgraded to `DEBUG`. | 2026-07-25 |
| **Dataset Docs Outdated** | `DATASET_MASTER.md` only documented v1.1; v1.2 and v1.3 undocumented. | 2026-07-25 |

## Historical Blockers (Archived)

| Blocker | Severity | Resolution |
| :--- | :---: | :--- |
| **Empty Test Suite** | Critical | Tests populated in `test_pipeline.py`. |
| **Stage 4 Synthesis Mocking** | High | Replaced mock strings with `SmolLM2` generation. |
| **CUDA OOM (Legacy)** | Implemented memory-aware loading (VRAM < 4.5GB). |
