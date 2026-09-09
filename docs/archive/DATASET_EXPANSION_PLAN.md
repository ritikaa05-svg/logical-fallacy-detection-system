# 10K Dataset Expansion Strategy (Approved)

## Objective
Evolve LogiScan from a "keyword matcher" to a "logic reasoner" by increasing the dataset to **10,000 high-quality samples** through targeted diversification.

---

## 1. Hard Negative Analysis (Target: 1,500 samples)
We need valid arguments that "sound" like fallacies but are logically sound to break lexical shortcuts.
- **Authority Negative**: "According to the IPCC 2024 report, global temperatures are rising due to carbon emissions." (Not an Appeal to Authority).
- **Emotion Negative**: "We should donate to the food bank because 1 in 5 children in our city are hungry." (Fact-based appeal, not a fallacy).
- **Hasty Generalization Negative**: "All 50 state governments in the US have an executive branch." (Verified universal fact).

## 2. Counterfactual Pair Analysis (Target: 500 pairs)
Generate "Reasoning Mirrors" to teach the model the difference between a flawed and valid step.
- **Fallacious**: "I ate a burger and then felt better, so burgers cure depression."
- **Valid**: "I ate a burger which provided necessary calories, alleviating my immediate hunger-induced fatigue."

## 3. Domain Diversity Expansion
Diversify samples across the following underrepresented domains:
| Domain | Target | Strategy |
| :--- | :---: | :--- |
| **Law & Legal** | 300 | Use LLM to generate court-room style argument structures. |
| **Medical/Science** | 300 | Focus on `false_cause` and `hasty_generalization` in research contexts. |
| **Technology** | 200 | Focus on `moving_goalposts` and `straw_man` in software spec debates. |
| **Education** | 200 | Academic policy discussions. |

## 4. Multi-Turn Reasoning (Target: 500 total)
Expand the multi-turn classes to move away from "User/Assistant" templates.
- **Classes**: `moving_goalposts`, `no_true_scotsman`, `tu_quoque`.
- **Format**: Generate IRC-style chat logs, Reddit threads, and debate transcripts with multiple participants.

---

## 5. Target 10K Distribution Design

| Component | Samples | Rationale |
| :--- | :---: | :--- |
| **Balanced Core Fallacies** | 6,500 | Existing balanced set with de-duplicated minority floor. |
| **Hard Negatives** | 1,500 | Essential for preventing False Positives on factual statements. |
| **Multi-turn Logic** | 500 | Necessary for Phase 4 (Argument Structure). |
| **Counterfactual Pairs** | 1,000 | Teaches structural comparison. |
| **Valid Reasoning** | 500 | Sound arguments (Modus Ponens, etc.) to break keyword triggers. |

## 6. Boundary Cleanup (Fallacy Boundary Audit Result)
The 10k set will no longer assume "Argument = Fallacy". We are introducing `non_fallacious` sub-classes into the Fine-Grained taxonomy to allow the model to "Opt-Out" of a fallacy label.
- **Target FPR**: < 5% on logic-adjacent non-fallacies.

---

## Implementation Roadmap
1. **Week 1**: Generate Hard Negatives for Top 10 fallacies.
2. **Week 2**: Diversify Multi-turn datasets (move beyond User/Assistant).
3. **Week 3**: Compile "Factual/Logic Definition" class to act as a buffer.
4. **Week 4**: Final merge and de-duplication pass.
