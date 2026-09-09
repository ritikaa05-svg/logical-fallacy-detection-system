# Phase 1 Results: Critical Fixes

## 1. Fix XAI Offset Heuristic
- **Fix Implemented**: Replaced naive `text.find()` with a stateful `curr_char_pos` tracker in `backend/app/services/explainability.py`. It now performs sequential, case-insensitive searches and prioritizes native `offset_mapping` when available.
- **Files Changed**: `backend/app/services/explainability.py`
- **Validation Performed**: Verified with a reproduction script (`scripts/reproduce_xai_issue.py`) using text with 3 occurrences of "scientists". Confirmed distinct indices.
- **Remaining Risks**: Very short or heavily mis-tokenized words might still misalign in extreme fallback cases.
- **Confidence Level**: 95%

## 2. Enable Redis Cache
- **Fix Implemented**: Removed hardcoded `skip_cache = True` and ensured the pipeline respects the `skip_cache` parameter. Wrapped caching in the orchestrator with defensive logic (though `CacheService` already handles most exceptions).
- **Files Changed**: `backend/app/pipeline/orchestrator.py`
- **Validation Performed**: Ran `scripts/test_cache_integration.py`. Confirmed:
    - Cache Miss on first run.
    - Cache Hit on second run (9ms latency).
    - Cache Bypass when `skip_cache=True` is passed.
- **Remaining Risks**: Stale data if model weights are updated without flushing Redis.
- **Confidence Level**: 100%

## 3. Populate Test Suite
- **Fix Implemented**: Implemented 6 core tests in `backend/tests/test_pipeline.py` and `backend/tests/test_explainability.py`.
- **Files Changed**: `backend/tests/test_pipeline.py`, `backend/tests/test_explainability.py`
- **Validation Performed**: All 6 tests passing with `pytest`.
- **Remaining Risks**: Test coverage for Stage 4 (Z3) is still minimal.
- **Confidence Level**: 90%

## 4. Resolve Offset Drift
- **Fix Implemented**: Introduced a formal `OffsetMapper` class in `orchestrator.py` to handle index translation for conversation history. Removed manual index subtraction hacks.
- **Files Changed**: `backend/app/pipeline/orchestrator.py`
- **Validation Performed**: Verified via `test_pipeline_with_history`. Confirmed that offsets for salient tokens are correctly mapped back to the user's original input text.
- **Remaining Risks**: Off-by-one errors if the `[TURN]` separator format changes.
- **Confidence Level**: 95%
