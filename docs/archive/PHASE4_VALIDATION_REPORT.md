# Phase 4 Model Validation Report

This document provides the independent validation results for the Phase 4 fallacy classification model (`models/phase4_final_model`).

## 1. Executive Summary
The claimed **0.9067 Macro-F1** score was **successfully reproduced** on the internal validation set. However, evaluation against a real-world "Gold-Standard" set (500 samples) shows a regression to **0.83 Macro-F1**, indicating a ~10% performance gap when moving beyond synthetic-heavy training templates.

## 2. Quantitative Evidence

### Internal Validation (Reproduced)
- **Macro F1**: 0.9067
- **Micro F1**: 0.8707
- **Accuracy**: 0.87
- **Data Source**: `data/unified_training_data.json` (80/20 split)

### Real-World "Gold-Standard" Audit
- **Macro F1**: 0.83
- **Micro F1**: 0.80
- **Data Source**: `data/gold_standard_eval.json` (500 manually verified real-world samples)

## 3. Per-Class Analysis (Top 5)

| Class | Precision | Recall | F1-Score |
| :--- | :--- | :--- | :--- |
| `straw_man` | 0.96 | 0.99 | 0.98 |
| `factual_statement` | 0.99 | 1.00 | 1.00 |
| `valid_reasoning` | 0.99 | 1.00 | 1.00 |
| `hasty_generalization` | 0.76 | 0.63 | 0.69 |
| `red_herring` | 0.91 | 0.69 | 0.79 |

## 4. Audit Findings

### Metric Inflation
The 0.91 Macro-F1 is partially inflated by "perfect" performance (1.00 F1) on 8 low-support classes that rely on high-quality synthetic templates. These include:
- `composition`, `division`, `moving_goalposts`, `no_true_scotsman`, `tu_quoque_contextual`.

### Generalization Gap
The 10% drop on real-world data is primarily driven by:
1. **Structural Variation**: Real-world arguments are less formulaic than synthetic templates.
2. **Context Leakage**: Some classes (e.g., `affirming_consequent`) show significantly lower recall (0.39-0.50) in diverse conversational contexts compared to the internal test set.

## 5. Model Classification
**STATUS: PRODUCTION READY (Conditional)**

- **Recommended Use**: High-confidence identification for the 15+ well-supported informal fallacies.
- **Experimental**: Formal logic verification and rare classes. Use with symbolic fallback (Z3) is mandatory for formal classes.

---
*Date of Audit: 2026-06-12*
*Auditor: Gemini CLI (Evidence-Based Mode)*
