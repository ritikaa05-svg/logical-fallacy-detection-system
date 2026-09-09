# LogiScan Project Audit

## 1. System Overview
LogiScan is a 3-stage neuro-symbolic pipeline for logical fallacy detection.
- **Backend**: FastAPI, PyTorch, Transformers, Z3, Redis.
- **Frontend**: Streamlit, Plotly, Custom HTML/CSS.
- **ML Models**: DistilBERT (S1), DeBERTa-v3 Multi-Head (S2 Unified Detection), SmolLM2-1.7B (S3 Synthesis), Z3 (S4 Symbolic).

## 2. Component Health

### Backend
- **API**: Functional; all endpoints tested.
- **Pipeline**: Core logic solid. Cache bypass resolved (`skip_cache` removed).
- **Explainability**: Integrated Gradients with char-level stateful offset tracking via `OffsetMapper`.
- **Formal Verification**: LLM-to-SMT translation with local LLM fallback (`local_smt_translator.py`).
- **Tests**: Populated — `test_pipeline.py` has 6 test functions covering pipeline, cache, Z3, and edge cases; `test_explainability.py` covers offset tracking.

### Frontend
- **Highlighter**: Consistent behavior using `OffsetMapper` for char-level offset tracking; repeated tokens handled correctly.
- **Breakdown Component**: Uses fuzzy regex matching for quotes, robust against minor LLM synthesis modifications.
- **State Management**: Streamlit session state used correctly with "Reset All State" button in sidebar.

### ML & Infrastructure
- **Model Loading**: Thread-safe singleton `ModelLifecycleManager` handles lazy loading and eviction. Unified `load_model` with `from_pretrained` + `safe_load` fallback, `ignore_mismatched_sizes`, and fallback `id2label`.
- **Hardware Support**: `DeviceManager` detects CUDA/MPS/CPU with VRAM-aware routing.
- **Caching**: Redis integration active; `skip_cache` toggle available via UI keyboard shortcut (`Ctrl+Shift+X`).

## 3. Critical Findings & Technical Debt
- ✅ **Missing Tests**: Resolved — tests now populated for pipeline and explainability.
- ✅ **Offset Drift**: Resolved — `OffsetMapper` handles history prepending and repeated tokens.
- ✅ **Code Quality**: Resolved — duplicate methods consolidated in `unified_classifier.py`.
- ✅ **Mocking**: Resolved — Stage 3 synthesis uses real `SmolLM2-1.7B` local generation.
- ✅ **XAI Accuracy**: Resolved — char-level stateful tracking replaces `text.find(token)` heuristic.

## 4. Remaining Risks
- **Long-tail fallacy recall**: Low-frequency fallacy classes may have limited training data.
- **Synthesis latency**: CPU-bound SmolLM2-1.7B adds 1.5–3s per analysis.
- **Z3 translation complexity**: Multi-step syllogisms with nested quantifiers remain challenging for the LLM→SMT pipeline.
