# Phase 3 Execution Plan: UX, Performance & Advanced Reasoning

## Phase 3 Objective
Enhance the user experience through consistent visualization, improve system performance via model optimization, and further strengthen the formal reasoning engine.

---

## Item 1: Unify Highlighting & Component Consolidation
- **Current State**: Highlighting logic is fragmented across `highlighting.py` (editor view) and `fallacy_breakdown.py` (split-pane view).
- **Goal**: Consolidate into a single robust rendering engine to ensure visual consistency between the main analysis and the detailed breakdown.
- **Task**: Refactor `fallacy_breakdown.py` to use the event-based assembly from `highlighting.py`.

## Item 2: Unified Model Re-Export & Latency Optimization
- **Current State**: Unified multi-head model has shape mismatches; Stage 3 (RoBERTa-Large) is slow on CPU.
- **Goal**: Resolve loading issues and improve "cold" inference speed.
- **Task**:
    1. Re-export the multi-head classifier weights to match the `DebertaV3MultiHead` architecture exactly.
    2. Investigate ONNX quantization for Stage 3 to reduce CPU latency below the 3.0s target.

## Item 3: Implement Logic Health Tracking
- **Current State**: "Logic Health" page is a static placeholder with mock data.
- **Goal**: Provide users with actual reasoning improvement metrics over time.
- **Task**:
    1. Implement a simple SQLite or JSON-based storage for local user session scores.
    2. Calculate "Logic Health" based on the moving average of `logic_score` from the last 10 requests.
    3. Update the Streamlit chart to pull from this real history.

## Item 4: Basic Predicate Logic in Z3 Fallback
- **Current State**: Regex fallback is propositional (handles `If P then Q`).
- **Goal**: Handle simple syllogisms (e.g., "All humans are mortal").
- **Task**: Enhance the regex parser to detect "All X are Y" patterns and generate universal quantification SMT-LIBv2 blocks.

---

## Validation Strategy
- **Visual**: Manually verify that highlights match exactly between the Editor and Breakdown views.
- **Performance**: Benchmark Stage 3 latency and verify it stays within the 3s window.
- **Functional**: Verify "Logic Health" persists across Streamlit reruns.
- **Reasoning**: Test the "Valid Syllogism" case in `scripts/validate_z3.py` and ensure it returns `unsat` (Valid).
