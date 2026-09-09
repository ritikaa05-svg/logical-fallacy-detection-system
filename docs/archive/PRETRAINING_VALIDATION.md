# Pre-Training Validation Audit

## Executive Summary
The balanced dataset `data/balanced_training_data.json` has achieved a stable class distribution (Imbalance Ratio 3.3:1) but contains **significant structural risks** regarding oversampling artifacts and lexical shortcuts.

## Part 1: Dataset Integrity & Distribution
- **Malformed Records**: 0 (✅ Pass)
- **Label Consistency**: 21 unique classes (✅ Pass)
- **Class Balance**:
    - Largest: 500 (`hasty_generalization`)
    - Smallest: 150 (`moving_goalposts`)
    - Mean: 334.4
- **Integrity Verdict**: Structural integrity is high.

## Part 2: Distribution Verification
| Metric | Value |
| :--- | :--- |
| Median Class Size | 387.0 |
| Standard Deviation | 159.1 |
| Imbalance Ratio | 3.33 |
*The intended 500-cap and 150-floor were respected.*

---

## Part 3: Oversampling & Shortcut Audit

### Duplication Risk (High)
- **Total Duplicate Text Entries**: 477
- **Collapse Risk**: `moving_goalposts` and `no_true_scotsman` are oversampled 6x from 25 to 150. Training on this will likely cause the model to memorize these specific examples.

### Shortcut Risk Ranking
1. **`moving_goalposts` / `no_true_scotsman`**: (100% Risk) Dominance of "user/assistant" tokens.
2. **`division`**: (100% Risk) Over-indexes on specific "sweet" examples.
3. **`appeal_to_nature`**: (85% Risk) Over-indexes on "natural".
4. **`equivocation`**: (69% Risk) Over-indexes on "therefore".

---

## Part 4: Synthetic Data Audit
- **100% Synthetic Classes**: `composition`, `division`, `moving_goalposts`, `no_true_scotsman`, `denying_antecedent`, `equivocation`.
- **Mixed Classes**: `straw_man` (79% Synthetic), `affirming_consequent` (42% Synthetic).
- **Core-Only Classes**: `ad_hominem`, `red_herring`, `false_cause`, `appeal_to_emotion`.

---

## Part 5: Trainability Assessment
- **Expected Macro-F1**: 0.55 - 0.65 (Significant improvement over 0.0039 but still bottlenecked by duplication).
- **Minority-Class Risk**: High. Likely to overfit on prompt style.
- **Generalization Risk**: Medium. Model will struggle with real-world conversational variations of multi-turn fallacies.

### Dataset Readiness Score: **68 / 100**
**Recommendation: B. Minor Improvements Then Train**
*The dataset is physically ready for training, but "Argument Intelligence" (Phase 4) requires more diverse minority samples to be effective.*
