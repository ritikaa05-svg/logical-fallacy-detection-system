# Model Reality Check (Phase 4)

## Summary
The system is **NOT using the trained Unified Model** correctly. While it attempts to load the real model, multiple failures trigger fallbacks and mock modes.

## Loading Evidence
- **Model Path**: `models/unified_classifier`
- **Device**: `cuda:0` (detected 3.6GB VRAM)
- **Quantization**: **Active** (4-bit NF4).
- **Architecture Mismatch**: **CRITICAL**.
    - Log: `DebertaV3MultiHead LOAD REPORT... MISSING: deberta.encoder.layer.{0...23}`.
    - Result: The model weights being loaded are from a 12-layer `deberta-v3-base` (encoder.layer.0...11), but the `DebertaV3MultiHead` class expects a 24-layer `deberta-v3-large` OR the key mapping `deberta.*` is missing in the checkpoint (which has `encoder.*` keys).
- **Taxonomy Mismatch**:
    - `config.json`: 22 labels.
    - `UnifiedClassifier` Code: 24 labels (Phase 4 additions).
    - Result: `ignore_mismatched_sizes=False` in `unified_classifier.py` will cause a crash on the final linear layer.

## Mock Mode Activation
- **Trigger**: `Prediction pipeline failed: ...` followed by `DEBUG Stage3 labels: ['hasty_generalization', 'false_cause']`.
- **Finding**: Stage 3 returns `hasty_generalization` and `false_cause` for "Pizza is delicious", which are standard mock return values in `unified_classifier.py`:
    ```python
    else:
        coarse, fine = "Informal (Presumption)", ["hasty_generalization", "false_cause"]
    ```
- **Verdict**: The system is **SILENTLY RUNNING MOCK MODE** because the real model loading fails.

## Fallback Paths
1. **API Fallback**: Attempted but failed with **401 Unauthorized**.
2. **Local Fallback (Separate S2/S3)**: Not attempted because `low_memory_mode` evicted them.
3. **Mock Fallback**: Active and currently providing all results.

## Confidence Calculation
- **Source**: Hardcoded in `_predict_mock` (0.85 for coarse, 0.8/0.4 for fine).
- **Saliency**: Simulated by modulo arithmetic (`i % 3 == 0`).

## Mock Mode Status
- **Should it remain?**: Only as a last resort. It is currently misleading because it masks model failures.
- **How to disable safely**: Set `LOGISCAN_MOCK_MODE=false` and ensure model integrity.

## Recommendations
1. Re-align `DebertaV3MultiHead` to use `deberta-v3-base` (12 layers) if the weights are base-sized.
2. Fix key mapping in `DebertaV3MultiHead`: the checkpoint uses `encoder.*` but the class uses `self.deberta` (standard HF Deberta expects `deberta.*`).
3. Re-generate `config.json` with 24 labels to match Phase 4 taxonomy.
