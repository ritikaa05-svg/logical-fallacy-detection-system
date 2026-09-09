# LogiScan Dataset Audit
*See `docs/DATASET_MASTER.md` for context on dataset versions and lifecycles.*

> **⚠️ Note:** This document describes the pre-expansion dataset state and predates the hard negative expansion (1.6K+ samples for formal fallacy classes). The current dataset JSON (`data/unified_training_data_v1.1.json`) is authoritative and contains **12,442 samples**. See `docs/DATASET_MASTER.md` for the canonical reference.

## Dataset Overview: `data/unified_training_data_v1.1.json`
- **Total Samples**: 12,442
- **Unique Classes**: 23 (includes new 'none' class for negative sampling)
- **Status**: Post-cleaning, augmented, deduplicated, and hard-negative-expanded.

## Composition Analysis
- **Core (Merged External Sources)**: ~7,500 samples
- **Synthetic/Augmented**: ~1,000 samples
- **Hard Negative Expansion**: 1,600+ samples (formal fallacy classes)
- **Negative Samples**: 21

## Class Balance (Top 10)
| Class | Count | Percentage |
| :--- | :---: | :---: |
| Hasty Generalization | 1,044 | 12.0% |
| Red Herring | 928 | 10.7% |
| Appeal to Authority | 774 | 8.9% |
| Bandwagon | 704 | 8.1% |
| Slippery Slope | 685 | 7.9% |
| False Dilemma | 672 | 7.7% |
| Appeal to Nature | 627 | 7.2% |
| Appeal to Tradition | 607 | 7.0% |
| Straw Man | 599 | 6.9% |
| Appeal to Emotion | 391 | 4.5% |

## Minority / Long-Tail Classes (Post-Augmentation)
| Class | Count | Percentage |
| :--- | :---: | :---: |
| Affirming Consequent | 238 | 2.7% |
| Composition | 200 | 2.3% |
| Division | 200 | 2.3% |
| Moving Goalposts | 25 | 0.3% |
| No True Scotsman | 25 | 0.3% |
| Tu Quoque Contextual | 24 | 0.3% |

*Note: Post-expansion counts for formal fallacy classes (e.g., Affirming Consequent → 555) are not reflected here. See `data/unified_training_data_v1.1.json` for the current distribution.*

## Label Quality Concerns (Post-Audit)
1. **Multi-Turn Sparsity**: Classes like `moving_goalposts` (25 samples) remain high-risk; targeted expansion planned in the 10K Strategy.
2. **Synthetic Bias**: Largely mitigated by sanitization of "user/assistant" tokens and context-shift augmentation.
3. **Lexical Shortcuts**: Successfully reduced for multi-turn categories through token sanitization. Domain-specific noun-bias in `composition`/`division` reduced via vocabulary diversification.

## Source of Truth
The authoritative dataset is `data/unified_training_data_v1.1.json` (12,442 samples). See `docs/DATASET_MASTER.md` for the canonical reference.
