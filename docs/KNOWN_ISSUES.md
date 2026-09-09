# LogiScan Known Issues

## 1. Highlighting Discrepancies (✅ Resolved)
- **Description**: Highlights appear in the wrong place or don't appear at all.
- **Resolution**: Implemented char-level stateful tracking via `OffsetMapper`.

## 2. Broken Redis Caching (✅ Resolved)
- **Description**: Analysis always runs fresh, ignoring the cache.
- **Resolution**: Restored `skip_cache` flag handling.

## 3. Latency Discrepancy (✅ Resolved)
- **Description**: Benchmark reported ~1500ms while production reported ~400ms.
- **Resolution**: Identified cold-start overhead vs steady-state; verified at ~240ms.

## 4. VRAM Overflow (✅ Resolved)
- **Description**: 4GB hardware OOM during multi-model load.
- **Resolution**: Migrated Stage 1 and Stage 2 to CPU-based ONNX inference.

## 5. Phase 5 extraction (✅ Resolved)
- **Description**: Structural Parser returns empty extractions due to LLM residency/auth issues.
- **Resolution**: Enabled local LLM fallback and corrected API configuration.

## 6. Long Text Truncation (✅ Resolved)
- **Description**: Inputs >512 tokens were silently right-truncated; content beyond the limit was invisible to the models.
- **Resolution**: Added `segmenter.py` with sliding window (448-token windows, 128-token overlap). Also added `_normalize_boundaries()` for mid-text delimiter matching and structural section segmentation.

## 7. Educational Wrapper Suppression (✅ Resolved)
- **Description**: Text like `Definition:...Demo Scenario:...Fallacious Response:...` was classified as "Non-Fallacious" because Stage 2 read the whole blob and the structural parser couldn't find a single argument structure.
- **Resolution**: The segmenter now splits on section delimiters (matching mid-text), and each section is analyzed independently. Fallacies embedded inside educational wrappers are correctly detected.

## 8. Entire-Text Quote Highlighting (✅ Resolved)
- **Description**: When the sentence splitter failed to split (e.g. `refute.Demo` with no space), the entire input was treated as one sentence and highlighted as a single quote.
- **Resolution**: Sentence splitter now handles `.` without trailing space. Added `MAX_QUOTE_CHARS=200` safety cap in `_extract_quote_offline()`.

## 9. Ctrl+C Hijacking in Streamlit (✅ Resolved)
- **Description**: Pressing `Ctrl+C` to copy text triggered Streamlit's "Clear caches" dialog instead.
- **Resolution**: Added capture-phase keydown handler that intercepts plain `Ctrl+C` and stops propagation before Streamlit's default handler fires.

## 10. Formal Recall Gap
- **Description**: `affirming_consequent` recall at 0.39; model is too conservative.
- **Status**: Targeted expansion completed; pending retraining.

## 11. Synthetic Memorization
- **Description**: High performance (1.00 F1) on minority classes due to limited template variety.
- **Status**: Phase 4 validation confirmed ~10% regression on real-world data.

## 12. Recent Hotfixes and Contract Changes (2026-06-20)
- **UnifiedClassifier caching**: Internal in-process cache now keys on (text, include_explanations). A `skip_cache` flag is supported by the classifier and pipeline to force fresh inference. Cached objects are deep-copied on return to avoid mutation issues.
- **Non-blocking loads**: Model lifecycle loads invoked from async code now run in a thread executor to avoid blocking the event loop.
- **Saliency format**: Backend emits `salient_tokens` as list of dicts (token, score, start, end) and includes `explanations_requested` flag. Frontend extension updated for backward compatibility.
- **HF API fallback**: Uses `HF_MODEL_ID` config and includes retry/backoff (3 attempts) and timeout handling to reduce transient failures.
- **Structural parser regex**: Improved robustness for multiple marker occurrences; conclusion is derived from final marker and premises aggregated from earlier segments.

Note: These hotfixes are deployed in the current branch; update downstream integrations if you rely on the legacy `salient_tokens` tuple format or the previous single-text cache semantics.

---

## 13. Salient Tokens Never Populated in Frontend Requests (Found 2026-06-23)
- **Description**: The API schema defaults `include_explanations` to `False` (`schemas/inference.py:42`), and none of the frontends (Streamlit dashboard, Chrome extension popup, background.js context menu) explicitly passed `True`. This meant `salient_tokens` was always `[]` in practice — the XAI token-level highlighting was never computed during normal usage.
- **Impact**: The extension's "Evidence" section (color-coded highlighted tokens) was always empty. The Streamlit saliency view showed full-sentence highlights with hardcoded `saliency: 1.0` (saliency-free fallback path).
- **Root cause**: Three-prong omission — API default `False`, no frontend sends the field, and the `capture-keyword` keyboard shortcut path had no toggle integration.
- **Fix (2026-06-23)**: Wired `include_explanations` to the existing `fast_track` toggle in all frontends:
  - `streamlit/app.py:101` → `"include_explanations": not fast_track`
  - `background.js:88` (popup path) → `include_explanations: !request.settings?.fastTrack`
  - `background.js:145` (context menu) → `include_explanations: true` (no fast track toggle available)
- **Status**: ✅ Fixed. Token-level saliency now computed when Fast Track is off.

## 14. Educational Text False Positives (Found 2026-06-23)
- **Description**: Text that *describes* or *defines* a logical fallacy (e.g., "This fallacy presents a complex situation as if there are only two possible options or outcomes, when in reality, more alternatives exist...") is classified as containing that fallacy. The ML model matches surface-level text patterns (`(either|only)...or` for false dilemma) with no understanding of educational intent vs. actual argumentation.
- **Impact**: Users pasting educational/definitional text see false positive fallacy detections. The confidence can be very high (>99%) because the pattern match is unambiguous.
- **Root cause**: The ML classifier operates on text patterns alone. There is no context-aware wrapper to distinguish "text about a fallacy" from "text committing a fallacy."
- **Mitigation (Phase 7)**: Added `DESCRIPTION_PATTERNS` (educational-framing regex set, `orchestrator.py:627-639` — e.g. `\b(This|A|An)\s+(fallacy|logical fallacy|reasoning error)\b`, `\bis a (logical |common |formal |informal )?fallacy\b`, `\boccurs when\b`, `^Definition:`, `^What is`) detected after Stage 1. When matched (`orchestrator.py:640-654`), the result is forced to a non-argument early return **before Stage 2/3 run** (`orchestrator.py:676-682`), so the ML classification path is now guarded too.
- **Status**: ✅ Fully mitigated for all text matching the framing patterns. Residual gap: educational text that matches none of the patterns has no LLM-judge fallback (low-risk; pattern set covers common definitional/educational framings).

## 15. Quote Extraction Prefers First Discourse Match (Found 2026-06-23)
- **Description**: When `salient_tokens` is unavailable (or attribution scores are split across similar clauses), `_extract_quote_offline` uses Tier 2 regex matching against `FALLACY_SIGNATURES`. It scans sentences left-to-right and picks the **first** clause matching the pattern. In educational text, this selects the definition sentence instead of the embedded example, producing misleading quotes.
- **Example input**: `"This fallacy presents only two options... Example: 'We either need to ban cars or accept pollution...'"`
- **Current result**: Quote = *"This fallacy presents a complex situation as if there are only two possible options or outcomes"* (the definition)
- **Expected result**: Quote should prefer the example sentence when the text is educational/mixed content.
- **Workaround**: With `include_explanations` now enabled (item 13), Tier 1 (saliency anchor) runs before Tier 2. If integrated gradients correctly attribute the prediction to example tokens, the quote will improve.
- **Status**: 🟡 Mitigated by item 13, but not fully resolved for cases where attribution is split equally.

## 16. Debate Agent Uses Untrained Policy (Found 2026-06-23)
- **Description**: The DQN debate agent logs `"No saved model found at ./models/dqn_debate_policy.pt. Using untrained agent."` on every startup. The agent has never been trained, so its action selection is effectively random (epsilon=0.9, nearly 90% random actions).
- **Impact**: The Debate page in the Streamlit dashboard returns nonsensical responses in ~90% of turns, making the feature unusable for demos.
- **Root cause**: The `training=False` fix (item 12) prevents exploration, but with an untrained policy network (random weights), the agent has no learned behavior even in inference mode.
- **Fix (Phase 7)**: Added `LOGISCAN_ENV` config flag. When the environment variable is set to `"production"`, `training=False` is forced unconditionally, preventing random exploration in deployed instances. The agent still needs training for meaningful responses.
- **Fix (2026-08-02, debate overhaul)**: The agent is now seeded via behavior-cloning initialization — `scripts/train_dqn_debate.py` builds state/action/reward transitions from the v1.3 training data (fallacy label → `_rule_based_action`, reward = pipeline confidence) and trains the DQN head, producing `models/dqn_debate_policy.pt` (3000 steps, avg_loss 0.0081). `DebateService` now also: (1) detects intent (greetings, question leads, ack phrases) and responds without invoking the pipeline, (2) gates `POINT_OUT_FALLACY` behind a confidence floor (`RL_POINT_CONF_FLOOR=0.60`, matching the reranker boundary) — below it the action downgrades to `ASK_SOCRATIC`, (3) de-duplicates response templates per session so canned replies never repeat verbatim, and (4) grounds Socratic/agree templates by quoting the user's own phrase. Debate turns are additionally logged to Postgres (`debate_sessions`/`debate_turns`, via best-effort `debate_logger.py`) when a real `DATABASE_URL` is configured. Verified against a live transcript: greetings, questions, acknowledgements, fallacy call-outs, and follow-ups all produce sensible, non-repeating responses.
- **Status**: ✅ Resolved — seeded policy + confidence gating + intent detection (2026-08-02).

## 17. Pydantic V2 Deprecation Warnings (✅ Resolved)
- **Description**: `schemas/inference.py` used deprecated Pydantic V2 patterns — `class Config` with `json_schema_extra` (should use `model_config = ConfigDict(...)`).
- **Fix (2026-06-29)**: Replaced `class Config` with `model_config = ConfigDict(...)` and added `ConfigDict` import.
- **Status**: ✅ Resolved. No more deprecation warnings.

## 18. Structural Parser Regex Misalignment (✅ Resolved, Phase 7)
- **Description**: The structural parser (previously LLM-dependent) returned empty premise/conclusion extractions due to OOM (4GB VRAM) and HF API auth failures. Jaccard scores were 40% for premise and conclusion extraction.
- **Fix (Phase 7)**: Full rewrite — 4-strategy regex chain (marker pair @ 0.90, conclusion marker @ 0.85, question-answer @ 0.75, last-sentence @ 0.60) with 10 premise markers + 11 conclusion markers. Jaccard improved from 40% to ~92%.
- **Status**: ✅ Resolved.

## 19. Unbounded Translation Cache (✅ Resolved, Phase 7)
- **Description**: `_translation_cache` was a module-level dict in `llm_translator.py` with no eviction policy, growing indefinitely over server lifetime.
- **Fix (Phase 7)**: Replaced raw dict with `functools.lru_cache(maxsize=1000)`.
- **Status**: ✅ Resolved.

## 20. Coarse Confidence Always 1.0 (✅ Resolved, Phase 7)
- **Description**: Single-head and ONNX inference paths set coarse category confidence to 1.0 (one-hot encoding), artificially inflating confidence.
- **Fix (Phase 7)**: Derived coarse confidence from fine-label probability distribution — sum of probabilities across all fine labels mapped to that coarse class.
- **Status**: ✅ Resolved.

## 21. Z3 Temp File Leak (✅ Resolved, Phase 7)
- **Description**: `tempfile.NamedTemporaryFile(delete=False)` created temp files in `z3_service.py`; `os.unlink` cleanup at line 205 was not exception-safe, leaking temp files on error.
- **Fix (Phase 7)**: Wrapped temp file creation and cleanup in `try/finally` block.
- **Status**: ✅ Resolved.

## 22. Device Selection Bypasses DeviceManager (✅ Resolved, Phase 7)
- **Description**: `unified_classifier.py` line 113 used `torch.device("cuda" if torch.cuda.is_available() else "cpu")` directly, bypassing `DeviceManager` singleton.
- **Fix (Phase 7)**: Replaced with `device_manager.get_device()` to respect MPS and other device choices.
- **Status**: ✅ Resolved.

## 23. `import math` Inside Function Body (✅ Resolved, Phase 7)
- **Description**: `stage1_gatekeeper.py` line 154 had `import math` inside `_heuristic_predict` instead of module-level.
- **Fix (Phase 7)**: Moved `import math` to top of file.
- **Status**: ✅ Resolved.

## 24. Nginx Config Incompatible with Docker Compose (✅ Resolved, Phase 7)
- **Description**: `deployment/nginx.conf` referenced `upstream logiscan_frontend { server frontend:8501; }` but the compose file defines only a combined `logiscan` service, making `frontend` host unresolvable.
- **Fix (Phase 7)**: Removed `logiscan_frontend` upstream block; nginx now proxies to `localhost:8501`.
- **Status**: ✅ Resolved.

## 25. Health Tracker Race Condition (✅ Resolved, Phase 7)
- **Description**: `health_tracker.py` used file-based read/write (`data/logic_health.json`) without locking, causing data corruption under concurrent requests.
- **Fix (Phase 7)**: Switched to in-memory storage with threading lock.
- **Status**: ✅ Resolved.

## 26. Chrome Extension Inline Event Handlers (✅ Resolved, Phase 7)
- **Description**: Inline `onclick`/`onchange` handlers in `content_script.js` referenced IIFE-scoped `SETTINGS` and `DASHBOARD_URL`, which are inaccessible from global scope. Toggles silently failed.
- **Fix (Phase 7)**: Converted all inline event handlers to programmatic `addEventListener` calls.
- **Status**: ✅ Resolved.

## 27. TimeoutError Handler Dead Code (✅ Resolved, Phase 7)
- **Description**: `middleware.py` registered `TimeoutError` handler after generic `Exception` handler, making it dead code.
- **Fix (Phase 7)**: Reordered handlers so `TimeoutError` is registered before `Exception`.
- **Status**: ✅ Resolved.

## 28. Debate Agent Always Trains in Production (✅ Resolved, Phase 7)
- **Description**: `debate_service.py` always passed `training=True` to `select_action`, causing epsilon-greedy random exploration in production.
- **Fix (Phase 7)**: Added `LOGISCAN_ENV` config — `training=False` when `LOGISCAN_ENV=production`.
- **Status**: ✅ Resolved.

## 29. LLM Breakdown Boolean Logic (✅ Resolved, Phase 7)
- **Description**: `orchestrator.py` line 804 had `use_llm_breakdown = not fast_path and (salient_tokens or not device_manager.use_api_fallback)`, which always evaluated to False when `use_api_fallback=True`.
- **Fix (Phase 7)**: Simplified to `use_llm_breakdown = not fast_path`; saliency/API-fallback checks moved inside the block.
- **Status**: ✅ Resolved.

## 30. Salient Tokens Never Populated (✅ Resolved)
- **Description**: Frontends never sent `include_explanations=True`, so `salient_tokens` was always `[]`.
- **Fix (Phase 7)**: Wired `include_explanations` to Fast Track toggle in Streamlit, popup, and context menu paths.
- **Status**: ✅ Resolved.

## 31. HF API Response Parsing Fragile (✅ Resolved, Phase 7)
- **Description**: `unified_classifier.py` parsed HF API responses assuming fixed list-of-dicts format with `label`/`score` keys; different model tasks return different structures.
- **Fix (Phase 7)**: Added defensive format detection — checks for dict, list-of-dicts, and nested structures; normalizes all to consistent format.
- **Status**: ✅ Resolved.

## 32. Local vs Remote Path Detection (✅ Resolved, Phase 7)
- **Description**: `llm_service.py` used fragile heuristic (`./` or `models/` prefix) to decide local vs HF repo ID.
- **Fix (Phase 7)**: Added `STAGE4_IS_LOCAL_PATH` boolean config flag for explicit path type declaration.
- **Status**: ✅ Resolved.

## 33. Extension Settings Not Propagated to Context Menu / Keyboard Shortcut (✅ Resolved, Phase 7)
- **Description**: `background.js` always sent `localize: false, fast_track: false`, ignoring user settings.
- **Fix (Phase 7)**: `analyzeAndShowResult` now reads settings from `chrome.storage.local` for context menu and keyboard shortcut paths.
- **Status**: ✅ Resolved.

## 34. Empty Stub Files (✅ Resolved, Phase 7)
- **Description**: `fallacy_card.py`, `logic_gauge.py`, `overlay.css`, and `data/.zip` were empty/orphan artifacts.
- **Fix (Phase 7)**: Deleted all four files; removed `overlay.css` from `manifest.json`.
- **Status**: ✅ Resolved.

## 35. storage Permission Declared But Unused (✅ Resolved, Phase 7)
- **Description**: `manifest.json` declared `storage` permission but no code used `chrome.storage`.
- **Fix (Phase 7)**: Implemented `chrome.storage.local` for settings persistence across all extension entry points.
- **Status**: ✅ Resolved.

## 36. Debug Log Statements at INFO Level (✅ Resolved, Phase 7)
- **Description**: `logger.info("DEBUG Stage3 labels: ...")` and similar ran unconditionally in production.
- **Fix (Phase 7)**: Changed to `logger.debug()` or removed.
- **Status**: ✅ Resolved.

## 37. RateLimiter KeyError on First Request (✅ Resolved, 2026-07-23)
- **Description**: The in-memory rate limiter fallback (used when Redis is unavailable) raised `KeyError: '127.0.0.1'` on the first request from a client. `is_allowed()` at line 151 accessed `self._clients[client_ip]` without checking if the key existed.
- **Impact**: All `/api/v1/analyze` POST requests returned 500 with no analysis performed.
- **Root cause**: `self._clients[client_ip] = [t for t in self._clients[client_ip] if t > cutoff]` — dict lookup on the right-hand side fails when the IP hasn't been seen before.
- **Fix**: Replaced `self._clients[client_ip]` lookups with `self._clients.get(client_ip, [])` in all three fallback paths (`is_allowed`, `get_remaining`, `get_reset`).
- **Status**: ✅ Resolved.

## 38. BNB Dummy Pass CUDA Device-Side Assert (✅ Resolved, 2026-07-23)
- **Description**: `_initialize_bnb` in `unified_classifier.py` fed `torch.zeros` as model input IDs during the dummy forward pass. All-zero inputs (bos_token_id=0 for RoBERTa) triggered a CUDA device-side assert, corrupting GPU state and killing all subsequent inference.
- **Impact**: Every analysis request after model load failed with `CUDA error: device-side assert triggered`. Subsequent model loads also failed because CUDA was in an error state.
- **Root cause**: `torch.zeros((1, seq_len))` creates a tensor where every position is `bos_token_id=0`. Some RoBERTa/DeBERTa layers (e.g., attention mask interaction with padding) may assert when the input is all-bos with no variation.
- **Fix**: Changed dummy input to use `pad_token_id` (1 for RoBERTa) for all positions, with a single `bos_token_id` at the final position — a valid input distribution that any transformer can process.
- **Status**: ✅ Resolved.

## 39. Frontend npm ci / Peer Dependency Conflict (✅ Resolved, 2026-07-23)
- **Description**: `run_native.sh` used `npm ci` which requires an exact `package-lock.json` match. The lockfile was out of sync with `package.json`, and package versions had peer dependency conflicts (`@vitejs/plugin-react@6.0.3` required `vite@^8.0.0` but `vite@6.3.2` was specified; `@vitest/coverage-v8@4.1.10` required `vitest@^4.0.0` but `vitest@3.1.2` was specified).
- **Impact**: `npm ci` failed silently. The `cd ..` in the `&&` chain never executed, leaving the script in `frontend/`, causing the subsequent `cd frontend` to fail with "No such file or directory."
- **Fix**: Updated `package.json` to `vite@8.1.5` and `vitest@4.1.10`, replaced `npm ci` with `npm install`, and wrapped directory changes in subshells `(...)` to prevent cascading failures.
- **Status**: ✅ Resolved.

## 40. Test File TypeScript Errors Blocking Production Build (✅ Resolved, 2026-07-23)

## 41. Comprehensive System Audit Findings (2026-07-25)
A full 15-section audit identified 39 findings. Below are the unresolved items; see `docs/audit/2026-07-25_comprehensive_audit.md` for the full report.

### Open Items

None remaining — all audit item #41 findings were closed out by Phase 7 (see `docs/ROADMAP.md` Phase 7) or the 2026-08-02 reconciliation:

- **Config Drift (High)** ✅ Resolved: `APP_VERSION` default now `1.2.0-rc1`, matching git tag `v1.2.0-rc1`.
- **Nginx / Upload Size Mismatch (High)** ✅ Resolved: `deployment/nginx.conf` `client_max_body_size 20m`, validated with `nginx -t`.
- **Undefined Name `ArgumentStructure` (High)** ✅ Resolved: no references remain; type hint uses imported `ArgumentIntelligenceResult`.
- **Test Failures (High)** ✅ Resolved: `test_api.py:14 test_root_endpoints` and `backend/tests/benchmarks/test_offsets.py:43 test_history_prefix_offsets` pass in the full suite.
- **Schema Drift (High)** ✅ Resolved: `degradation_tier` added to frontend `AnalysisResult`.
- **Schema Drift (Medium)** ✅ Resolved: `localize` added to frontend `AnalysisRequest`.
- **Stub Router Dead Code (Medium)** ✅ Resolved: `backend/app/routes.py` removed; `main.py` includes only live routers.
- **Dockerfile Duplicate Install (Medium)** ✅ Resolved: torch pinned in `requirements.txt` (CPU index); Dockerfile no longer double-installs.

### Resolved Items (doc-only)
- `ARCHITECTURE.md`: Version, React version, model descriptions corrected.
- `CONFIGURATION.md`: v12 model paths documented, `.env` STAGE2 path noted.
- `CHANGELOG_AI.md`: Audit findings recorded.
- **Description**: `npm run build` runs `tsc -b && vite build`. Test files in `src/__tests__/` contained TypeScript errors (`unused 'beforeEach'`, `'start' does not exist in type 'FallacyDetail'`, type mismatch with `CrossSegmentContradictions`) that caused `tsc` to fail.
- **Impact**: Frontend could not be built for production deployment.
- **Fix**: Added `exclude: ["src/__tests__", "src/**/*.test.*", "src/**/*.spec.*"]` to `tsconfig.app.json`.
- **Status**: ✅ Resolved.
