# Dataset Distribution Audit

## Executive Summary
The dataset `data/unified_training_data.json` exhibits **severe class imbalance** and **source heterogeneity**. While the majority classes are well-supported by "real-world" core data, the minority and structural classes are 100% dependent on synthetic samples.

## Phase A: Distribution Analysis
- **Total Samples**: 8,687
- **Number of Classes**: 22
- **Imbalance Ratio**: **43.5 : 1** (`hasty_generalization` vs `tu_quoque_contextual`)
- **Median Class Size**: 341.5
- **Mean Class Size**: 394.8
- **Standard Deviation**: 314.9

### Minority Classes (Risk of Collapse)
| Class | Count | Source |
| :--- | :---: | :--- |
| `tu_quoque_contextual` | 24 | 100% Synthetic Multi-turn |
| `moving_goalposts` | 25 | 100% Synthetic Multi-turn |
| `no_true_scotsman` | 25 | 100% Synthetic Multi-turn |
| `composition` | 100 | 100% Synthetic |
| `division` | 100 | 100% Synthetic |
| `denying_antecedent` | 100 | 100% Synthetic |

### Majority Classes (Bias Magnets)
| Class | Count | Source |
| :--- | :---: | :--- |
| `hasty_generalization` | 1,044 | 100% Real (Core) |
| `red_herring` | 928 | 100% Real (Core) |
| `appeal_to_authority` | 774 | 100% Real (Core) |

---

## Phase B: Label Quality Review

### Potentially Noisy Classes
- **`straw_man`**: 80.5% of samples (482/599) come from `raw_pool` (LLM generations). This may introduce stylistic bias where the model learns the LLM's "hallucinated" straw man patterns rather than real adversarial debate.
- **`appeal_to_emotion`**: Relatively low core count (391) given its broad nature; likely overlaps with `ad_hominem`.

### Underrepresented Classes
- **All Multi-turn Classes**: With < 30 samples each, these classes will likely achieve ~0% F1 without aggressive oversampling or focal loss.

### Overrepresented Classes
- **`hasty_generalization`**: Acts as a "catch-all" magnet due to its volume and linguistic similarity to other logical errors.

---

## Phase C: Training Risk Analysis

1. **Majority-Class Bias**: The model will default to `hasty_generalization` or `red_herring` when uncertain, as these minimize the overall loss function.
2. **Minority-Class Collapse**: Macro-F1 will remain near 0.0 because the multi-turn classes (24-25 samples) provide insufficient signal for the gradient to distinguish them from noise.
3. **Synthetic Overfitting**: Since 100% of the formal logic classes (`composition`, `division`, etc.) are synthetic, the model may only recognize them when they use the specific vocabulary of the generator.
4. **Poor Calibration**: The model will be overconfident on majority classes and underconfident/random on minority classes.
