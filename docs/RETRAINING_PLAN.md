# LogiScan Synchronized Retraining Plan (v2.0)

## Objective
Restore internal model consistency across the LogiScan pipeline. Currently, only the Phase 4 Fine Classifier uses the 10.7K unified dataset, while earlier stages (Gatekeeper and Coarse) are anchored to obsolete data distributions.

## Training Sequence (Synchronized)
To eliminate distribution mismatch and normalize salience, models MUST be retrained in the following order:

1.  **Stage 1: Gatekeeper (Binary Filter)**
    *   **Goal**: Distinguish logical claims from factual statements, documentation, and technical text.
    *   **Data**: Full 10.7K dataset. **Labels**: 0 for `factual_statement` and `valid_reasoning`; 1 for all fallacies.
    *   **Model**: DistilBERT-base-uncased (Optimized for ONNX/CPU).
    *   **Output**: `models/stage1_gatekeeper/model.onnx`.

2.  **Stage 2: Coarse Classifier (Broad Routing)**
    *   **Goal**: Map arguments to the 5-class coarse taxonomy (`Formal`, `Informal Ambiguity`, `Presumption`, `Relevance`, `Non-Fallacious`).
    *   **Data**: Full 10.7K dataset mapped via `COARSE_MAP`.
    *   **Model**: DistilBERT or DeBERTa-v3-small.

3.  **Stage 3: Phase 4 Fine Classifier (Authoritative Detection)**
    *   **Goal**: 24-way classification across the full LogiScan taxonomy.
    *   **Data**: Full 10.7K dataset.
    *   **Model**: DeBERTa-v3-MultiHead (Shared backbone for Stage 2 + 3).
    *   **Export**: Generate production `model.onnx` for CPU-based inference.

## Dataset: `data/unified_training_data_v1.3.json`
- **Total Samples**: 17,938 (Hardened)
- **Train/Val Split**: 80/20 (Stratified)
- **Formal class rescue**: 6 formerly zero-sample classes now have 500+ samples each
- **Key Negative Classes**:
    - `factual_statement` (1,494 samples - Includes technical/complex descriptions)
    - `valid_reasoning` (1,094 samples - Diverse deductive structures)
- **Source Breakdown**: 7,531 core + 4,500 formal adversarial + 2,699 synthetic + 1,656 hard negatives + 996 near-miss + 482 raw + 74 multiturn

## Expected Benefits
- **Normalized Salience**: Eliminates 0.99 over-confidence on technical documentation.
- **Accurate Gating**: The Argument Gate will only trigger on true non-arguments.
- **Taxonomy Parity**: All stages will agree on the logical boundaries of the 24 classes.

## Rollback Strategy
- Preserve `models/phase4_final_model` as stable baseline.
- If new Stage 1 precision < 0.90 on documentation benchmark, revert to heuristic fallback.
