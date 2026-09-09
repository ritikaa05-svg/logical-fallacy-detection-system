# Phase 4 Training Results (V1)

## Global Metrics
- **Accuracy**: 0.78
- **Macro-F1**: 0.8147
- **Weighted-F1**: 0.78
- **Precision (Weighted)**: 0.79
- **Recall (Weighted)**: 0.78

## Top Performing Classes (F1 > 0.90)
| Class | F1-Score | Support |
| :--- | :---: | :---: |
| `composition` | 1.00 | 8 |
| `division` | 1.00 | 7 |
| `equivocation` | 1.00 | 8 |
| `tu_quoque_contextual` | 1.00 | 4 |
| `factual_statement` | 0.99 | 84 |
| `valid_reasoning` | 0.97 | 84 |
| `tu_quoque` | 0.93 | 7 |

## Underperforming Classes (F1 < 0.60)
| Class | F1-Score | Recall | Precision | Status |
| :--- | :---: | :---: | :---: | :--- |
| `false_cause` | 0.49 | 0.55 | 0.45 | 🚩 Critical Weakness |
| `appeal_to_emotion` | 0.53 | 0.56 | 0.50 | 🚩 Critical Weakness |
| `affirming_consequent`| 0.55 | 0.39 | 0.92 | 🚩 Recall Gap |
| `ad_hominem` | 0.58 | 0.64 | 0.54 | ⚠️ Noise |
| `hasty_generalization`| 0.58 | 0.54 | 0.63 | ⚠️ Large Class Noise |

## Key Findings
1. **Boundary Goal Met**: `factual_statement` (0.99) and `valid_reasoning` (0.97) are now the model's strongest real-world classes. FPR leakage is successfully mitigated.
2. **Synthetic Overfitting**: 1.00 F1 scores on minor synthetic classes indicate the model has memorized templates. Generalization to novel phrasing for these classes is likely low.
3. **Formal Fallacy Bottleneck**: `affirming_consequent` has high precision (0.92) but low recall (0.39), suggesting the model is too conservative when identifying formal logic errors.
4. **Informal Noise**: `false_cause` and `hasty_generalization` continue to overlap, causing a "Precision Trap."
