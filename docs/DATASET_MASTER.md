# Dataset Overview & Versioning

This document serves as the master reference for the LogiScan dataset lifecycle, linking the specific audit and inventory reports.

## Dataset Lifecycle

1.  **Raw Collection** (`data/raw_generation_pools/`): Initial generation pools for each fallacy type.
2.  **Cleaning & Augmentation**:
    *   **Preprocessing**: Token sanitization and lexical bias mitigation (`backend/app/services/lexical_bias_mitigator.py`).
    *   **Augmentation**: Synthetic generation of minority classes.
3.  **Deduplication & Hard Negative Expansion**: An exact deduplication pass was performed on the merged dataset, followed by hard negative expansion (1.6K+ samples for `affirming_consequent` and other minority classes). This produced v1.1.0 (12,442 samples).
4.  **Formal Class Data Rescue**: Added 4,500 adversarial formal-fallacy examples from `formal_hard_negative_gen` (500 each for `undistributed_middle`, `illicit_major`, `illicit_minor`, `exclusive_premises`, `existential_fallacy` plus 500 more `denying_antecedent`). This produced v1.2.0 (16,942 samples).
5.  **Contrastive Hard-Negative Mining**: Generated 996 near-miss adversarial examples structurally similar to known fallacies, merged as source `near_miss_hard_negative`. This produced v1.3.0 (17,938 samples).

## Documentation Mapping

| Document | Purpose | Relationship |
| :--- | :--- | :--- |
| `DATASET_INVENTORY.md` | Provides snapshot of 8,686-count pre-expansion dataset. | ⚠️ Out of date (v1.3+ current). |
| `DATASET_AUDIT.md` | Analyzes composition, balance, and quality concerns. | Describes pre-expansion state. |
| `DATASET_GAP_ANALYSIS.md` | Identifies missing samples for future expansion. | Based on `DATASET_AUDIT.md` requirements. |

## Version Reference

| Version | Status | Total Samples | Key Characteristics |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | Deprecated | ~8,707 | Post-augmentation, pre-deduplication. |
| **v1.1.0** | Deprecated | 12,442 | Post-deduplication + hard negative expansion (1.6K+). |
| **v1.2.0** | Deprecated | 16,942 | +4,500 formal class rescue (`formal_hard_negative_gen`). |
| **v1.3.0** | **Current** | **17,938** | +996 contrastive near-miss hard negatives. |

### Source Distribution (v1.3.0)

| Source | Samples | Description |
| :--- | :---: | :--- |
| `core` | 7,531 | Base curated dataset |
| `formal_hard_negative_gen` | 4,500 | Adversarial formal fallacy examples (Phase 8.5) |
| `synthetic` | 2,699 | Synthetic generation of minority classes |
| `hard_negative_gen` | 1,656 | Initial hard negative expansion |
| `near_miss_hard_negative` | 996 | Contrastive near-miss examples (Phase 8.3) |
| `raw_pool` | 482 | Raw generation pools |
| `synthetic_multiturn` | 74 | Multi-turn synthetic dialogues |

### Formal Class Coverage (v1.3.0)

| Class | Samples | Notes |
| :--- | :---: | :--- |
| `affirming_consequent` | 555 | Stable across all versions |
| `denying_antecedent` | 600 | Expanded from 100 (v1.1) → 600 (v1.2) |
| `undistributed_middle` | 500 | Rescued from 0 (v1.1) → 500 (v1.2) |
| `illicit_major` | 500 | Rescued from 0 (v1.1) → 500 (v1.2) |
| `illicit_minor` | 500 | Rescued from 0 (v1.1) → 500 (v1.2) |
| `exclusive_premises` | 500 | Rescued from 0 (v1.1) → 500 (v1.2) |
| `existential_fallacy` | 500 | Rescued from 0 (v1.1) → 500 (v1.2) |

**Note:** The JSON file is the source of truth. The INVENTORY, AUDIT, and GAP_ANALYSIS reports (written against the pre-expansion 8,686-count snapshot) are out of date.
