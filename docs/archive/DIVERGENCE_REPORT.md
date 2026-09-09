# Dataset Divergence Report: Pre- vs. Post-Cleaning

## 1. Metrics Comparison

| Class | Pre-Cleaning Bias (%) | Post-Cleaning Bias (%) | Delta |
| :--- | :---: | :---: | :---: |
| moving_goalposts | 18.69% | 10.88% | -7.81% |
| tu_quoque_contextual | 17.60% | 13.08% | -4.52% |
| no_true_scotsman | 19.20% | 14.17% | -5.03% |
| composition | 11.18% | 11.18% | 0.00% |
| division | 12.29% | 12.29% | 0.00% |
| equivocation | 9.44% | 9.44% | 0.00% |
| denying_antecedent | 8.61% | 8.61% | 0.00% |

## 2. Key Findings
- **Sanitization Success**: The "user/assistant/turn" tokens were the primary drivers of shortcut bias in the multi-turn synthetic categories. Their removal led to significant drops in bias scores for those classes.
- **Structural Persistence**: Classes like `composition` and `division` remained unchanged because they contained no "user/assistant" tokens. Their bias is rooted in the limited domain of their examples (e.g., "metal", "book"), not the synthetic formatting.
- **Quantitative Conclusion**: We have successfully removed the most egregious "synthetic formatting" shortcuts, but domain-specific lexical bottlenecks remain in the physical-object fallacy categories.

## 3. Implications for Augmentation
- Multi-turn classes are now "cleaner" but still low-count (25). Augmentation here will be highly effective.
- Domain-specific classes (`composition`, `division`) need broader context augmentation to overcome their current noun-dependency.
