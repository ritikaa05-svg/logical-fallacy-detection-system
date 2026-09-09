# Phase 2 Execution Plan: Code Health & Reliability

## Item 1: Refactor Unified Classifier
- **Current State**: The `UnifiedClassifier` uses fragmented logic for unified vs. separate model predictions. Post-processing (softmax, sorting, label mapping) is duplicated across `_predict_unified` and `_separate_predict`.
- **Technical Debt**: Duplicate code paths for label lookup and saliency extraction. Thin async wrappers (`predict_coarse`/`predict_fine`) add overhead without clear benefit.
- **Proposed Fix**:
    1. Consolidate post-processing into a single `_process_logits` method.
    2. Unify the attribution call site.
    3. Standardize label mapping using a single source of truth.
- **Risks**: Potential for breaking fallback logic if `id2label` mapping differs between unified and separate models.
- **Validation**: Compare confidence scores and labels for 10 sample inputs before and after refactoring.

## Item 2: Improve LLM Synthesis
- **Current State**: `LLMSynthesisService` methods (`generate`, `verify_fallacy`, `generate_compact_explanation`) are currently returning static placeholder strings.
- **Technical Debt**: The "Synthesis" part of the Neuro-Symbolic stage is largely mocked.
- **Proposed Fix**:
    1. Implement real LLM inference for all mocked methods.
    2. Support both local inference (via `transformers`) and remote (via HuggingFace API) based on `device_manager` targets.
    3. Add a tiered fallback system (Detailed LLM -> Compact LLM -> Heuristic Template).
- **Risks**: Increased latency; potential for LLM hallucination in corrections.
- **Validation**: Verify that 3 different fallacies (e.g., Ad Hominem, Straw Man, False Cause) produce unique, context-aware explanations and correction strategies.

## Item 3: Enhance Z3 Translation
- **Current State**: SMT translation relies on a simple one-shot prompt or a basic propositional regex fallback.
- **Technical Debt**: Regex fallback does not support predicates or complex connectives. LLM prompt is prone to syntax errors.
- **Proposed Fix**:
    1. **LLM Prompt**: Improve the prompt to explicitly define the contradiction goal (asserting the negation of the conclusion).
    2. **Regex Fallback**: Implement support for basic syllogisms (e.g., "All X are Y") and `If P then Q` logic in the fallback builder.
    3. **Syntax Validation**: Strengthen the parenthesis checker.
- **Risks**: SMT-LIBv2 is sensitive to theory choice (QF_UF vs. LRA); complex arguments may still fail.
- **Validation**: Test with a verification suite including valid syllogisms and classic formal fallacies (Affirming the Consequent).
