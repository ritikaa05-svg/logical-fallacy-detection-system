# Post-Training Dataset Audit (Phase 4)

## Objective
Determine the sufficiency of the current 9,507-sample dataset based on empirical training performance (Macro-F1 0.81).

## 1. Sufficiency Verdict: YES for Baseline, NO for Production
The dataset is sufficient to move past "forced fallacy" logic, but is not yet a robust reasoner for informal fallacies.

## 2. Rebalancing Performance
- **Did Sqrt Smoothing Work?**: **YES**. Loss was finite and model converged to 0.81 Macro-F1. Minority classes (Support < 10) reached 1.00 F1 without poisoning the majority classes.
- **Evidence**: `hasty_generalization` (Support 157) maintained a respectable 0.58 F1 despite having its gradient "damped" by smoothing.

## 3. Justification for Further Expansion (10K Target)
Expansion to 10,000+ samples is **STRICTLY JUSTIFIED** by the following evidence:
- **`false_cause` Failure**: F1 0.49 suggests a structural lack of causal-link samples in the current set.
- **`affirming_consequent` Gap**: 0.39 Recall indicates the model lacks enough formal counter-examples to "trust" its identification of logical structure.
- **Overfitting Risk**: The 1.00 F1 on `tu_quoque_contextual` is purely artifactual (Support 4). Real-world multi-turn support requires ~100 unique dialogue chains to be robust.

## 4. Pursuing 10K
Pursuit of the full 10K goal should proceed, focusing exclusively on:
1. **Formal Logic (+300 samples)**: To fix recall gaps in sound vs. unsound structures.
2. **Causal Reasoning (+200 samples)**: To separate `false_cause` from generalization.
3. **Emotional Nuance (+150 samples)**: To separate `ad_hominem` from general `appeal_to_emotion`.
