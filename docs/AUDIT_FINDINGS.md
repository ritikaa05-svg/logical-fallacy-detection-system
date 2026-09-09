# LogiScan  -  Audit Findings & Prioritized Action Items

Generated: 2026-06-20

---

##  Critical (blocking or security)

### 1. Unified Classifier Model Had 0% Key Overlap (✅ Resolved)
- **File:** `docs/audit/2026-06-11_phase-a-verification.md`, lines 76-91
- **Issue:** The `DebertaV3MultiHead` checkpoint was not properly saved; 0% key overlap between checkpoint and config meant weights were effectively random. The live config points to `phase4_final_model` (correct), but it is unclear whether the root cause was fixed.
- **Action:** Verify that `models/phase4_final_model` was properly exported with correct weight-to-config alignment.
- **Resolution:** Verified `models/phase4_final_model` has 100% key overlap. See `docs/CHECKPOINT_VERIFICATION.md`.

### 2. Phase 5 Structural Parser is Non-Functional (✅ Resolved, Phase 7)
- **File:** `docs/PHASE5_EVIDENCE_AUDIT.md`, lines 5-6, 30-31
- **Issue:** Premise/conclusion extraction returns `[]` or fallbacks due to OOM on 4GB VRAM and HF API auth failures. Labeled "Experimental Scaffolding – not ready for production deployment."
- **Action:** Either fix the local LLM OOM (model too large) or implement a lightweight regex-only parser.
- **Resolution (Phase 7):** Rewritten as a 4-strategy regex chain (marker pair @ 0.90, conclusion marker @ 0.85, question-answer @ 0.75, last sentence @ 0.60) with 10 premise + 11 conclusion markers. Jaccard improved from 40% to ~92%. See `docs/PHASE5_EVIDENCE_AUDIT.md` for updated status.

---

##  High (bugs affecting functionality)

### 3. Chrome Extension Inline Event Handlers Broken (✅ Resolved, Phase 7)
- **File:** `frontend/extension/content_script.js`, lines 294, 300, 305, 336
- **Issue:** Inline `onclick`/`onchange` handlers reference `SETTINGS` and `DASHBOARD_URL` from the IIFE scope, but inline handlers execute in the global scope. Localize/Fast Track toggles and Dashboard link silently fail.
- **Action:** Attach event listeners programmatically instead of using inline HTML attributes.
- **Resolution (Phase 7):** All inline handlers converted to `addEventListener` calls within the IIFE scope.

### 4. TimeoutError Handler is Dead Code (✅ Resolved, Phase 7)
- **File:** `backend/app/api/middleware.py`, lines 104, 132
- **Issue:** `TimeoutError` handler registered after the generic `Exception` handler. Since `TimeoutError < Exception`, the generic handler catches it first.
- **Action:** Reorder exception handlers so `TimeoutError` is registered before `Exception`.
- **Resolution (Phase 7):** `TimeoutError` handler moved before `Exception` handler.

### 5. Debate Agent Always Uses Training Mode (✅ Resolved, Phase 7)
- **File:** `backend/app/services/debate_service.py`, line 312
- **Issue:** `training=True` is always passed to `select_action`, meaning epsilon-greedy random exploration runs in production. The agent takes random actions ~epsilon% of the time during normal use.
- **Action:** Separate training mode (`training=True`) from inference mode (`training=False`). Only use `training=True` during explicit `/debate/train` calls.
- **Resolution (Phase 7):** Added `LOGISCAN_ENV` config flag. When `LOGISCAN_ENV=production`, `training=False` is forced unconditionally.

### 6. LLM Breakdown Skipped in API-Fallback Mode (✅ Resolved, Phase 7)
- **File:** `backend/app/pipeline/orchestrator.py`, line 804
- **Issue:** Condition `use_llm_breakdown = not fast_path and (salient_tokens or not device_manager.use_api_fallback)`. When `use_api_fallback` is True, `not use_api_fallback` is False, so `use_llm_breakdown` is always False. Contradicts the intent of API fallback mode.
- **Action:** Fix the boolean logic so API fallback mode can still generate LLM breakdowns.
- **Resolution (Phase 7):** Simplified to `use_llm_breakdown = not fast_path`; API-fallback check moved inside the block.

### 7. Empty Test Files (✅ Resolved)
- **Files:** `backend/tests/test_z3.py`, `backend/tests/test_rl_engine.py`
- **Issue:** Both files exist with 0 lines of test code. The Z3 solver and RL debate engine have zero test coverage.
- **Action:** Implement tests for Z3 solver (SMT parsing, verification) and RL debate engine (state calculation, reward calculation, action selection).
- **Resolution:** Both files now contain working tests.

### 8. `popup.js` Invalid Fetch API Option (✅ Resolved, Phase 7)
- **File:** `frontend/extension/popup.js`, line 167
- **Issue:** `fetch(..., { timeout: 3000 })`  -  `timeout` is not a valid Fetch API option; silently ignored. Health check request has no timeout.
- **Action:** Use `AbortController` or `AbortSignal.timeout(3000)`.
- **Resolution (Phase 7):** Replaced with `AbortSignal.timeout(3000)`.

### 9. Settings Ignored in Context Menu / Keyboard Shortcut (✅ Resolved, Phase 7)
- **File:** `frontend/extension/background.js`, lines 133-159
- **Issue:** `analyzeAndShowResult` always sends `localize: false, fast_track: false`, ignoring user settings configured in the popup or overlay.
- **Action:** Accept settings as a parameter or retrieve from `chrome.storage`.
- **Resolution (Phase 7):** `analyzeAndShowResult` now reads settings from `chrome.storage.local` for all entry points.

---

##  Medium (correctness & robustness)

### 10. Model Pipeline Distribution Mismatch (✅ Resolved)
- **File:** `docs/RETRAINING_PLAN.md`, lines 3-5; `docs/WORK_LOG.md`, lines 40-44
- **Issue:** Only Stage 3 was retrained on the 12.4K hardened dataset. Stages 1 and 2 still use old data distributions, causing inconsistent gating and classification behavior.
- **Action:** Perform synchronized retraining of all three stages on the same hardened dataset.
- **Resolution:** All three stages were retrained and consolidated onto the current stack, deployed via `.env` overrides: `STAGE1_MODEL_PATH=./models/stage1_v13_classifier`, `STAGE2_MODEL_PATH=./models/stage3_v13_classifier`, `STAGE3_MODEL_PATH=./models/stage3_v13_classifier`. The Stage-3 v1.3 DeBERTa-v3-small (single-head, 29-label, ONNX) model serves both Stage 2 (coarse) and Stage 3 (fine) classification, superseding the Phase 4 24-label model. On 2026-08-05 the degenerate `stage1_v12` gatekeeper was retrained (`stage1_v13_classifier`, val F1 0.9974), and the legacy `stage1_v12` / `phase4_final_model` were retired after a benchmark record was archived in `docs/MODEL_COMPARISON.md` (`stage3_v12` kept as archival baseline).

### 11. Nginx Config Incompatible with Docker Compose (✅ Resolved, Phase 7)
- **File:** `deployment/nginx.conf`, line 10; `deployment/docker-compose.yml`, lines 4-16
- **Issue:** Nginx references `upstream logiscan_frontend { server frontend:8501; }` but the compose file defines only a single combined `logiscan` service. Host `frontend` does not exist.
- **Action:** Either add a separate frontend container, or update nginx to point to `localhost:8501`.
- **Resolution (Phase 7):** Removed `logiscan_frontend` upstream block; nginx proxies to `localhost:8501`.

### 12. Device Selection Bypasses DeviceManager Singleton (✅ Resolved, Phase 7)
- **File:** `backend/app/services/unified_classifier.py`, line 113
- **Issue:** Direct check `torch.device("cuda" if torch.cuda.is_available() else "cpu")` bypasses the `DeviceManager` singleton. If DeviceManager chose MPS, UnifiedClassifier would use CUDA or CPU.
- **Action:** Use `device_manager.get_device()` instead of direct `torch.cuda.is_available()`.
- **Resolution (Phase 7):** Replaced with `device_manager.get_device()`.

### 13. Benchmark Shows 0% Exact Match on Quote Extraction (✅ Resolved, Phase 7)
- **File:** `backend/tests/benchmarks/latest_report.json`, Suite B
- **Issue:** None of the 5 argument samples had exact quote matches (`exact_match_rate: 0.0`). 40% returned the entire text as fallback (`whole_text_fallback_rate: 0.4`).
- **Action:** Investigate and fix the evidence extraction tier to produce exact-span matches.
- **Resolution (Phase 7):** Replaced `_extract_quote_offline` with structural parser Tier 0.5, expanded discourse marker signatures (8 new fallacy types), and semantic sentence selection. Benchmark dataset expanded from 10→30 cases. Results: 100% exact match, 0% whole-text fallback, 1.0 avg IoU.

### 14. Coarse Confidence Always 1.0 (One-Hot) (✅ Resolved, Phase 7)
- **File:** `backend/app/services/unified_classifier.py`, lines 379, 631-632
- **Issue:** For single-head and ONNX inference paths, coarse category confidence is always set to 1.0 (one-hot encoding), even when the mapping is uncertain. Artificially inflates coarse confidence.
- **Action:** Derive coarse confidence from the fine-label probability distribution instead of using hard mapping.
- **Resolution (Phase 7):** Coarse confidence now derived from sum of fine-label probabilities per coarse class.

### 15. Unbounded Translation Cache (✅ Resolved, Phase 7)
- **File:** `backend/app/services/llm_translator.py`, line 15
- **Issue:** `_translation_cache` is a module-level dict with no eviction policy. Grows indefinitely over the lifetime of the server.
- **Action:** Add LRU eviction or use the shared Redis cache service.
- **Resolution (Phase 7):** Replaced raw dict with `functools.lru_cache(maxsize=1000)`.

### 16. Z3 Temp File Cleanup Not Exception-Safe (✅ Resolved, Phase 7)
- **File:** `backend/app/services/z3_service.py`, lines 198, 205
- **Issue:** `tempfile.NamedTemporaryFile(delete=False)` creates a temp file; `os.unlink` cleanup at line 205. If an exception occurs between creation and cleanup, the temp file leaks.
- **Action:** Use `try/finally` to ensure cleanup, or use `tempfile` context manager with `delete=True`.
- **Resolution (Phase 7):** Wrapped file creation and cleanup in `try/finally`.

### 17. `_initialize_bnb` May Crash on DeBERTa Input Shapes (✅ Resolved, Phase 7)
- **File:** `backend/app/services/unified_classifier.py`, lines 717-727
- **Issue:** Uses `torch.zeros((1, 1), dtype=torch.long)` as dummy input for bitsandbytes initialization. DeBERTa may expect different input dimensions.
- **Action:** Create dummy input matching the model's expected input shape from the config.
- **Resolution (Phase 7):** Changed to `torch.zeros((1, seq_len), dtype=torch.long)` where `seq_len` is read from `model.config.max_position_embeddings` (512 for DeBERTa-v3).

### 18. HF API Response Parsing Assumes Fixed Format (✅ Resolved, Phase 7)
- **File:** `backend/app/services/unified_classifier.py`, line 326
- **Issue:** Parses API response assuming list-of-dicts with `label` and `score` keys. Different model tasks may return different formats.
- **Action:** Add defensive format detection and fallback parsing.
- **Resolution (Phase 7):** Added format detection (dict, list-of-dicts, nested) with normalization to consistent structure.

### 19. Local vs Remote Path Detection Is Fragile (✅ Resolved, Phase 7)
- **File:** `backend/app/services/llm_service.py`, lines 253-256
- **Issue:** Heuristic checks for `./` or `models/` prefix to decide if a path is local vs HF repo ID. A user with `./my_custom_model` gets the wrong default model ID.
- **Action:** Use explicit `local_files_only` parameter or dedicated config flag.
- **Resolution (Phase 7):** Added `STAGE4_IS_LOCAL_PATH` boolean config flag in `config.py`.

### 20. `health_tracker.py` Race Condition Risk (✅ Resolved, Phase 7)
- **File:** `backend/app/services/health_tracker.py`, lines 31-39
- **Issue:** File-based read/write (`data/logic_health.json`) without locking. Concurrent requests can cause data corruption or lost updates.
- **Action:** Use file locking (`fcntl.flock`) or migrate to Redis.
- **Resolution (Phase 7):** Switched to in-memory storage with `threading.Lock`.

---

##  Low (cleanup & polish)

### 21. Leftover Debug Log Statements at INFO Level (✅ Resolved, Phase 7)
- **Files:** `backend/app/pipeline/orchestrator.py`, line 586; `backend/app/services/z3_service.py`, line 123
- **Issue:** `logger.info(f"DEBUG Stage3 labels: ...")` and `logger.info(f"DEBUG get_var: ...")` always execute in production, polluting logs.
- **Action:** Change to `logger.debug()` or remove.
- **Resolution (Phase 7):** Changed to `logger.debug()`.

### 22. Debug Logs at INFO Level (Second Pass) (✅ Resolved)
- **Files:** `backend/app/pipeline/orchestrator.py` (19 locations); `backend/app/services/z3_service.py` (3 locations)
- **Issue:** Internal routing, per-request progress, and GPU-recovery messages logged at `INFO` level — useful during development but noise in production.
- **Action:** Downgrade routing/progress logs to `logger.debug()`.
- **Resolution:** All 22 locations downgraded. Kept at `INFO`: `PipelineOrchestrator initialized`, `Cache hit`, and `Pipeline complete` for operational monitoring.

### 22. Empty Streamlit Component Stubs (✅ Resolved, Phase 7)
- **Files:** `frontend/streamlit/components/fallacy_card.py`; `frontend/streamlit/components/logic_gauge.py`
- **Issue:** Both files exist with 0 lines. Expected to contain UI components.
- **Action:** Implement or remove the stub files.
- **Resolution (Phase 7):** Both files deleted.

### 23. Empty `overlay.css` (✅ Resolved, Phase 7)
- **File:** `frontend/extension/overlay.css`
- **Issue:** Declared in `manifest.json` but contains only a comment. All overlay styles are injected programmatically via JS.
- **Action:** Remove from `manifest.json` or populate with actual styles.
- **Resolution (Phase 7):** Deleted `overlay.css` and removed from `manifest.json`.

### 24. Stage 2 Has Dead Code (✅ Already Clean)
- **File:** `backend/app/pipeline/stage2_coarse.py`, lines 15-20
- **Issue:** `CATEGORY_PATTERNS` is defined but never used (the class delegates entirely to `unified_classifier`).
- **Action:** Remove the unused code.
- **Resolution:** Code had already been removed in a prior cleanup pass.

### 25. `import math` Inside Function Body (✅ Resolved, Phase 7)
- **File:** `backend/app/pipeline/stage1_gatekeeper.py`, line 154
- **Issue:** `import math` inside `_heuristic_predict` instead of at module level.
- **Action:** Move import to top of file.
- **Resolution (Phase 7):** Moved `import math` to module level.

### 26. `storage` Permission Declared But Never Used (✅ Resolved, Phase 7)
- **File:** `frontend/extension/manifest.json`
- **Issue:** `storage` permission is declared but no code uses `chrome.storage`. Settings are stored in-memory.
- **Action:** Either implement `chrome.storage` for persistent settings or remove the permission.
- **Resolution (Phase 7):** Implemented `chrome.storage.local` across all extension entry points.

### 27. Dataset Version Mismatch in Docs (✅ Resolved, Phase 7)
- **File:** `docs/DATASET_MASTER.md`, line 6
- **Issue:** States v1.1.0 has 8,686 samples but `unified_training_data_v1.1.json` has 12,442 samples.
- **Action:** Update the dataset master document to reflect the actual count.
- **Resolution (Phase 7):** All references in `DATASET_MASTER.md` updated to 12,442.

### 28. Empty `.zip` Artifact (✅ Resolved, Phase 7)
- **File:** `data/.zip`
- **Issue:** A binary file named `.zip` (no basename) sits in the data directory. Purpose unclear.
- **Action:** Investigate and remove if leftover.
- **Resolution (Phase 7):** Deleted `data/.zip`.

---

##  Summary by Area (Updated 2026-07-21)

### Resolution Summary (Updated 2026-07-23)
| Priority | Total | Resolved | Remaining |
|:---------|:-----:|:--------:|:---------:|
| Critical | 2 | 2 | 0 |
| High | 7 | 7 | 0 |
| Medium | 11 | 11 | 0 |
| Low | 10 | 10 | 0 |
| **Total** | **30** | **30** | **0** |

**All 30 audit findings from this report are resolved.**

> **⚠️ Note:** A comprehensive 15-section audit on 2026-07-25 identified 39 new findings (1 Critical, 9 High, 12 Medium, 17 Low). See `docs/KNOWN_ISSUES.md` #41. This report's 30 findings were all resolved; the new findings are tracked separately.
| **Infrastructure/DevOps** | 0 | 0 | 0 | 0 |
| **Data/Docs** | 0 | 0 | 0 | 0 |
| **Total** | **0** | **0** | **1** | **0** |
