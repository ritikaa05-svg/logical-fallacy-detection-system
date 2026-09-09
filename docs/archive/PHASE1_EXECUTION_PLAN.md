# Phase 1 Execution Plan: Critical Fixes

## Item 1: Fix XAI Offset Heuristic
- **Root Cause**: Reliance on `text.find()` for token-to-character mapping, which ignores duplicate tokens.
- **Affected Files**: `backend/app/services/explainability.py`
- **Proposed Fix**:
    1. Extract `offset_mapping` directly from the tokenizer output.
    2. If `offset_mapping` is missing (non-fast tokenizers), implement a "Token Sequence Matcher" that iterates through the text and tracks the last matched position to ensure duplicate tokens are handled sequentially.
- **Risks**: Tokenizer-specific character representations (e.g., `Ġ` in RoBERTa) might require normalization.
- **Validation**: Test with text like `"Scientists say scientists should trust scientists."` and verify 3 distinct spans.

## Item 2: Enable Redis Cache
- **Root Cause**: Hardcoded `skip_cache = True` in orchestrator.
- **Affected Files**: `backend/app/pipeline/orchestrator.py`
- **Proposed Fix**:
    1. Verify `skip_cache` logic respects the `InferenceRequest` parameter.
    2. Add `try-except` blocks around Redis calls to ensure pipeline works even if Redis is down.
- **Risks**: Cached data becoming stale if model versions change.
- **Validation**: Perform two identical requests; verify second request has `cached: True` and lower latency.

## Item 3: Populate Test Suite
- **Root Cause**: Unimplemented test stubs.
- **Affected Files**: `backend/tests/` (multiple files)
- **Proposed Fix**:
    1. Implement `test_pipeline.py` with full 4-stage mocks.
    2. Implement `test_z3.py` for formal verification.
    3. Implement `test_explainability.py` specifically for offset verification.
- **Risks**: Mocking too aggressively might hide integration bugs.
- **Validation**: Run `pytest` and achieve >80% coverage on core logic.

## Item 4: Resolve Offset Drift
- **Root Cause**: Manual index subtraction for prepended history.
- **Affected Files**: `backend/app/pipeline/orchestrator.py`
- **Proposed Fix**:
    1. Create an `OffsetMapper` class that stores the length of the prepended context.
    2. Use the mapper to translate indices before building annotations.
- **Risks**: Off-by-one errors during concatenation.
- **Validation**: Test multi-turn debate and verify highlights align with user-inputted text only.
