# LogiScan Dataset Inventory (Archived)

> **⚠️ This document is archived.** The dataset has evolved significantly since this inventory was written.
> See **[`docs/DATASET_MASTER.md`](DATASET_MASTER.md)** for the current canonical reference covering v1.1 through v1.3.

**Historical snapshot:** This inventory captures the 8,686-count pre-expansion distribution used for early training runs. Since then:
- v1.1.0: +3,756 hard negatives (12,442 total)
- v1.2.0: +4,500 formal class rescue samples (16,942 total)
- v1.3.0: +996 contrastive near-miss hard negatives (17,938 total)

Six formerly zero-sample formal fallacy classes (`undistributed_middle`, `illicit_major`, `illicit_minor`, `exclusive_premises`, `existential_fallacy`) now have 500 samples each. **The current source of truth is `data/unified_training_data_v1.3.json` (17,938 samples).**

## Class Distribution (v1.0 Snapshot — 8,686 samples)

| Class | Count | Percentage |
| :--- | :--- | :--- |
| Hasty Generalization | 1044 | 12.02% |
| Red Herring | 928 | 10.68% |
| Appeal to Authority | 774 | 8.91% |
| Bandwagon | 704 | 8.10% |
| Slippery Slope | 685 | 7.89% |
| False Dilemma | 672 | 7.74% |
| Appeal to Nature | 627 | 7.22% |
| Appeal to Tradition | 607 | 6.99% |
| Straw Man | 599 | 6.90% |
| Appeal to Emotion | 391 | 4.50% |
| Ad Hominem | 387 | 4.45% |
| False Cause | 295 | 3.40% |
| Affirming Consequent | 238 | 2.74% |
| Composition | 200 | 2.30% |
| Division | 200 | 2.30% |
| Begging the Question | 161 | 1.85% |
| Tu Quoque | 100 | 1.15% |
| Equivocation | 100 | 1.15% |
| Denying Antecedent | 100 | 1.15% |
| Moving Goalposts | 25 | 0.29% |
| No True Scotsman | 25 | 0.29% |
| Tu Quoque Contextual | 24 | 0.28% |
| None (Negative) | 21 | 0.24% |
| **Total** | **8686** | **100%** |

*Note: The discrepancy from 8,707 is due to an exact deduplication pass conducted during the validation phase of `cleaned_training_data.json`.*
