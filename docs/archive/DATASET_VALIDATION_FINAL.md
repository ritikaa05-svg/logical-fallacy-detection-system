# Dataset Validation Final (Phase 4)

## Summary
The unified dataset `data/unified_training_data.json` is structurally sound but exhibits **significant minority-class risks** and **lexical bias potential** in new boundary classes.

## Global Metrics
- **Total Samples**: 9,507
- **Total Labels**: 24
- **Exact Duplicates**: 1 (0.01%)
- **Source Heterogeneity**:
    - `core`: 7,531 (79.2%) - High quality, human-verified.
    - `synthetic`: 1,420 (14.9%) - Template-based.
    - `raw_pool`: 482 (5.1%) - LLM-generated.
    - `synthetic_multiturn`: 74 (0.8%) - Low support.

## Distribution & Imbalance
- **Largest Class**: `hasty_generalization` (1,044)
- **Smallest Class**: `tu_quoque_contextual` (24)
- **Class Imbalance Ratio**: **43.5 : 1**
- **Boundary Classes**:
    - `valid_reasoning`: 560
    - `factual_statement`: 560
    - Total Non-Fallacious: 1,120 (11.8%)

## Risk Analysis

### 1. Template Overfitting (High)
- **Target Classes**: `valid_reasoning`, `factual_statement`, `composition`, `division`.
- **Finding**: These classes are 100% synthetic and follow a strict "Variant + Base Template" structure.
- **Risk**: The model may learn to recognize the 27 stylistic variants (e.g., "I read online that...") rather than the underlying logical structure.

### 2. Minority-Class Collapse (Critical)
- **Target Classes**: `tu_quoque_contextual`, `moving_goalposts`, `no_true_scotsman`.
- **Finding**: All multi-turn classes have < 30 samples.
- **Risk**: These will likely achieve 0.0 F1 score in a standard cross-entropy training run.

### 3. Lexical Shortcut Risks
- **Finding**: `appeal_to_nature` likely over-indexes on the word "natural".
- **Finding**: `factual_statement` may over-index on entities (Paris, Sun, Earth) due to template repetition.

## Verdict
The dataset is **Ready for Phase 4 Baseline**, but requires **Weighted Random Sampling** or **Focal Loss** to prevent majority-class dominance. 10K samples should still be pursued to bolster the minority multi-turn classes.
