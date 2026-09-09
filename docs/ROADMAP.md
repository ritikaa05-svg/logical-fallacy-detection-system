# LogiScan Development Roadmap

## Phase 1: Critical Fixes — Complete
1.  **Fix XAI Offset Heuristic**: Resolved with `OffsetMapper` class.
2.  **Enable Redis Cache**: `skip_cache` logic restored.
3.  **Populate Test Suite**: Unit/integration tests added for 4-stage pipeline.
4.  **Resolve Offset Drift**: Offset tracking refactored with robust token-to-char mapping.

## Phase 2: Code Health & Reliability — Complete
1.  **Refactor Unified Classifier**: Consolidated models into single DeBERTa-v3 Multi-Head.
2.  **Improve LLM Synthesis**: Real generation via `SmolLM2-1.7B-Instruct` (local).
3.  **Enhance Z3 Translation**: Local LLM fallback translator provides offline SMT generation.

## Phase 3: UX & Performance — Complete
1.  **Unify Highlighting Logic**: Highlighting refined with char-level stateful tracking.
2.  **Optimize Inference Latency**: Steady-state latency reduced to ~240ms via ONNX migration.
3.  **Saliency-Free Fallback**: Highlight alignment restored for CPU/API-only environments.
4.  **React SPA Frontend**: Replaced Streamlit dashboard with a Vite + React 19 + TypeScript + Tailwind SPA.
    - AnnotatedText component with stack-based overlapping-span highlighting and XAI tooltips (top-contributing token display).
    - Analysis, Debate, Health, and Status pages with react-router-dom routing.
    - Static build (~181 KB gzipped) served by FastAPI via `StaticFiles`.

## Phase 4: Production Stabilization — Complete
1.  **Synchronized Retraining**: All three stages retrained on the hardened dataset (v1.1→v1.3, 12.4K→17.9K). Stage 1: `stage1_v12` (DistilBERT). Stage 2: `stage2_v12` (DistilBERT, 6 coarse labels). Stage 3: `stage3_v12` (RoBERTa, 29 fine labels). Deployed via `.env` overrides.
2.  **ONNX Migration**: Converted all ML stages to ONNX for CPU-sovereign inference.
3.  **False Positive Mitigation**: Reduced false positives on neutral text by 90% via hardened Stage 3.
4.  **Config Drift Awareness**: `.env` still points `STAGE2_MODEL_PATH` at `stage3_v12` (RoBERTa), not `stage2_v12` (DistilBERT). Coarse categories are derived from fine-label distribution via `SHADOW_COARSE_MAP`, which works but bypasses the dedicated coarse head in `stage2_v12`. See `AUDIT_FINDINGS.md` item 1.2.

## Phase 5: Argument Intelligence — Complete
1.  **Structural Extraction**: Implemented hybrid Regex/LLM parser for premises and conclusions.
2.  **Multi-Segment Support**: Implemented structural and sliding-window segmentation.
3.  **Local LLM Fallback**: Enabled 4-bit quantized local synthesis for sovereign mode.
4.  **Latency Gating**: Reduced processing time by 90% via strict fallacy gating.

## Phase 6: Document-Scale & Professional Analysis — Complete
- **Objective**: Analyze reasoning across entire documents and multi-page transcripts.
- **Deliverables**:
    - **PDF/Doc Ingestion**: Automated extraction from professional document formats via `POST /api/v1/documents/upload`. ✅ Complete.
    - **Document Upload UI**: File drag-and-drop zone (PDF/DOCX/TXT) on the Analysis page with mode toggle (Text / Document), upload progress states, and per-page result browsing. ✅ Complete.
    - **Cross-Segment Contradiction**: Detect logical inconsistencies between different parts of a document, surfaced as severity-ranked contradiction cards in the frontend. ✅ Complete.
    - **Professional Reporting**: Generate structured PDF/JSON reasoning audits with a "Download Report" button on the Analysis page (PDF + JSON formats). ✅ Complete.
    - **Refine Formal Recall**: Targeted retraining for complex formal classes (`denying_antecedent`). 🟡 Data-rescue complete (v1.3 dataset: `denying_antecedent` 600, five formerly-zero formal classes at 500 each). The Stage 3 retrain itself is tracked under Phase 8 #5.
- **⚠ Known Blockers**: None. (nginx `client_max_body_size` was 1m, blocking uploads >1 MB; raised to `20m` in Phase 7 #26, matching `MAX_FILE_SIZE_MB=20`.)

## Phase 7: Debt Liquidation & Pipeline Integrity — Complete
- **Objective**: Eliminate every known blocker, security vulnerability, dead-code path, and correctness bug before scaling the system further.
- **Deliverables**:
     1.  **Credential Rotation**: Revoke any exposed HuggingFace API tokens in `.env` history, migrate all secrets to a vault-backed injection pattern, and add a pre-commit hook that rejects plaintext tokens. — ✅ Audited 2026-08-02: **no real secrets ever entered git history** (`.env` never tracked on any branch/dangling commit; only tracked env files are `.env.example`, `.env.staging`, `.env.production`, all with inert `hf_<REPLACE_WITH_YOUR_TOKEN>` / `changeme` placeholders). `config.py:155-165` already rejects plain `hf_` tokens under `LOGISCAN_ENV=production`. Gitleaks added to pre-commit + CI `secret-scan` job 2026-08-02 (verified: no leaks); vault-backed injection is aspirational (tracked in Phase 9).

     2.  **Structural Parser Recovery**: Fix the Phase 5 Regex/LLM premise-conclusion parser — resolve OOM by streaming inference, replace hard-coded HF auth with the rotated credential flow, and add a pure-regex fallback for fully offline environments. — ✅ Re-audited 2026-08-02: parser is regex-first (4-strategy chain, `structural_parser.py:218-231`) with LLM as last resort gated on `STAGE4_IS_LOCAL_PATH`; no hardcoded auth anywhere (all via `settings.HUGGINGFACE_API_TOKEN`); input capped at `MAX_INPUT_TOKENS` upstream (no unbounded OOM vector). Residual defects found: `llm_service.py:129-132` quantized-load failure logs "falling back" but re-raises (no real fallback); `llm_service.py:283-288` can send the local filesystem path as HF API `model_id` when API fallback is active. — ✅ Fixed 2026-08-02 (real fallback ladder + API model-id guard, tests added).
     3.  **Health Tracker Concurrency Fix**: Eliminate the race condition in `health_tracker.py` by adding a threading lock with in-memory storage and best-effort disk persistence. — ✅ Completed
     4.  **Dead Code Purge**: Remove the unreachable `TimeoutError` handler in `middleware.py` by switching to explicit `app.add_exception_handler()` registration order. — ✅ Completed
     5.  **RL Mode Guard**: Add an explicit `LOGISCAN_ENV` flag (`training` / `production`) so the debate agent disables epsilon-greedy exploration in production; default to `production`. — ✅ Completed
     6.  **API-Fallback Fix**: Correct the LLM breakdown boolean logic in `orchestrator.py` so synthesis runs when API fallback is active. — ✅ Completed
     7.  **Test Coverage Backfill**: Populate the empty Z3 translation and RL engine test files with at least 80% branch coverage; integrate into CI as a gating check. — ✅ Completed 2026-08-02 (`test_z3.py` + `test_rl_engine.py` backfilled to 44 tests, branch coverage 95%; CI `coverage run --branch` + `--fail-under=80` gate added).
     8.  **Extension CSP Compliance**: Replace all inline event handlers in the Chrome extension settings page with `addEventListener` bindings to restore toggle functionality and pass Manifest V3 CSP. — ✅ Completed (verified 2026-08-02: zero inline handlers remain; KNOWN_ISSUES #26)
     9.  **Extension Settings Persistence**: Replace in-memory settings with `chrome.storage.local` so popup settings persist across popup opens and are readable by `background.js` for context menu / keyboard shortcut invocations. — ✅ Completed (verified 2026-08-02: popup.js + content_script.js + background.js all storage-backed; KNOWN_ISSUES #33/#35)
     10. **Unbounded Translation Cache**: Replace the module-level dict in `llm_translator.py` with a thread-safe LRU cache (max 1024 entries) to prevent memory leaks. — ✅ Completed
     11. **Coarse Confidence One-Hot Fix**: Derive coarse category probabilities from the fine-label distribution instead of hardcoding 1.0 confidence in `unified_classifier.py` single-head and ONNX paths. — ✅ Completed
     12. **Z3 Temp File Leak**: Wrap `subprocess.run` in `z3_service.py` with try/finally to ensure temp SMT files are cleaned up on exception. — ✅ Completed
     13. **Device Selection Bypass**: Replace direct `torch.cuda.is_available()` with `device_manager.get_torch_device()` in `unified_classifier.py` to respect MPS detection. — ✅ Completed
     14. **import math Inside Function Body**: Move `import math` from inside `_heuristic_predict` to module level in `stage1_gatekeeper.py`. — ✅ Completed
       15. **Educational Text False Positives**: Extend the Description Guard in `orchestrator.py` with educational-framing patterns to suppress false detections on text *describing* fallacies (Known Issue #14). — ✅ Completed (verified 2026-08-02: guard fires at `orchestrator.py:640-654` **before** Stage 2/3 and forces a non-argument early return, so both ML and LLM paths are guarded; KNOWN_ISSUES #14 updated)
       16. **API Response Parsing Robustness**: Add defensive format detection in `unified_classifier.py` HF API fallback path — different model tasks return different JSON shapes; detect format rather than assuming list-of-dicts. — ✅ Completed
       17. **Local vs Remote Path Detection**: Replace fragile heuristic prefix matching for local model paths in `llm_service.py` with an explicit config flag or `local_files_only` parameter. — ✅ Completed (via `STAGE4_IS_LOCAL_PATH`)
       18. **Nginx Config Alignment**: Fix `deployment/nginx.conf` — the upstream `frontend` host referenced at line 10 does not exist in `docker-compose.yml`. Either add a frontend container or update nginx to point to the combined service. — ✅ Completed
       19. **Dead Code Cleanup**: Remove unused `CATEGORY_PATTERNS` from `stage2_coarse.py` and empty stub files in `frontend/streamlit/components/`. — ✅ Completed (verified 2026-08-02: `CATEGORY_PATTERNS` gone; `stage2_coarse.py` is a 22-line shim over `unified_classifier`; `frontend/streamlit/components/` holds only the used `fallacy_breakdown.py`; KNOWN_ISSUES #34)
       20. **Dataset Documentation Sync**: Update `docs/DATASET_MASTER.md` to reflect the actual 12,442 sample count in `unified_training_data_v1.1.json`. — ✅ Completed (verified 2026-08-02: doc matches actual counts for v1.1.0/v1.2.0/v1.3.0)
       21. **Orphan Artifact Cleanup**: Investigate and remove the empty `.zip` file in `data/`. — ✅ Completed (verified 2026-08-02: no `.zip` files remain; KNOWN_ISSUES #34)
       22. **Debug Log Level Cleanup**: Move debug log statements at INFO level in `orchestrator.py` and `z3_service.py` to `logger.debug()`. — ✅ Completed (verified 2026-08-02: remaining `logger.info` calls in orchestrator are operational summaries; z3_service has zero INFO)
       23. **Unused Import Cleanup**: Remove unused `plotly.express` import from `frontend/streamlit/app.py`. — ✅ Completed (verified 2026-08-02: app.py imports `plotly.graph_objects as go`, which is used)
       24. **Empty `overlay.css`**: Either populate with actual styles or remove from `manifest.json` declaration. — ✅ Completed (verified 2026-08-02: file and manifest declaration removed; KNOWN_ISSUES #34)
       25. **`_initialize_bnb` Input Shape**: Fix dummy input dimensions in `unified_classifier.py` to match DeBERTa's expected input shape from config. — ✅ Completed (verified 2026-08-02: `seq_len` from `model.config.max_position_embeddings`, pad-filled with single trailing BOS; KNOWN_ISSUES #38)
       26. **Nginx client_max_body_size**: Increase from `1m` to `20m` to match `MAX_FILE_SIZE_MB=20` for document upload support. — ✅ Completed 2026-08-02 (`deployment/nginx.conf:23`, validated with `nginx -t`)
       27. **Undefined Type `ArgumentStructure`**: Fix `orchestrator.py:115` — `ArgumentStructure` is used in a type hint but never defined. — ✅ Completed (verified 2026-08-02: zero references remain; hint uses imported `ArgumentIntelligenceResult`)
       28. **Frontend Schema Sync**: Add `degradation_tier` and `localize` fields to frontend `AnalysisResult` / `AnalysisRequest` types. — ✅ Completed 2026-08-02 (types synced in `frontend/src/types/api.ts`; degraded-mode badge shown when `degradation_tier > 0`)
       29. **Stage 3 Label Coverage**: Add discourse signatures for the 5 formal classes currently missing from `FALLACY_SIGNATURES` (`exclusive_premises`, `existential_fallacy`, `illicit_major`, `illicit_minor`, `undistributed_middle`). — ✅ Completed 2026-08-02 (all 5 added; test asserts every fine label has a signature)
       30. **Coarse Validator Expansion**: Add `"Informal (Other)"` to the `Stage2Result.coarse_category` validator set. — ✅ Completed 2026-08-02 (validator + downstream coarse maps + test)
       31. **Stub Router Deprecation**: Remove `backend/app/routes.py` stub router and its inclusion in `main.py` — superseded by `v1/debate_router.py`. — ✅ Completed (verified 2026-08-02: file no longer exists; `main.py:102-110` includes only live routers)
       32. **Duplicate `pip install torch`**: Remove the explicit CPU torch install from `deployment/Dockerfile:13` — `requirements.txt` handles it. — ✅ Completed 2026-08-02 (`torch==2.13.0+cpu` pinned with `--extra-index-url https://download.pytorch.org/whl/cpu` in `backend/requirements.txt`; Dockerfile line removed)

## Phase 8: Training Alignment & Extraction Accuracy — Planned
- **Objective**: Close the distribution gap across all ML stages and bring quote extraction from 0% to production-grade accuracy.
- **Deliverables**:
     1.  **Synchronized Full-Pipeline Retraining**: Retrain Stages 1 and 2 on the same 12.4K hardened dataset already used for Stage 3, ensuring consistent decision boundaries across the entire classification pipeline.
     2.  **Quote Extraction Overhaul**: Replace the current extraction heuristic with a span-prediction head (token-level start/end logits) fine-tuned on annotated fallacy spans, targeting greater than 70% exact-match F1.
     3.  **Contrastive Hard-Negative Mining**: Generate adversarial near-miss examples (valid arguments structurally similar to known fallacies) and inject them into the training set to harden Stage 1 detection precision.
     4.  **Evaluation Harness**: Build an automated benchmark suite that reports per-stage precision, recall, F1, and exact-match rate on every commit, replacing manual smoke tests.
      5.  **Formal Class Data Rescue**: Six of seven formal fallacy classes have **zero training samples** in the current dataset. Generate at least 300–500 examples each for `undistributed_middle`, `illicit_major`, `illicit_minor`, `exclusive_premises`, and `existential_fallacy`. Expand `denying_antecedent` from 100 to 500. Retrain Stage 3 on the augmented dataset. — ✅ Complete: v1.3 dataset (500/class, `denying_antecedent` 600); Stage-3 retrain trained on Kaggle (T4x2, DataParallel) and deployed as `models/stage3_v13_classifier` (29 classes, ONNX).
      6.  **Synchronized Retraining (All Stages)**: Retrain Stage 1 (DistilBERT gatekeeper) and Stage 2 (coarse classifier) on the same 12.4K hardened dataset already used for Stage 3. Create a training script for Stage 2, which currently has none. This closes the distribution mismatch gap tracked in `AUDIT_FINDINGS.md` #10.
      7.  **Benchmark CI Gate**: Integrate the evaluation harness into the CI pipeline (`ci.yml`) so that per-commit benchmark reports are generated and a regression gate blocks PRs that degrade F1 by more than a configurable threshold.
      8.  **Affirming Consequent Recall Fix**: Address the 0.39 recall gap — the primary blocker from `BLOCKERS.md`. Targeted hard negative expansion completed; this item tracks the actual retraining and validation.

## Phase 9: Production Hardening & Observability — In Progress
- **Objective**: Make LogiScan deployable as a reliable, multi-user service with real-time health visibility.
- **Deliverables**:
     1.  **Persistent Rate Limiting**: Replace the in-memory rate limiter (`security.py`) with a Redis-backed sliding-window implementation that survives restarts and works across multiple backend instances. Support per-user / per-IP tiered rate limits.
     2.  **Health Tracker Redis Migration**: After the concurrency fix, optionally migrate health state from file-based JSON to Redis so multi-worker deployments share a single health history.
     3.  **Structured Logging & Metrics**: Instrument every pipeline stage with OpenTelemetry spans and export latency, throughput, and error-rate metrics to a Prometheus-compatible endpoint. Add a unique request ID to every log line for traceability.
      4.  **Researcher's Dashboard (Phase 1)**: Build a read-only web UI that visualizes Symbolic Traces — Z3 proof trees rendered alongside ML confidence scores and saliency maps for each detected fallacy. — ✅ Complete: real `GET /api/v1/traces/{analysis_id}` endpoint backed by `trace_store.py` (file-persisted, `data/traces/`); orchestrator captures rich trees (SMT script, Z3 model, parsing confidence, saliency) per `analysis_id` (reuses `X-Request-ID`); frontend TraceView wired via `FallacyCard` → `/traces/:analysisId`.
      4.1 **Classifier Load Regression Fix**: The model-path consolidation removed `ENABLE_SHADOW_MODE`/`SHADOW_MODEL_PATH` from `Settings` while `unified_classifier._load()` still accessed them → every request crashed on load, fell back to mock predictions (scattered single-word highlight spans) and reloaded the model per segment (~2.5s/segment latency). — ✅ Complete: config fields restored (defaults `false`/`None`), hard attribute access replaced with `getattr()` guards; scripts (`latency_audit.py`, `final_measurement.py`) fixed via config restore. Frontend: last analysis persisted to `sessionStorage` and hydrated on mount so TraceView/browser back-navigation and clickable History rows restore the full result (full `AnalysisResult` stored in `historyStore` for the 10 most recent entries). Also fixed: the `/{path:path}` SPA catch-all shadowed the root `/health/live` + `/health/ready` probes (registered after the catch-all); probes now register before the SPA block, and `test_root_endpoints` updated for SPA HTML at `/`. — **Page-label regression (2nd report)**: `orchestrator._aggregate_with_contradictions` defaulted `page_number` to `idx + 1` even for text-mode (paragraph) analysis, mislabeling every segment as "Page N" (`Page 7 ↔ Page 9` with dead "View Page" buttons). ✅ Complete: fallback removed (`seg_dict.get("page_number")`, `None` unless a real `int`), regression tests added (backend `test_paragraph_contradictions_have_no_page_labels`, frontend "labels paragraph contradictions as segments, not pages").
      4.2 **Debate Agent Usable Policy**: The DQN debate agent had no trained checkpoint, so action selection fell back to `_rule_based_action` (canned, repeating templates; fallacy call-outs at ~13% confidence). — ✅ Complete: behavior-cloning seed via `scripts/train_dqn_debate.py` (state = depth/density/sentiment/logic; transitions from v1.3 labels; 3000 steps → `models/dqn_debate_policy.pt`), intent detection (greetings/question-leads/acks skip the pipeline), `POINT_OUT_FALLACY` confidence floor (`RL_POINT_CONF_FLOOR=0.60`, downgrades to `ASK_SOCRATIC` below), per-session template de-dup, user-phrase grounding, and best-effort debate turn logging to Postgres (`debate_logger.py`, `debate_sessions`/`debate_turns`). Backend suite: 134 tests passing (78 in RL/debate scope).
     5.  **Containerized Deployment**: Publish a production-grade `docker-compose.yml` (backend, Redis, dashboard) with health checks, resource limits, liveness/readiness probes, and a one-command `make deploy` target.
     6.  **Graceful Degradation Policy**: Define and enforce a formal degradation ladder — when GPU is unavailable, fall back to ONNX-CPU; when the local LLM OOMs, fall back to API; when the API is down, fall back to rule-based synthesis — with each transition logged as a structured event.
     7.  **Docker Health Checks**: Add proper `HEALTHCHECK` directives and container health endpoints to the Docker Compose setup so orchestrators (Kubernetes, Docker Swarm) can manage the lifecycle.
     8.  **Pre-Commit Hook Integration**: Add `pre-commit` config (`.pre-commit-config.yaml`) with hooks for `ruff`, `mypy`, and a custom secret scanner to prevent plaintext credentials from being committed.
     9.  **Staging / Production Config Separation**: Introduce environment-specific config files (`.env.staging`, `.env.production`) with validation on startup that the correct file is loaded.
     10. **Dependency Audit**: Pin all dependencies to exact versions and add a weekly Dependabot / Renovate config for automated security update PRs.
     11. **Zero-Downtime Deployments**: Add a second backend replica to docker-compose and configure the nginx reverse proxy for rolling updates without dropping in-flight requests.

## Phase 10: Cross-Document Reasoning & Multimodal Expansion — Planned
- **Objective**: Extend LogiScan beyond single-document analysis into cross-document reasoning graphs and multimodal input streams.
- **Deliverables**:
     1.  **Cross-Document Contradiction Graph**: Build a document-linking layer that ingests a corpus (e.g., a set of policy papers or debate transcripts), extracts per-document argument structures, and detects inter-document contradictions and unsupported assumptions using Z3 satisfiability checks.
     2.  **Argument Knowledge Base**: Persist extracted premises, conclusions, and fallacy annotations into a queryable graph store (e.g., Neo4j or in-memory property graph) to support longitudinal reasoning audits across document versions.
     3.  **Audio/Video Transcription Pipeline**: Integrate Whisper-based transcription to accept audio and video inputs, segment speaker turns, and feed each segment through the existing fallacy-detection pipeline.
     4.  **Real-Time Streaming Mode**: Implement a WebSocket-based streaming interface that accepts live transcript chunks (from meetings, debates, or lectures) and returns fallacy annotations with sub-second latency.
     5.  **Researcher's Dashboard (Phase 2)**: Extend the dashboard with a corpus-level view — interactive argument graphs, cross-document contradiction highlighting, and temporal drift analysis across document versions.
     6.  **Plugin Ecosystem**: Publish a stable extension API so third-party tools (Google Docs add-on, VS Code extension, Slack bot) can submit text and receive structured fallacy reports without coupling to LogiScan internals.

## Phase 11: Frontend Quality & Test Expansion — Planned
- **Objective**: Bring frontend test coverage and robustness to parity with the backend.
- **Deliverables**:
     1.  **Page Component Tests**: Write `vitest` + `@testing-library/react` tests for the Analysis, Health, and Status pages — covering rendering, loading states, error states, and empty data.
     2.  **Integration Test for Analysis Flow**: Test the full Analysis page flow: user types text → clicks Scan → API mock returns result → AnnotatedText renders with correct highlights.
     3.  **Toast Notification System Tests**: Test toast success, error, and dismiss behavior.
     4.  **DebateDrawer Component Tests**: Test optimistic streaming, typing indicator, action color badges, and close behavior.
     5.  **Accessibility Audit**: Run `axe-core` on all pages and fix violations — focus management, ARIA labels, color contrast, keyboard navigation.
     6.  **Mobile Responsiveness Tests**: Verify all pages render correctly at common breakpoints (320px, 768px, 1024px, 1440px).
     7.  **Error Boundary Coverage**: Test that ErrorBoundary correctly catches rendering errors on each page and that the "Try again" reset button recovers state.

## Phase 12: API Surface & Documentation Maturity — Planned
- **Objective**: Make the API a first-class product with comprehensive docs, versioning strategy, and SDK support.
- **Deliverables**:
     1.  **OpenAPI Specification Completeness**: Audit `/openapi.json` for missing response schemas, error codes, and endpoint descriptions — patch any gaps in Pydantic models.
     2.  **API Versioning Strategy**: Define and implement a long-term API versioning policy (URL-based `/api/v2/` vs header-based) with deprecation notices and migration guides.
     3.  **Rate Limit Response Headers**: Standardize rate limit headers across all endpoints — `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After` — consistent with RFC 6585.
     4.  **Interactive API Playground**: Ship a lightweight browser-based API explorer (separate from Swagger UI) that lets users paste text, tweak parameters, and see formatted results without writing code.
     5.  **Client SDK (Python)**: Publish a `logiscan-client` PyPI package with type-hinted async/sync methods for all endpoints, automatic retry, and result model bindings.
     6.  **Client SDK (TypeScript / JavaScript)**: Publish an npm package for browser and Node.js usage, targeting the Chrome extension and web app integrators.
     7.  **Changelog & Migration Guides**: Maintain `CHANGELOG.md` with breaking changes, deprecation notices, and migration paths for each API version bump.

## Phase 13: Community & Ecosystem — Planned
- **Objective**: Grow LogiScan into an open-source community project with contributions, evaluation leaderboards, and real-world deployments.
- **Deliverables**:
     1.  **Public Evaluation Leaderboard**: Host a leaderboard (via GitHub Pages or a lightweight API) where researchers can submit their models for standardized evaluation on the LogiScan benchmark suite.
     2.  **Contributing Guide**: Write `CONTRIBUTING.md` with development setup, coding standards, PR workflow, and a beginner-friendly issue tag system.
     3.  **Model Zoo**: Publish pre-trained model checkpoints (Stage 1-3) on Hugging Face Hub with model cards documenting training data, performance metrics, and intended use.
     4.  **Community Datasets Curation**: Curate and publish community-contributed fallacy datasets with standardized annotation guidelines, inter-annotator agreement metrics, and license compatibility.
     5.  **Benchmarking Harness as a CLI Tool**: Extract the evaluation harness into a standalone `logiscan-bench` CLI tool that anyone can run against their own dataset without setting up the full backend.
     6.  **Conference / Workshop Paper**: Prepare a system demonstration paper for venues like ACL (demo track), EMNLP (demo), or AAAI — describing the neuro-symbolic architecture, benchmark results, and design lessons.

---

## Strategic Direction

### Current Strengths
- **Surgical UX**: Precise highlighting and absolute offset accuracy relative to user text.
- **Hybrid Reasoning**: Combines deep learning classification with symbolic logic verification (Z3).
- **Resource Optimized**: Runs full analysis on 4GB VRAM hardware via ONNX and memory-aware loading.
- **Sovereign Inference**: Full offline capability with no cloud dependency when `DISABLE_API_FALLBACK=true`.

### 12-Month Vision
1.  **Industry Standard**: LogiScan will become the reference implementation for reasoning-integrity auditing, with reproducible benchmarks and a public evaluation leaderboard.
2.  **Researcher's Dashboard**: A specialized UI to visualize Symbolic Traces (Z3 proofs) alongside ML predictions, deployed as part of the core distribution.
3.  **Cross-Document Reasoning**: Move beyond single-document analysis to corpus-scale logical consistency, powered by argument knowledge graphs.
4.  **Multimodal Logic**: Real-time reasoning analysis for audio and video streams via integrated transcription and streaming fallacy detection.
5.  **Production-Grade Reliability**: Zero-downtime deployments, persistent rate limiting, structured observability, and a formal graceful-degradation policy across all inference paths.
6.  **Community-Driven Benchmarks**: An open leaderboard where researchers compete on fallacy detection accuracy, driving progress in the field through reproducible evaluation.
