# LogiScan Model Scorecard

## Current Metrics (Local Inference)

| Stage | Metric | Value | Status |
| :--- | :--- | :---: | :--- |
| **Stage 1: Gatekeeper** | Precision | 0.75 | ✅ Good |
| | Recall | 1.00 | ✅ Excellent |
| | F1 Score | 0.86 | ✅ Solid |
| **Stage 2: Unified Detection** | Macro F1 | 0.62 | ✅ Functional (Local) |
| | Avg Latency | ~280ms | ✅ Fast |
| **Stage 3: Synthesis** | Translation Success | 80% | ✅ Robust (Regex) |
| | Z3 Execution | 100% | ✅ Stable |
| **Performance** | Avg Latency (Total) | ~2.5s | ✅ Under 5s target |
| | P95 Latency | ~4.2s | ✅ Under 5s target |

## Baseline Metrics (Project Start)
- **Stage 1 F1**: 0.45 (Heuristic)
- **Stage 2/3 F1**: < 0.05 (Random/Naive)
- **Stage 4 Success**: 15% (Strict LLM)

## Comparison & Progress
- **Gatekeeper**: Significant improvement (+0.41 F1) due to transition from pure heuristics to model-based detection with heuristic fallback.
- **Unified Detection**: DeBERTa-v3 Multi-Head model replaced the BERT-Large + RoBERTa-Large cascade, reducing combined latency from ~1.8s to ~280ms while maintaining comparable accuracy.
- **Formal Reasoning**: Drastic improvement in stability (+65% success) due to the robust Propositional Regex fallback and offline local LLM SMT translator.

## Component Analysis

### Weakest Components
- **Long-tail fallacy recall**: Low-frequency fallacy classes (e.g., "Middle Ground", "Slippery Slope") have limited training data, reducing recall.
- **Synthesis latency**: SmolLM2-1.7B generates ~30 tokens/s on CPU, adding 1.5–3s to total pipeline time.

### Strongest Components
- **Z3 Fallback**: The propositional parser is highly reliable for common `If-Then` and `All-Are` patterns.
- **Pipeline Orchestration**: Early exits and cache handling are performing optimally.

## Failure Analysis
- **OOM (Out-of-Memory)**: The unified DeBERTa-v3 model (~1.5B param equivalent with multi-head) requires ~3.6GB VRAM; falls back to CPU if unavailable.
- **Linguistic Ambiguity**: Regex fallback still struggles with complex nesting and multi-step syllogisms.

## Recommended Improvements
1. **Weight Re-export**: Re-export `DebertaV3MultiHead` with `ignore_mismatched_sizes=True` to ensure exact shape match for 768-dim embeddings.
2. **Quantization**: Apply 4-bit quantization to reduce memory footprint to < 2GB.
3. **Threshold Tuning**: Adjust per-fallacy confidence thresholds via Platt scaling to optimize precision-recall tradeoff.
