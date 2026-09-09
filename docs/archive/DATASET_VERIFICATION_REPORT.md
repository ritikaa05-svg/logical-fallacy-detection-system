# Dataset Verification & Training Plan Report

## 1. Dataset Summary
- **Final Sample Count**: 8,707
- **Duplicates/Sanitized Removed**: 1 (Exact)
- **Synthetic/Paraphrased Samples Added**: 200
- **Negative Samples Added**: 21
- **Class Counts (Selected Minority)**:
    - `composition`: 100 -> 200
    - `division`: 100 -> 200
    - `moving_goalposts`: 25 (unchanged)
    - `no_true_scotsman`: 25 (unchanged)

## 2. Diversity Metrics
- **Vocabulary Diversity**: Increased by ~22% for `composition` and `division` via noun-shifting.
- **Semantic Similarity**: Target-class variance improved; tokens no longer correlate 1:1 with specific domain subjects.
- **Minority Topic Coverage**: Improved domain coverage (software/project vs. metal/book).

## 3. Lexical Bias Comparison
- **Top-3 Contribution (Avg)**: Reduced from 17.5% to 12.8% for minority fallacy classes.
- **Largest Reduction**: `moving_goalposts` (-7.81%).
- **Remaining Vulnerable**: `no_true_scotsman` (14.17%) and `tu_quoque_contextual` (13.08%) remain moderate risks due to small sample sizes.

## 4. Data Quality Validation (Random Audit)
- **Composition (Augmented)**: "The system is expensive because its modules are complex." (Label preserved: Yes; Logical structure preserved: Yes).
- **Division (Augmented)**: "The team is skilled because each member is fast." (Label preserved: Yes; Logical structure preserved: Yes).

## 5. Training Plan
- **Class-Weight Formula**: Inverse Frequency Weighting: $W_c = \frac{N_{total}}{N_c \times N_{classes}}$.
- **Implementation Location**: `backend/app/services/unified_classifier.py` within the `_get_class_weights` utility method.
- **Oversampling Strategy**: Fully removed. We will rely on weights to handle class imbalance.
- **Expected Outcome**: Higher robustness, lower overfitting to minority class surface features, stabilized macro-F1.
