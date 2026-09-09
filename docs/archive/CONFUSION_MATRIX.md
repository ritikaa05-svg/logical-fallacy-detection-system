# Phase 4 Confusion Matrix Audit

*Note: Inferred from Precision/Recall discrepancies in the classification report.*

## Primary Confusion Clusters

### 1. The "Generalization Trap"
- **Cluster**: `hasty_generalization` ↔ `false_cause`
- **Evidence**: `false_cause` precision is only 0.45.
- **Cause**: Both fallacies share the "jumping to conclusions" linguistic structure. Without deep temporal reasoning, the model struggles to distinguish between "All X are Y" (Hasty) and "A caused B" (Cause).

### 2. The "Hostility Overlap"
- **Cluster**: `ad_hominem` ↔ `appeal_to_emotion` ↔ `tu_quoque`
- **Evidence**: `ad_hominem` F1 (0.58) and `appeal_to_emotion` F1 (0.53) are both suppressed.
- **Cause**: Personal attacks (`ad_hominem`) are inherently emotional. The model frequently mislabels the intensity of an attack as an emotional appeal or vice versa.

### 3. The "Formal Logic Silence"
- **Cluster**: `affirming_consequent` → `valid_reasoning` (False Negatives)
- **Evidence**: `affirming_consequent` recall is 0.39 despite 0.92 precision.
- **Cause**: The model is "playing it safe." When presented with complex "if/then" structures, it defaults to the `valid_reasoning` class to minimize weighted loss, missing 61% of actual formal errors.

## Actionable Insights
- **Target for V2**: Increase `affirming_consequent` and `denying_antecedent` samples to break the "Conservative Bias."
- **Boundary Check**: No confusion was noted between `factual_statement` and fallacies, confirming the new boundary classes are semantically distinct.
