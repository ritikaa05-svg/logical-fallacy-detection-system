# Phase 4 Error Analysis Report

## 1. Top Confusion Pairs
Based on Precision-Recall gaps and dataset audit, the following are the primary confusion clusters:

| Rank | Predicted | Actual | Likeliness | Error Type |
| :--- | :--- | :--- | :---: | :--- |
| 1 | `hasty_generalization` | `false_cause` | High | Semantic Overlap |
| 2 | `valid_reasoning` | `affirming_consequent` | High | Structural (Conservative Bias) |
| 3 | `ad_hominem` | `appeal_to_emotion` | Medium | Semantic (Hostility vs Emotion) |
| 4 | `hasty_generalization` | `red_herring` | Medium | Information Noise |
| 5 | `bandwagon` | `appeal_to_authority` | Low | Lexical (Expert vs People) |

## 2. Failure Mode Analysis (Audit Findings)

### A. The "Structural Blindness" (Affirming Consequent)
- **Status**: 0.39 Recall, 0.92 Precision.
- **Why it fails**: The model only flags "obvious" textbook syllogisms. When the "If/Then" logic is embedded in conversational text (e.g., "Ivan: You cannot borrow my car..."), the model defaults to `valid_reasoning` or `red_herring`.
- **Root Cause**: Insufficient variety in conversational logical structures.

### B. The "Correlation/Causation Trap" (False Cause)
- **Status**: 0.49 F1, 0.45 Precision.
- **Why it fails**: Dataset contamination. Audit found samples like "Have you stopped cheating on exams?" (loaded as False Cause) which are actually `loaded_question` (not in taxonomy) or `ad_hominem`.
- **Root Cause**: Label ambiguity and noisy human-verified data in the `core` set.

### C. The "Emotion/Attack Gradient" (Ad Hominem vs Emotion)
- **Status**: ~0.55 F1 for both.
- **Why it fails**: Personal attacks are emotionally charged. The model struggles with intensity. "You are always so rude" (Ad Hominem) is linguistically similar to "His voice touched my heart" (Emotion) in terms of "Subjective/Feeling" tokens.
- **Root Cause**: Overlap in lexical cues (pronouns + intensity adverbs).

## 3. Dataset Quality Audit
- **Insufficient Samples**: `affirming_consequent` (188) and `begging_the_question` (161) are under-supported compared to `hasty_generalization` (1,044).
- **Synthetic Bias**: Small classes (Support < 10) like `composition` and `division` have 1.00 F1, indicating the model has memorized the "Template + Variant" structure.
- **Label Ambiguity**: High overlap between `false_cause` and `hasty_generalization` in conversational contexts.

## 4. Reliability Assessment (Small-Class Audit)
The following F1 scores are **STATISTICALLY UNRELIABLE**:
- `tu_quoque_contextual` (1.00): Support=4. One misclassification would drop F1 to 0.75.
- `moving_goalposts` (0.86): Support=4.
- `no_true_scotsman` (0.89): Support=4.
- `denying_antecedent` (0.88): Support=7.

**Verdict**: The 0.8147 Macro-F1 is "inflated" by perfect scores on these 8 tiny synthetic classes. Real-world performance on these classes is likely near 0.40.
