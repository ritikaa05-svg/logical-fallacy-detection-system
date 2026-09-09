# LogiScan AI Changelog

## 2026-08-05 (Stage 1 v13 Gatekeeper + Legacy Model Retirement)

### Deployed
- **Stage 1 gatekeeper retrained (`stage1_v13_classifier`)**: replaces the degenerate `stage1_v12` (constant salience 1.000, macro F1 0.4954 = majority baseline). DistilBERT, 6 epochs, best-val-F1 checkpoint (trained on Kaggle T4x2 via `cloud_training/notebooks/defense_prep_training.ipynb`). Measured: **val F1 0.9974, test F1 0.9991** (n=1,155 each). Salience sanity: 0.999 / 0.004 / 0.999.
- **ONNX export**: `models/stage1_v13_classifier/model.onnx` (opset 18, dynamic batch/sequence), verified PyTorch vs ONNX-Runtime; backend loads it (`use_onnx=True` confirmed).
- **Path wiring**: `STAGE1_MODEL_PATH` → `./models/stage1_v13_classifier` in `.env`, `.env.example`, `backend/.env.production`, `backend/.env.staging`, `deployment/docker-compose.yml`; also fixed stale `phase4_final_model` refs for Stage 2/3 in the prod/staging env files (→ `stage3_v13_classifier`).

### Measurements
- **Split-seed variation** (Stage 3, identical config, 3 seeds, Kaggle T4): seed 42 → 0.8927, 2024 → 0.8792, 7 → 0.8832; **mean 0.885 ± 0.0069** (`results/seed_variation.json`).
- **Model-series benchmark** (`scripts/benchmark_model_series.py`, `docs/MODEL_COMPARISON.md`): stage1 0.4954→0.9272; phase4 0.8024→0.8756 (24-class subset); **stage3_v12 (archived) scores 0.9134 vs current 0.8971** — old RoBERTa-base leads on the standardized split incl. natural-text classes; kept as archival baseline for a documented re-deployment option.

### Cleanup
- **Deleted**: `models/stage1_v12` (degenerate), `models/phase4_final_model` (24-label predecessor), `models/stage1_v13_classifier.zip` (transport artifact).
- **Archived**: `models/stage3_v12` kept (see MODEL_COMPARISON.md).

## 2026-08-02 (Stage-3 v1.3 Model Deployment)

### Deployed
- **Stage-3 v1.3 29-class classifier live**: trained on Kaggle (T4x2, `nn.DataParallel`, batch 16/GPU, 6 epochs, sqrt-inverse-frequency CE, AMP) — DeBERTa-v3-small single-head matching the `phase4_final_model` architecture; supersedes the 24-label Phase 4 model.
- **New classes**: five rescued formal classes (`undistributed_middle`, `illicit_major`, `illicit_minor`, `exclusive_premises`, `existential_fallacy`) plus `denying_antecedent` (600) / `affirming_consequent` (555) expansions.
- **ONNX deployment format**: `models/stage3_v13_classifier/` ships `model.onnx` + `model.onnx.data` (opset 18, dynamic batch/sequence, logits `[batch, 29]`), loaded via ORT-CPU like the prior model. Verified: `affirming_consequent` @ 0.946 on a canonical sample, 224 ms CPU inference @ 256 tok.
- **Path wiring**: `STAGE2_MODEL_PATH`/`STAGE3_MODEL_PATH` → `./models/stage3_v13_classifier` in `backend/app/config.py`, `.env`, `.env.example`, `deployment/docker-compose.yml`, `deployment/copy_models.sh`; docs updated (`CONFIGURATION.md`, `AUDIT_FINDINGS.md`, `ROADMAP.md` Phase 8 #5).
- **No code changes required**: loader single-head path (`num_labels >= 24`), `SHADOW_COARSE_MAP` (all 29 labels), `SEVERITY_WEIGHTS` formal classes, and `document_router` formal set already supported the 29-class schema.
- **Training tooling**: `cloud_training/scripts/train_stage3_v13.py` + `cloud_training/stage3_v13_kaggle.ipynb` — DataParallel auto-wrap on >1 GPU, per-GPU batch preservation, unwrap-before-save/export, ONNX export cell.

## 2026-08-02 (Debate Agent Overhaul)

### Fixed
- **Debate drawer degenerate behavior**: `models/dqn_debate_policy.pt` never existed → `_rule_based_action` fired every turn (canned `AGREE_AND_PIVOT` loops, fallacy call-outs at ~13% confidence, naive mapping of greetings/questions/acks to pipeline turns).
- **DQN now has a seeded policy**: `scripts/train_dqn_debate.py` (behavior-cloning initialization) builds transitions from the v1.3 dataset (fallacy label → rule action, reward = pipeline confidence) and trains the DQN head; checkpoint saved to `models/dqn_debate_policy.pt` (3000 steps, avg_loss 0.0081). Loaded on startup when run from repo root (matching `run_native.sh`).
- **Intent detection** (`_detect_intent`): greetings, question leads, and ack phrases (short acknowledgements) are answered directly with social/reframing turns — no pipeline invocation, no spurious fallacy output.
- **Confidence gating**: `POINT_OUT_FALLACY` now requires top-label confidence ≥ `RL_POINT_CONF_FLOOR` (0.60, matching the reranker boundary); below it the action downgrades to `ASK_SOCRATIC` (config `backend/app/config.py`).
- **Per-session template de-dup**: `_pick_template` cycles through grounded Socratic templates without verbatim repeats within a session; responses quote the user's own phrase.
- **Debate turn logging** (`backend/app/services/debate_logger.py`): best-effort asyncpg writer to `debate_sessions`/`debate_turns` (per `deployment/init-db.sql`); no-ops safely when no real `DATABASE_URL` is configured (placeholder-DSN/asyncpg-missing guards).
- **Tests**: RL/debate coverage expanded to 78 tests (`backend/tests/test_rl_engine.py` — intent parametrization, gating above/below floor, de-dup cycles, grounding, defensive top-label, logger failure modes). Backend suite: 134 passed.
- **Verified live** on port 8766: greeting → social turn; "Can you learn without learning?" → Socratic reframe; "Maybe" → acknowledgement; "You are a bird hence you must fly" → `POINT_OUT_FALLACY` @ 0.94 (above floor, kept); "What does it mean?" → reframe request. No repeated templates.

## 2026-08-02 (Debt Liquidation Sweep, Phase 7 + Audit Reconciliation)

### Completed
- **Phase 7 debt liquidation**: all 32 items closed out — creds audit (no secrets ever in git), LLM fallback ladder + API model-id guard, educational-text FP guard before Stage 2/3, "Informal (Other)" validator, 5 missing formal-class signatures, torch CPU pin (`2.13.0+cpu`), `client_max_body_size 20m`, pydantic `example=` → `json_schema_extra`, frontend `degradation_tier`/`localize` schema sync + degraded badge, Z3/RL coverage backfill (95% branch, CI `--fail-under=80` gate), gitleaks pre-commit + CI secret scan.
- **Phase 6 deliverable done**: formal-class data rescue landed (v1.3 dataset: `denying_antecedent` 600, five formerly-zero classes at 500 each); Stage-3 retrain tracked under Phase 8 #5.
- **KNOWN_ISSUES #41 fully reconciled**: all audit findings resolved (config drift, nginx upload size, `ArgumentStructure`, test failures, schema drifts, stub router, Dockerfile duplicate torch).
- **Version hygiene**: `APP_VERSION` default synced to `1.2.0-rc1`, matching git tag `v1.2.0-rc1`.

## 2026-07-25 (Comprehensive System Audit & Documentation Update)

### Audit
- Completed 15-section comprehensive system audit of the entire LogiScan codebase.
- **39 findings**: 1 Critical, 9 High, 12 Medium, 17 Low.
- Full report generated covering Configuration, Dead Code, Type Safety, Tests, Schema Drift, Pipeline Integrity, Security, Model Integrity, Frontend Build, Infrastructure, Error Handling, Dependencies, and Style.

### Updated
- `docs/ARCHITECTURE.md`: Version string synced to `v1.2.0-rc1` (matching git tag). React version corrected from 18→19. Model stage descriptions updated to reflect actual production paths (`stage1_v12`, `stage2_v12`, `stage3_v12`) and coarse-via-fine derivation via `SHADOW_COARSE_MAP`.
- `docs/CONFIGURATION.md`: Added v12 model path documentation for production/staging overrides. Noted `.env` STAGE2_MODEL_PATH currently points to `stage3_v12` (RoBERTa) rather than a dedicated coarse model.
- `docs/KNOWN_ISSUES.md`: Added audit findings as Known Issue #41 (Comprehensive System Audit Findings).

## 2026-07-23 (Startup & Inference Hardening)

### Fixed
- **RateLimiter KeyError Crash**: In-memory fallback rate limiter raised `KeyError: '127.0.0.1'` on first request. Fixed all three `is_allowed`, `get_remaining`, and `get_reset` methods to use `self._clients.get(client_ip, [])` before dict access (`backend/app/core/security.py`).
- **BNB Dummy Pass CUDA Assert**: `_initialize_bnb` fed `torch.zeros` as dummy input, triggering CUDA device-side assert on RoBERTa-based models. Changed to use `pad_token_id` with a single `bos_token_id` at the final position (`backend/app/services/unified_classifier.py`).
- **Frontend Build Failure (npm ci)**: `package-lock.json` was out of sync with `package.json`; `@vitejs/plugin-react@6.0.3` required `vite@^8.0.0` but `vite@6.3.2` was specified. Updated to `vite@8.1.5` and `vitest@4.1.10`, replaced `npm ci` with `npm install` (`frontend/package.json`).
- **Test Files Blocking Production Build**: TypeScript errors in `src/__tests__/` caused `tsc -b` to fail. Excluded test files from `tsconfig.app.json` (`frontend/tsconfig.app.json`).
- **Script Directory State Leak**: Failed `npm ci` left `run_native.sh` in the wrong directory, causing cascading `cd` failures. Wrapped `cd` operations in subshells and removed hard `cd ..` dependencies (`run_native.sh`).

## 2026-06-20 (Hotfixes)

### Fixed
- UnifiedClassifier cache made thread-safe and flag-aware: internal in-process cache now keys on (text, include_explanations) and honors `skip_cache=True`. Cached results are deep-copied when returned to avoid shared mutable state.
- Prediction loader no longer blocks the event loop: model lifecycle loads are executed in a thread executor to prevent async stalls on first inference.
- StructuralParser regex hardened: multi-marker occurrences are handled, conclusion is taken from the final marker, premises are joined from earlier segments.
- Hugging Face Inference API fallback: added a dedicated `HF_MODEL_ID` config and robust retry/backoff (3 attempts) with timeout handling.
- Saliency contract clarified: `_process_logits` now returns `explanations_requested` boolean alongside `salient_tokens` so callers can distinguish "not requested" vs "no salient spans".
- Frontend extension updated to accept backend's `salient_tokens` dict format (token, score, start, end) while maintaining backward compatibility with legacy tuple format.
- Added `DISABLE_API_FALLBACK` environment setting to force local-only inference; DeviceManager now respects this flag and also disables fallback when no `HUGGINGFACE_API_TOKEN` is configured.
- LLMSynthesisService: implemented a small circuit-breaker for consecutive Hugging Face API failures (3 consecutive failures disables API attempts temporarily) and updated API-use logic to respect `DISABLE_API_FALLBACK`.
- Corrected taxonomy mapping: removed `false_dilemma` from `FORMAL_FALLACIES` in the orchestrator and updated `SHADOW_COARSE_MAP` to categorize `false_dilemma` as "Informal (Presumption)".
- Pipeline aggregation now propagates `argument_structure` from per-segment results into aggregated InferenceResult when available.
- Updated project .env example with commented `DISABLE_API_FALLBACK` instruction.

## 2026-06-15 (Phase 5: Argument Intelligence & Multi-Segment Processing)


### Added
- **Segmenter Preprocessor**: Implemented `backend/app/pipeline/segmenter.py` with structural delimiter support and `tiktoken`-based sliding windows.
- **Multi-Segment Aggregation**: Added result merging logic to `PipelineOrchestrator` for handling complex, long-form documents.
- **Sovereign Mode**: Enabled local LLM fallback for Phase 5 extraction, allowing 4-bit quantized inference on 4GB-class hardware.

### Improved
- **Radical Latency Reduction**:
    - Implemented **Strict Gating**: Stage 4 (Synthesis/Z3) is bypassed if Stage 2/3 detects no fallacy, saving ~15s per segment on CPU.
    - **Hybrid Structural Parsing**: Enforced Regex-first extraction with LLM fallback only for high-complexity claims.
    - **Token Optimization**: Reduced structural LLM token limits from 250 to 60.
- **Robust Argument Gating**: Refined the transition from structural analysis to classification. Implemented a **0.95 salience buffer** that prevents the structural parser from bypassing classification on high-certainty dialogues, fixing a regression where conversational fallacies (e.g., Straw Man) were missed.
- **Production Models**: Promoted hardened Phase 4.4 Stage 3 model to production, significantly reducing false positives on neutral text.

### Fixed
- **Phase 5 Blocker**: Resolved empty extractions by correcting Hugging Face repo IDs and relaxing residency restrictions.
- **Pydantic Validation**: Fixed type mismatch in structural parser where `is_argument` was receiving a list instead of a boolean, causing analysis crashes.
- **CPU Stall**: Eliminated 46s+ stalls by implementing Regex-first structural parsing and strict fallacy gating for heavy stages.

## 2026-06-14 (Phase 4.4: Fine Classifier Hardening)

### Added
- **Hardened Dataset**: Generated `unified_training_data_v1.1.json` (12,442 samples) with 1,656 targeted hard negatives.
- **Audit Tools**: Created `scripts/dataset_audit.py` for structural diversity analysis.

### Improved
- **Formal Logic Integrity**: Increased `valid_reasoning` diversity by 45%+ human-written content.
- **Boundary Robustness**: Added explicit non-argument samples to train Stage 1 and Stage 2 against technical false positives.

## 2026-06-12 (Production Stabilization & Phase 5 Scaffolding)

### Added
- **ONNX Migration**: Created `cloud_training/scripts/export_to_onnx.py` and converted Stage 1 and Stage 2 models to ONNX.
- **Phase 5 Scaffolding**: Implemented `StructuralParserService` and Pydantic schemas for premise/conclusion extraction.
- **Model Validation Report**: Created `docs/PHASE4_VALIDATION_REPORT.md` providing independent verification of model metrics.
- **Evidence Audit**: Created `docs/PHASE5_EVIDENCE_AUDIT.md` assessing the functional status of structural analysis.

### Fixed
- **VRAM Overflows**: Resolved 4GB OOM issues by offloading ONNX inference to CPU.
- **Latency Measurement**: Identified and resolved discrepancy between cold-start and steady-state latency (~240ms verified).
- **Background Thread Leak**: Converted model eviction timers to daemon mode to ensure clean process termination.

### Validated
- **Phase 4 Accuracy**: Reproduced 0.9067 Macro-F1 on internal set; measured 0.83 on real-world gold set.
- **Phase 5 Status**: Formally classified as "Scaffolding Only" due to non-functional extraction engine.

## 2026-06-07 (Phase 4 Milestone)

### Added
- **10.7K Unified Dataset**: Exceeded Phase 4 target (10,786 valid samples).
- **Taxonomy Expansion**: Integrated `valid_reasoning` and `factual_statement` into core classifier.
- **Numerical Safeguards**: Added `GradScaler` and Sqrt-Smoothing weight logic to prevent `NaN` loss.
- **Stabilized Training**: `Phase4_Train_Stabilized.ipynb` produced Macro-F1 of **0.8147**.
- **Audit Reports**: Created `LATENCY_AUDIT.md`, `MODEL_REALITY_CHECK.md`, `PHASE4_ERROR_ANALYSIS.md`, and `PHASE4_GO_NO_GO_REPORT.md`.

### Changed
- **Pipeline Optimization**: Reduced latency from 7000ms to 1400ms via selective residency caching.
- **Model Lifecycle**: Optimized `low_memory_mode` to prioritize Stage 1 residency on 4GB VRAM.
- **Data Quality**: Surgically relabelled mislabeled `false_cause` samples in core data.

### Fixed
- **NaN Loss Root Cause**: Identified weighted gradient overflow in FP16 as primary failure mode.
- **Forced Fallacy Bias**: Eliminated "must-pick-a-fallacy" behavior by providing valid logic buffer.

## 2026-06-06 (Current Session)

### Fixed
- **Model Loading Robustness**: Added `ignore_mismatched_sizes=True` to `AutoModelForSequenceClassification.from_pretrained` in `unified_classifier.py`.
- **Fallback Label Map**: Added `id2label` override when model config lacks `id2label`, preventing index-out-of-range on prediction.
- **Config Path Resolution**: Fixed config loading to use `os.path.join` and `os.path.expanduser` for robust path resolution across environments.
- **Local SMT Translation**: Created `local_smt_translator.py` — offline LLM-based SMT-LIBv2 generation using `SmolLM2-1.7B-Instruct` as Z3 fallback when API is unavailable.
- **Lexical Bias Mitigation**: Reduced false positives for "all", "always", "none" by 70% via `LexicalBiasMitigator` with weighted cross-entropy and augmented training data.
- **Script Resilience**: Sanitized `run_native.sh` with `set -e`, `cd` safety, and `sys.exit(1)` on Python errors.
- **Dead Code Cleanup**: Removed orphaned `neuro_symbolic.py` (Stage 4 synthesis) — logic moved into `local_smt_translator.py`.

### Added
- `backend/app/services/local_smt_translator.py`: Local LLM-based SMT rule generation for offline Z3 fallback.
- `backend/app/services/lexical_bias_mitigator.py`: Reduces false positives from lexically biased fallacy triggers.
- `docs/lexical_bias_report.md`: Analysis of lexical bias in fallacy detection.

## 2026-06-03 (Current Session)

### Fixed
- **UI/UX Overhaul**:
    - **Hover Fluidity**: Implemented stack-safe rendering, zero-flicker hover bridges, and visual pointer arrows.
    - **Theme Integrity**: Fixed "transparency leak" by implementing solid background fallbacks and full theme variable tokenization.
    - **Mobile Responsiveness**: Refactored the Fallacy Breakdown component to stack vertically on small screens.
- **System Stability**:
    - **Memory-Aware Loading**: Implemented dynamic VRAM detection to offload heavy models to CPU when below 4.5GB, preventing CUDA OOM.
    - **Architecture Binding**: Fixed DeBERTa-v3 key mismatches by explicitly using the custom `DebertaV3MultiHead` class during weight loading.
    - **NameError**: Restored missing `get_health_status` function in `app.py`.
- **Performance**:
    - **Timeout Resolution**: Increased frontend API timeout to 120s and fixed CUDA/CPU device mismatches for LLM inputs.
- **Bug Fixes**:
    - **Syntax Correction**: Fixed `SyntaxError` in `fallacy_breakdown.py` caused by unescaped f-string braces.
    - **Deprecation Cleanup**: Replaced `torch_dtype` with the modern `dtype` parameter to silence library warnings.

### Added
- **Keyboard Shortcuts**: Added `Ctrl+Shift+X` global shortcut to toggle "Skip Cache" in the dashboard.
- **Training Infrastructure**: Created `train_stage3.py` for 22-class model expansion and updated `train_stage1.py` for latest unified data.
- **Audits**: Completed `docs/UI_AUDIT.md`, `docs/MODEL_SCORECARD.md`, and `docs/DATASET_AUDIT.md`.

## 2026-06-01 (Current Session)

### Fixed
- **Phase 1: Critical Fixes Complete**
- **Phase 2: Code Health & Reliability Complete**
- **Phase 3: UX, Performance & Advanced Reasoning Complete**
    - **Item 1 (Unify UI)**: Consolidated all highlighting components to use the same robust event-based assembly engine.
    - **Item 2 (Health Tracker)**: Implemented full local logic health tracking with persistence and real-time visualization.
    - **Item 3 (Z3 Pro)**: Upgraded propositional regex fallback with negation support and aggressive term unification.
- **Unified Classifier**: Fixed multiple `NameError` and redundant logic issues.
- **Frontend**: Fixed `ValueError` in breakdown component and fully modernized the dashboard UI.

### Added
- `backend/app/services/health_tracker.py`: New persistence service for user scores.
- `docs/PHASE3_EXECUTION_PLAN.md` / `docs/PHASE3_RESULTS.md`
- `docs/ROADMAP.md`: Extended with Phases 4-6 (Argument Intelligence, Long-Form Analysis, Research Platform) and Strategic Direction.
- `scripts/validate_refactor.py` / `scripts/validate_z3.py` / `scripts/capture_baseline.py`

## 2026-05-31

### Fixed
- Resolved `pytest-asyncio` configuration errors and `utcnow()` deprecation warnings.
- Fixed `DebateAction` validation error for negative Q-values.
- Corrected `Z3Service` regex variable name generation tests.
- Added `psutil` to `backend/requirements.txt`.

### Changed
- Migrated Pydantic models to use `ConfigDict`.
- Refined `conftest.py` for better service mocking.
