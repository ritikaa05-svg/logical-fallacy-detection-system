# Hard Negative Quality Audit: Batch 1

## 1. Sample Review (n=50)
| Category | Count | Example |
| :--- | :--- | :--- |
| Valid Argument | 5 | "The study shows that X increases Y, so Y is a reliable indicator." |
| Factual Statement | 35 | "According to the CDC, vaccination is effective." |
| Citation/Reference | 10 | "The university research board published findings." |
| Definition | 0 | - |
| Meta-logic | 0 | - |

## 2. Argument Requirement Verification
- **Status**: **FAILED**. 70% of Batch 1 samples are simple factual statements or bare citations.
- **Requirement**: Hard negatives must be reasoning-based, not just factual.
- **Action**: The current template-based generation (`scripts/expansion/generate_hard_negatives.py`) is too simplistic.

## 3. Shortcut Analysis (Trigger Words)
- 'according to': 100 occurrences (found in 100% of samples)
- 'study': 23 occurrences
- 'research': 19 occurrences
- **Verdict**: Extreme lexical bias detected.

## 4. Distribution Check
- **Authority-related**: 100% (All samples use the "According to..." template).
- **Emotion-related**: 0%
- **Causal/Generalization**: 0%

## 5. Summary & Recommendation
The Batch 1 generation failed the quality audit. The template is brittle and produces factual statements, not "Hard Negative" arguments.

**Immediate Actions:**
1. **Disable template**: The `generate_hard_negatives.py` template is rejected.
2. **Implement LLM-based reasoning**: The generator must be updated to use the LLM synthesis service to create diverse, multi-premise arguments, even if it requires lowering the batch size or accepting longer latency.
3. **Redo Batch 1**: Batch 1 will be purged and regenerated once the generator is improved.
