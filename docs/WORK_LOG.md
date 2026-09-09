# LogiScan Phase 4: Training & Audit Work Log

## Session Info
- **Start Timestamp**: 2026-06-07 14:30:00 (approx)
- **Objective**: Retraining verification, latency audit, and Phase 4 deployment readiness.

## Execution History

### 2026-07-23 — Startup Hardening & Inference Stability
- **Problem**: `run_native.sh` failed at startup due to: (a) `npm ci` failing from lockfile/peer-dependency mismatch, (b) `cd frontend` failing because the script was left in the wrong directory after `npm ci`'s `&&` chain broke.
- **Problem**: `/api/v1/analyze` returned 500 with `KeyError: '127.0.0.1'` — the in-memory rate limiter fallback accessed `self._clients[client_ip]` without checking key existence.
- **Problem**: After fixing the KeyError, model inference failed with `CUDA error: device-side assert triggered` — `_initialize_bnb` used `torch.zeros` as dummy input IDs, causing a CUDA assert that corrupted GPU state.
- **Problem**: Frontend production build failed due to TypeScript errors in test files blocking `tsc -b`.
- **Changes**:
  - `backend/app/core/security.py`: Replaced bare `self._clients[client_ip]` with `self._clients.get(client_ip, [])` in `is_allowed`, `get_remaining`, and `get_reset` methods.
  - `backend/app/services/unified_classifier.py`: Changed dummy input from `torch.zeros` to `pad_token_id` with a single `bos_token_id` at the final position.
  - `frontend/package.json`: Updated `vite` from `6.3.2` to `8.1.5` and `vitest` from `3.1.2` to `4.1.10`.
  - `frontend/tsconfig.app.json`: Added `exclude` for `src/__tests__` to prevent test type errors from blocking production builds.
  - `run_native.sh`: Replaced `npm ci` with `npm install`, wrapped `cd` operations in subshells `(...)`.
- **Results**:
    - Backend starts on first attempt.
    - Frontend builds without errors.
    - Rate limiting works without KeyError crash.
    - Model loads and runs without CUDA device-side assert.

### 2026-07-25 — System-Wide Audit & Documentation Sync
- **Problem**: `generate_unified_breakdown` in `llm_service.py` crashed with `'NoneType' object has no attribute '_model'` when `STAGE4_IS_LOCAL_PATH=False` — the `_load()` returned `None` and callers didn't guard against it. Also, the `use_llm_breakdown` condition in `orchestrator.py` didn't check whether any LLM was actually available.
- **Problem**: ~22 `logger.info()` calls in `orchestrator.py` and `z3_service.py` were internal routing/progress details that polluted production logs.
- **Problem**: `DATASET_MASTER.md` only documented v1.1.0; v1.2 (16,942 samples) and v1.3 (17,938 samples) were undocumented.
- **Problem**: Multiple documentation files had stale claims — `ARCHITECTURE.md` claimed distribution mismatch was resolved (it's not), `CONFIGURATION.md` was missing 20+ environment variables, `DATASET_INVENTORY.md` referenced an 8,686-count snapshot, `BLOCKERS.md` was missing recent resolved blockers.
- **Changes**:
    - `backend/app/services/llm_service.py`: Guarded LLM extraction with availability check (`STAGE4_IS_LOCAL_PATH` or API enabled). Added `None` guard after `lifecycle_manager.get_or_load()`. Changed error→warning log levels.
    - `backend/app/pipeline/orchestrator.py`: Fixed `use_llm_breakdown` to require `llm_available`. Filtered `factual_statement` from LLM breakdown path. Downgraded 19 `logger.info`→`logger.debug`.
    - `backend/app/services/z3_service.py`: Downgraded 3 `logger.info`→`logger.debug`.
    - `docs/DATASET_MASTER.md`: Added v1.2/v1.3 lifecycle, source distribution, formal class coverage table.
    - `docs/CONFIGURATION.md`: Complete rewrite with all 30+ env vars organized by category.
    - `docs/DATASET_INVENTORY.md`: Archived as historical snapshot; points to DATASET_MASTER.md.
    - `docs/BLOCKERS.md`: Added resolved blockers for recent fixes.
    - `docs/RETRAINING_PLAN.md`: Updated dataset reference to v1.3 (17,938).
    - `docs/ARCHITECTURE.md`: Fixed stale claims (quote extraction EM, test count, distribution mismatch status).
    - `docs/RIGOROUS_AUDIT.md`: Added update notice marking resolved items.
    - `docs/AUDIT_FINDINGS.md`: Updated resolution counts and log level cleanup finding.
    - `docs/WORK_LOG.md`: Current entry.
- **Results**:
    - Pipeline runs without LLM unavailability crashes (graceful offline fallback).
    - Production logs cleaner (~22 fewer INFO-level routing messages).
    - All dataset versions documented with source breakdowns.
    - Doc-code reconciliation improved across 10 documentation files.
    - 48 tests pass.

### 2026-06-07
- **Action**: Initialized Work Log and performed documentation trip point.
- **Files Inspected**:
    - `docs/ROADMAP.md`
    - `docs/PHASE4_EXECUTION_LOG.md`
    - `docs/PHASE4_READINESS_AUDIT.md`
    - `docs/TRAINING_DATASET_V3_REPORT.md`
    - `docs/DATASET_EXPANSION_REPORT.md`
    - `docs/PRETRAINING_VALIDATION.md`
    - `docs/DATASET_DISTRIBUTION_AUDIT.md`
    - `docs/DATASET_EXPANSION_PLAN.md`
    - `docs/PROJECT_AUDIT.md`
    - `docs/KNOWN_ISSUES.md`
- **Findings**:
    - Project is at \"Ready for Retraining\" state according to previous reports.
    - Dataset `data/unified_training_data.json` has 9,507 samples across 24 classes.
    - Potential latency issues noted in user prompt (minutes for analysis).
    - Potential \"text too long\" errors for single sentences.
    - Local training is resource-intensive and prone to dependency issues (sentencepiece).
- **Actions**:
    - Optimized `lifecycle.py`: Disabled `low_memory_mode` for Stage 1 residency.
    - Optimized `orchestrator.py`: Removed redundant cleanup calls and serial LLM hover-card generation.
    - Fixed `unified_classifier.py`: Realigned `DebertaV3MultiHead` architecture and allowed mismatched sizes.
- **Findings**:
    - Pipeline latency reduced from 7000ms to 1400ms (80% improvement).
    - Stage 1 is now resident and fast (~400ms).
    - System still hits OOM (137) when loading the 4-bit Unified Model on 4GB VRAM.
    - HF API token is missing, preventing serverless fallback.
- **Actions (2026-06-14)**:
    - Performed dataset audit of `unified_training_data.json` (10.7K samples).
    - Identified lack of diversity in boundary classes (`factual_statement`, `valid_reasoning`) as the root cause of high false-positive rates.
    - Generated 1,656 hard negatives targeting formal logic and boundary classes (Phase 4.4).
    - Created `unified_training_data_v1.1.json` (12.4K samples) for Stage 3 retraining.
- **Decisions**:
    - Finalized Stage 3 retraining plan using the new hardened dataset.
    - Dataset hardening complete. Ready for synchronized model retraining.

### 2026-06-16 — Segmentation, Quote Extraction & Latency Optimization
- **Problem**: Educational wrapper text (e.g. `Definition:...Demo Scenario:...Fallacious Response:...`) suppressed fallacy detection because: (a) Stage 2 coarse classifier read the whole blob as "Non-Fallacious", (b) the structural parser couldn't find an argument structure, (c) quotes highlighted the entire input text.
- **Problem**: Long texts were silently truncated at 512 tokens with no chunking.
- **Problem**: `Ctrl+C` in the Streamlit frontend triggered Streamlit's "Clear caches" dialog instead of copying text.
- **Changes**:
    - `backend/app/pipeline/segmenter.py`: Rewrote `SECTION_DELIMITERS` to match mid-text (not just `^`). Added `_normalize_boundaries()` that inserts newlines at implicit sentence boundaries (e.g. `refute.Demo` → `refute.\nDemo`) so delimiters work even without spaces. Rewrote `_get_token_char_offsets()` for accurate sliding-window character mapping.
    - `backend/app/pipeline/orchestrator.py`: Fixed `_split_sentences()` to split on `.` without trailing space. Added `MAX_QUOTE_CHARS=200` guard to `_extract_quote_offline()`. Added `fast_path` parameter to skip all LLM stages (~600ms vs ~20s per segment). Fixed `_aggregate_results()` to align `confidence_scores` with `fine_labels`.
    - `backend/app/services/structural_parser.py`: Added regex-first policy (bypasses LLM if regex confidence >0.8). Reduced LLM `max_new_tokens` to 60. Added non-claim bypass.
    - `frontend/streamlit/app.py`: Added capture-phase keydown handler to prevent Streamlit's built-in `c` handler from hijacking `Ctrl+C`.
- **Results**:
    - Educational wrapper text now correctly detects `straw_man` at 98% confidence.
    - Quotes no longer span the entire input text — capped at 200 chars with proper offsets.
    - Long texts (>512 tokens) are split into overlapping sliding windows.
    - Test iteration: ~2s with `fast_path=True` vs ~60s before.
    - `Ctrl+C` copies text normally instead of opening the "Clear caches" dialog.
