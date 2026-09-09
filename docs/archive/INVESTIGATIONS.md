# LogiScan System Investigations

## Investigation: Highlight System Failure & Data Flow Trace

### Initial Hypothesis
Highlights were either disappearing, appearing at the wrong indices, or clustering at the start of the text. Suspected "Offset Drift" and naive token matching.

### Data Flow Trace (Evidence)
Performed using `scripts/trace_data_flow.py` with input:
`"You are wrong because you are a bad person. You are wrong because you are a bad person."`

#### Stage A: Raw Input
`You are wrong because you are a bad person. You are wrong because you are a bad person.`

#### Stage B: Backend Output (Pre-Fix)
- **Is Logical Claim**: True
- **Fine Labels**: `['ad_hominem']`
- **Result**: Only the first sentence was analyzed/annotated.

#### Stage C: Salient Tokens (Pre-Fix)
- Token "You" (2nd occurrence) was mapped to index 0 instead of 44.
- Token "because" (2nd occurrence) was mapped to index 14 instead of 58.
- **Root Cause Identified**: `explainability.py` used `text.find(clean_token)` which always returns the first occurrence.

#### Stage D: Annotations (Pre-Fix)
- Only one `FallacyAnnotation` object was created for the first sentence.
- **Root Cause Identified**: Orchestrator logic was hardcoded to take the first span and build a single annotation.

#### Stage E: Generated HTML (Pre-Fix)
- Malformed nesting at sentence boundaries: `<span class="ls-sentence-hl">...</span><span class="ls-sentence-hl">` (Empty or swallowed tags).
- **Root Cause Identified**: Event sorting priority in `highlighting.py` (`S_START < S_END`) caused tags to overlap incorrectly at shared indices.

### Resolved Root Causes

1. **NameError: os**
   - **File**: `backend/app/services/unified_classifier.py`
   - **Root Cause**: `os.getenv` was used in `__init__` without an `import os` statement.
   - **Evidence**: Traceback during execution.

2. **XAI Offset Clustering**
   - **File**: `backend/app/services/explainability.py`
   - **Root Cause**: Naive string searching for tokens.
   - **Remedy**: Implemented `curr_char_pos` tracker to search for tokens sequentially.

3. **Rendering Priority**
   - **File**: `frontend/streamlit/highlighting.py`
   - **Root Cause**: END tags were processed after START tags at the same index.
   - **Remedy**: Changed priority to `{"T_END": 0, "S_END": 1, "S_START": 2, "T_START": 3}`.

### Lessons Learned
- **Sequential Token Mapping**: Integrated Gradients attribution mapping must be stateful if using string search fallbacks.
- **Event-Based HTML Assembly**: The order of operations at the same index is the most common cause of "swallowed" highlights in Streamlit/Markdown rendering.
- **Import Verification**: Runtime environment variables (`os.getenv`) must have their imports verified after any service refactoring.

### Rejected Hypotheses
- **Hypothesis**: CSS was hiding the highlights.
- **Evidence**: Inspection of generated HTML showed tags were either missing or malformed at the structural level, not just the visual level.
