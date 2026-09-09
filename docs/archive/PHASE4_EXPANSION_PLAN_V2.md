# Phase 4 Targeted Dataset Expansion Plan

## Objective
Targeted expansion of weak classes to bridge the Precision-Recall gaps identified in the V1 model.

## 1. Targeted Additions (F1 < 0.65)

| Class | Current Count | Target Addition | Reasoning |
| :--- | :---: | :---: | :--- |
| `affirming_consequent` | 188 | +200 | Fix 0.39 Recall gap by adding diverse IF/THEN patterns. |
| `false_cause` | 296 | +200 | Clean definitions and add more "A therefore B" causal errors. |
| `appeal_to_emotion` | 391 | +150 | Add "Pure Emotion" samples (fear, pity) without personal attacks. |
| `ad_hominem` | 387 | +150 | Focus on "Character vs Argument" distinction. |
| `begging_the_question` | 161 | +100 | Add circular reasoning chains (A -> B -> A). |
| `hasty_generalization` | 1,044 | +0 (Clean) | **DO NOT ADD**. Focus on cleaning current noise. |

## 2. Reliability Expansion (Minority Classes)
*Goal: Move from "Memorized" to "Generalized"*

| Class | Current Count | Target Addition |
| :--- | :---: | :---: |
| `tu_quoque_contextual` | 24 | +50 |
| `moving_goalposts` | 25 | +50 |
| `no_true_scotsman` | 25 | +50 |

## 3. Estimated Expansion Total: 950 samples
This will bring the dataset to the **10,457 sample mark**, fulfilling the Phase 4 Roadmap and providing sufficient support for robust retraining.

## 4. Quality Constraints
- All new `affirming_consequent` samples must include a valid counter-example in the metadata to ensure logical structure.
- `false_cause` expansion must avoid "Ad Hominem" personal insults to de-risk cluster confusion.
