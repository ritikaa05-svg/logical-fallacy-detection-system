# Training Dataset V3.1 Report (Phase 4c - 10K Milestone)

## Summary
The training dataset has reached its final Phase 4 scale of **10,786 samples**. This version specifically addresses the recall gaps and minority class weaknesses identified in the V1 audit.

## Final Class Distribution (Top 15)
| Rank | Fallacy / Class | Count | Status |
| :--- | :--- | :---: | :--- |
| 1 | Hasty Generalization | 1,044 | Majority |
| 2 | Red Herring | 928 | Majority |
| 3 | Appeal to Authority | 774 | Majority |
| 4 | Bandwagon | 704 | Majority |
| 5 | Slippery Slope | 685 | Majority |
| 6 | False Dilemma | 672 | Majority |
| 7 | Appeal to Nature | 627 | Majority |
| 8 | Appeal to Tradition | 607 | Majority |
| 9 | **valid_reasoning** | **600** | ✅ Boundary Boosted |
| 10 | Straw Man | 599 | Majority |
| 11 | **factual_statement** | **599** | ✅ Boundary Boosted |
| 12 | **appeal_to_emotion** | **541** | ⬆️ Boosted (+150) |
| 13 | **ad_hominem** | **537** | ⬆️ Boosted (+150) |
| 14 | **false_cause** | **446** | ⬆️ Boosted (+150) |
| 15 | **begging_the_question** | **311** | ⬆️ Boosted (+150) |

## Minority Class Reliability (Bottom 5)
| Fallacy / Class | Count | Improvement |
| :--- | :---: | :---: |
| `tu_quoque_contextual` | 124 | **5.1x increase** |
| `composition` | 100 | **2.0x increase** |
| `division` | 100 | **2.0x increase** |
| `denying_antecedent` | 100 | **2.0x increase** |
| `tu_quoque` | 50 | Baseline |

## Key Improvements
1. **Formal Logic Recall**: `affirming_consequent` increased from 188 to 288 samples (+53%) with high-diversity conversational templates.
2. **Cluster Separation**: `ad_hominem` and `appeal_to_emotion` now have balanced support (537/541) to improve discrimination.
3. **Boundary Stability**: Both `valid_reasoning` and `factual_statement` reached the 600-sample milestone despite aggressive deduplication.
4. **Data Health**: Obvious personal attacks mislabeled as `false_cause` in core data have been surgically relabelled to `ad_hominem`.

## Findings
- The dataset is now highly robust against "forced fallacy" logic.
- Imbalance ratio has improved from 43:1 down to **21:1** for most classes (excluding the rare `tu_quoque`).
- Total scale is 107.8% of the Phase 4 Roadmap target.
