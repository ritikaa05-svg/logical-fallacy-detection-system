# Training Dataset V3 Report (Phase 4 - Task C)

## Summary
The training dataset has been expanded and unified to include boundary classes, reaching a total of **9,507 samples**. This dataset is specifically designed to reduce False Positives in Phase 4.

## Final Class Distribution
| Rank | Fallacy / Class | Count | Category |
| :--- | :--- | :---: | :--- |
| 1 | Hasty Generalization | 1,044 | Informal (Presumption) |
| 2 | Red Herring | 928 | Informal (Relevance) |
| 3 | Appeal to Authority | 774 | Informal (Relevance) |
| 4 | Bandwagon | 704 | Informal (Relevance) |
| 5 | Slippery Slope | 685 | Informal (Presumption) |
| 6 | False Dilemma | 672 | Informal (Presumption) |
| 7 | Appeal to Nature | 627 | Informal (Presumption) |
| 8 | Appeal to Tradition | 607 | Informal (Presumption) |
| 9 | Straw Man | 599 | Informal (Relevance) |
| 10 | **valid_reasoning** | **560** | **Non-Fallacious (Boundary)** |
| 11 | **factual_statement** | **560** | **Non-Fallacious (Boundary)** |
| 12 | Appeal to Emotion | 391 | Informal (Relevance) |
| 13 | Ad Hominem | 387 | Informal (Relevance) |
| 14 | False Cause | 296 | Informal (Presumption) |
| 15 | Affirming Consequent | 188 | Formal |
| 16 | Begging the Question | 161 | Informal (Presumption) |
| 17 | Composition | 50 | Informal (Ambiguity) |
| 18 | Tu Quoque | 50 | Informal (Relevance) |
| 19 | Division | 50 | Informal (Ambiguity) |
| 20 | Equivocation | 50 | Informal (Ambiguity) |
| 21 | Denying Antecedent | 50 | Formal |
| 22 | Moving Goalposts | 25 | Informal (Relevance) |
| 23 | No True Scotsman | 25 | Informal (Relevance) |
| 24 | Tu Quoque Contextual | 24 | Informal (Relevance) |

**TOTAL: 9,507**

## Key Changes
- **Boundary Classes Added**: `valid_reasoning` (560) and `factual_statement` (560) are now top-11 classes, providing a strong signal for non-fallacious text.
- **De-duplication**: 150-char prefix hashing applied across all sources.
- **Normalization**: All labels standardized to snake_case.

## Findings
- The "None" category gap is officially closed.
- Minor classes (Tu Quoque Contextual, No True Scotsman, etc.) remain underrepresented but are sufficient for baseline detection.
- Total volume is >95% of the 10K target.

## Next Steps
- Perform Training Readiness Audit (Task D).
