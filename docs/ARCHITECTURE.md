# LogiScan System Architecture (v1.2.0-rc1)

## Overview
LogiScan is a 4-stage neuro-symbolic pipeline designed for detecting and explaining logical fallacies in natural language. It combines deep learning classifiers with formal verification (Z3) and lightweight heuristic evidence extraction.

## System Components

### 1. Backend (FastAPI)
- **API Layer**: Provides RESTful endpoints for text analysis.
- **Pipeline Orchestrator**: Coordinates the multi-stage detection flow.
- **Service Layer**:
  - `Segmenter`: Structural delimiter and sliding window pre-processor with boundary normalization for mid-text delimiters.
  - `UnifiedClassifier`: Core ML inference (ONNX-optimized for CPU). Notes: internal in-process cache is now keyed by (text, include_explanations) and supports `skip_cache=True`; cached objects are deep-copied before returning to callers for safety. Model lifecycle loading is executed in a threadpool to avoid blocking the async event loop on first access. Shadow-model loading is guarded with `getattr()` so removing shadow settings from config cannot crash `_load()` (regression fixed; `ENABLE_SHADOW_MODE`/`SHADOW_MODEL_PATH` restored to `Settings` with defaults `false`/`None`).
  - `Z3Service`: Formal verification for deductive arguments.
  - `LLMSynthesisService`: Generates human-readable corrections (with API fallback). The HF Inference API fallback uses a dedicated `HF_MODEL_ID` configuration and implements retry/backoff and timeout handling.
  - `StructuralParser`: Hybrid (Regex + LLM) argument extraction. Regex-first policy: LLM only invoked if regex confidence < 0.8. Regex extraction has been hardened to correctly handle multiple marker occurrences (conclusion from last marker).
  - `CacheService`: Redis-backed result caching. The pipeline also maintains an in-process cache for very fast repeated single-process calls (see `UnifiedClassifier`).
  - `TraceStore`: File-backed persistence (`data/traces/{analysis_id}.json`, retained up to `TRACE_MAX_FILES`) of per-analysis symbolic trace trees. Trees are built from the `InferenceResult` (plus the live `Z3Context` on uncached runs, which includes the SMT script, Z3 model output, and parsing confidence). Each `/analyze` response carries an `analysis_id` (the middleware `X-Request-ID`); `GET /api/v1/traces/{analysis_id}` serves the tree to the frontend TraceView page.
  - `Frontend Contract`: Classifier results now include `explanations_requested` alongside `salient_tokens` so frontends can distinguish "explanations not requested" vs "no salient spans found". The frontend extension accepts `salient_tokens` as a list of dicts ({token, score, start, end}) while remaining backward-compatible with legacy tuple formats.

### 2. Machine Learning Pipeline (Stabilized)

- **Stage 1: Gatekeeper (DistilBERT)**: Binary filter for logical claims. Optimized for CPU. Production path: `models/stage1_v13_classifier` (DistilBERT, 2 labels, ONNX).
- **Stage 2: Coarse Classifier (DeBERTa)**: 24-label single-head classification; coarse categories are derived from the fine-label distribution. Production path: `models/phase4_final_model` (DeBERTa-v3, single-head, 24 labels).
- **Stage 3: Fine-Grained Classifier (DeBERTa)**: 24-label fine-grained fallacy detection. Production path: `models/phase4_final_model` (DeBERTa-v3, single-head, 24 labels). Uses lexical bias mitigation for low-support classes and LLM reranker for rare classes.
- **Stage 4: Symbolic (Z3 SMT Solver)**: Formal verification for formal classes (e.g., Affirming the Consequent). Only runs when coarse category is "Formal".
- **Stage 4: Synthesis (SmolLM2 / API)**: Generates human-readable corrections. **Gated: only runs if a fallacy is detected.** Degradation ladder: local LLM → API fallback → rule-based template.

## Data Flow (Non-Blocking)

1. **User Input**: User submits text (Direct or via multiturn history).
2. **Segmentation**: `Segmenter` normalizes boundaries (inserts newlines at implicit sentence boundaries to enable mid-text delimiter matching), then splits into logical sections or sliding windows.
3. **Context Mapping**: `OffsetMapper` preserves char-level offsets across segments and history.
4. **Stage 1 (Gatekeeper)**: Determines logical salience per segment.
5. **Structural Parser (Hybrid)**: Hybrid extraction of premises/conclusions. Bypasses LLM for non-claims, uses Regex-first logic, and respects `fast_path` mode.
6. **Stage 2/3 (Classification)**: ONNX-based inference detects fallacy type and broad category.
    - **Refined Argument Gate**: Bypasses classification ONLY if the parser identifies a non-argument AND Stage 1 salience is low (< 0.95). High-salience text (e.g., conversational fallacies) is always analyzed by the ML heads to prevent false negatives.
7. **Strict Gating**: If no fallacy is detected, Stage 4 is bypassed for 95% latency reduction.
8. **Evidence Extraction**: `_extract_quote_offline` uses a 3-tier pipeline (structural parser Tier 0.5, saliency anchor Tier 1, discourse segmenter Tier 2). Achieves **100% exact match rate** and **0% whole-text fallback** on benchmark. Guarded by `MAX_QUOTE_CHARS=200`.
9. **Annotation Construction**: Orchestrator builds annotations from extracted quotes (Saliency-free fallback).
10. **Aggregation**: `PipelineOrchestrator` merges segment results into a unified `InferenceResult` with aligned confidence scores.
11. **Response**: Result returned with precise offsets and structure.
12. **Trace Persistence**: Orchestrator stores a symbolic trace tree keyed by the request's `X-Request-ID` (surfaced as `analysis_id`); cached hits rebuild a minimal tree from the cached result.

## Diagram
```mermaid
graph TD
    User((User)) -->|Input Text| API[FastAPI API]

    subgraph Pipeline Orchestrator
        SEG[Segmenter Preprocessor] --> S1[Stage 1: Gatekeeper ONNX]
        S1 --> S5[Structural Parser Hybrid]
        S5 --> S23[Stage 2/3: Unified Detection ONNX]
        S23 --> GATE{Fallacy Detected?}
        GATE -->|No| AGG[Aggregator]
        GATE -->|Yes| S3[Stage 3: Z3 Solver]
        GATE -->|Yes| S4[Stage 4: LLM Synthesis/API]
        S3 --> AGG
        S4 --> AGG
    end

    API --> Pipeline Orchestrator
    Pipeline Orchestrator -->|InferenceResult| API
    API -->|JSON Response| User
```

## Fast-Path Mode
A `fast_path=True` option is available on `PipelineOrchestrator.analyze()` for rapid iteration. When enabled:
- Structural parser LLM invocation is skipped entirely (argument structure defaults to `is_argument=False`)
- Stage 4 LLM synthesis is replaced with a template string
- LLM reranker for rare classes is skipped
- Unified breakdown generation uses offline fallback instead of LLM

This drops per-segment latency from ~20s to ~600ms. Production requests should omit `fast_path` (defaults to `False`) for full analysis quality.

### 3. Frontend (React SPA)
- **Tech Stack**: Vite 8 + React 19 + TypeScript 5.8 + Tailwind CSS 3.
- **Entry Point**: `frontend/` directory alongside the legacy Streamlit dashboard.
- **Build Output**: `frontend/dist/` — served by FastAPI via `StaticFiles`.
- **Key Components**:
  - `AnnotatedText`: Core span-highlighting engine. Accepts `FallacyAnnotation[]` from the API and renders nested `<mark>` / `<span>` elements with hover tooltips showing fallacy name, confidence %, and top contributing token (XAI). Uses a stack-based tree algorithm with auto-close/reopen for correct overlapping-span rendering.
  - `FallacyCard`: Compact card showing fallacy name (color-coded by type), confidence tier, quote, and explanation. Renders a "View Trace" link to `/traces/:analysisId` when the result carries an `analysis_id`.
  - `TraceView` / `TraceTree`: Read-only symbolic-trace visualizer — fetches `GET /api/v1/traces/{analysis_id}` and renders the Z3 proof tree (satisfiable/unsatisfiable/unknown nodes) alongside ML confidence bars and saliency token chips, with collapsible child nodes.
  - `DebateDrawer`: Slide-over chat panel with optimistic streaming (400 ms min delay), typing indicator, and action-color badges.
  - `Analysis`: Split-pane page — textarea input + scan button on the left, annotated text + fallacy cards on the right.
  - `Health`: Recharts AreaChart of `GET /api/v1/history` logic scores (last 10) with 5-metric summary cards.
  - `Status`: Recursively flattened key-value grid from `GET /api/v1/health` (device info, cache stats, version), auto-refresh 15 s.
  - `ErrorBoundary`: Wraps all routes — catches render errors and shows a fallback UI with "Try again" reset button.
  - `History`: Displays past analyses from `localStorage` store (`lib/historyStore.ts`) — score, fallacy count, latency, cached status. Rows are clickable when a full result was retained (`fullResult` stored for the 10 most recent entries), restoring the analysis on the home page. The current analysis state (mode, text, result, document upload, toggles) is mirrored to `sessionStorage` (`logiscan_last_analysis`) and hydrated on mount, so TraceView "Back to Analysis" and browser back-navigation preserve the last result instead of resetting the page.
- **Routing**: `react-router-dom` — routes `/` (Analysis), `/health`, `/status`, `/history`; Debate is a slide-over drawer.
- **Theming**: CSS custom properties — dark terminal default, `.light` class override for light theme. ThemeToggle persists preference to `localStorage`. Badge colors (status, debate actions) also use theme-aware CSS vars.
- **Keyboard Shortcuts**:
  - `Ctrl+Enter` — submit analysis in Analysis page
  - `Escape` — close Debate drawer (with backdrop guard)
- **Mobile**: Responsive grids — Health summary cards collapse from 5 → 2 → 3 → 5 columns; Status badges from 3 → 1 → 3; nav scrolls horizontally on overflow; padding scales with `sm:` breakpoints.
- **Tests**: vitest + @testing-library/react — 149 passing tests across 13 test files (ThemeToggle, ErrorBoundary, History, AnnotatedText, DebateDrawer, accessibility, responsive breakpoints, page components).
- **Browser Extension**: `frontend/extension/` — Manifest v3 extension ("ArgCheck") with context menu, `Ctrl+Shift+L` hotkey, popup UI, and shadow-DOM overlay. Dashboard link updated to SPA (`localhost:8000`). Popup prefers new `fallacies[]` API format over legacy `fine_labels`.
- **Build Size**: ~195 KB gzipped (under 250 KB target).
- **Build**: `npm run build` runs `tsc -b && vite build`. Test files in `src/__tests__/` are excluded from the TypeScript build via `tsconfig.app.json` to prevent test-only type errors from blocking production builds.
- **Dependencies**: Uses `npm install` (not `npm ci`) due to frequent lockfile/version updates. `vite@8.1.5` and `vitest@4.1.10` are pinned in `package.json`.
- **Dev Proxy**: Vite dev server proxies `/api` to `http://localhost:8000`.

### 4. Startup Script (`run_native.sh`)
- **Production mode**: Activates venv, installs Python deps, runs `npm install` in a subshell, builds frontend if `dist/` missing, then starts uvicorn to serve both API and SPA.
- **Dev mode**: Adds a parallel Vite dev server (`localhost:5173`) with hot reload.
- **Key patterns**: `cd` operations are wrapped in subshells `(...)` to prevent directory state leaks. Uses `npm install --silent` (not `npm ci`) to avoid lockfile mismatch failures.
- **Cleanup**: Trap on EXIT kills both uvicorn and Vite via PID files.

#### Streamlit Limitations Addressed

| Limitation | Streamlit | React SPA |
|---|---|---|
| **Page loads** | Full server re-render on every interaction | Client-side routing — instant nav, no reload |
| **State management** | No client state; all state lives in `st.session_state` re-derived on rerun | Persistent React state across interactions; fetch results cached in-memory |
| **Code splitting** | All UI code loaded upfront as one Python script | `React.lazy` + Suspense — each page loads on demand |
| **Type safety** | Python duck-typing; no static checks in UI logic | TypeScript strict mode — compile-time type safety matching Pydantic models |
| **Bundle size** | Streamlit + deps ~50 MB+ Python on server | ~193 KB gzipped static JS/CSS — deploy to any CDN or nginx |
| **Debate UX** | No streaming; chat requires full page rerun | Optimistic placeholder + 400 ms min delay before batch-replace; typing indicator animation |
| **Drawer/panel** | Limited to columns/containers; no slide-over | `DebateDrawer` — slide-over from right with backdrop, no route change |
| **Charts** | Altair/Plotly — server-rendered, no animations | Recharts — client-side, animated, interactive |
| **Transitions** | No page-level animations | `animate-slideUp` keyed on route path |
| **Theming** | Basic color config via `.streamlit/config.toml` | CSS custom properties — full light/dark toggle via `.light` class |
| **Scrollbar** | Browser default | Custom 6 px scrollbar matching terminal aesthetic |
| **Deployment** | Requires Streamlit server process | Static files — serve from FastAPI, S3, Cloudflare, or any web server |

## Architectural Risks & Mitigations
- **Hardware Bottleneck**: Resolved via **ONNX Migration** and **Stage 4 Gating**.
- **Long-Form Text**: Handled by **Sliding Window Segmenter** (448-token windows, 128-token overlap) and **Regex-First Structural Parsing**.
- **Education Wrapper Suppression**: Resolved by **Boundary Normalization + Segmentation**: delimiters like `Definition:`, `Demo Scenario:`, `Fallacious Response:` are detected mid-text and each section is analyzed independently.
- **Entire-Text Quote Highlighting**: Resolved by **`MAX_QUOTE_CHARS=200` guard** in `_extract_quote_offline` and robust **sentence splitter** that handles `.` without trailing spaces.
- **Offset Drift**: Mitigated by `OffsetMapper` with segment-aware shifting and character-level offset mapping in `_normalize_boundaries`.
- **Explainability Gap**: Mitigated by **Saliency-Free Highlighting**, ensuring highlights work in 100% of cases even without GPU gradients.
- **Distribution Mismatch**: ✅ **Resolved** — all stages retrained and consolidated onto the current stack: `stage1_v13_classifier` (DistilBERT, gatekeeper) plus `stage3_v13_classifier` (DeBERTa, single-head 29-label) used by both Stage 2 and Stage 3. The earlier v12 series (`stage2_v12`, `stage3_v12`) was removed. Coarse categories are derived from the fine-label distribution.
