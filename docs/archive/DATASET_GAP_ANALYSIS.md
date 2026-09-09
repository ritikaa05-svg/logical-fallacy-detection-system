# Dataset Gap Analysis
*See `docs/DATASET_MASTER.md` for context on dataset versions and lifecycles.*

> **⚠️ Note:** This document is based on the pre-expansion dataset (8,686 samples). The current dataset JSON (`data/unified_training_data_v1.1.json`) is authoritative and contains **12,442 samples** after hard negative expansion. See `docs/DATASET_MASTER.md` for the canonical reference.

| Class | Current Count | Target Count | Samples Required |
| :--- | :--- | :--- | :--- |
| Hasty Generalization | 1044 | 1100 | 56 |
| Red Herring | 928 | 1000 | 72 |
| Appeal to Authority | 774 | 850 | 76 |
| Bandwagon | 704 | 800 | 96 |
| Slippery Slope | 685 | 800 | 115 |
| False Dilemma | 672 | 800 | 128 |
| Appeal to Nature | 627 | 700 | 73 |
| Appeal to Tradition | 607 | 700 | 93 |
| Straw Man | 599 | 700 | 101 |
| Appeal to Emotion | 391 | 500 | 109 |
| Affirming Consequent | 555 | 500 | 0 (✅ Met) |
| Composition | 200 | 400 | 200 |
| Division | 200 | 400 | 200 |
| Moving Goalposts | 25 | 300 | 275 |
| No True Scotsman | 25 | 300 | 275 |
| Tu Quoque Contextual | 24 | 300 | 276 |
| Begging the Question | 161 | 300 | 139 |
| **None (Valid/Factual)** | 21 | 1000 | 979 |
| **Total** | **12442** | 10000 | **—** |

## Expansion Category Breakdown
- **Hard Negatives**: 1,500 target.
- **Counterfactuals**: 500 pairs.
- **Domain/Multi-Turn**: Remaining distribution.

> **Source of truth:** `data/unified_training_data_v1.1.json` (12,442 samples). See `docs/DATASET_MASTER.md` for the current canonical reference.
