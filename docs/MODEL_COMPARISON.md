# Model Series Benchmark (Old vs New — Retirement Record)

**Date:** 2026-08-05 · **Hardware:** CPU (torch 2.13.0, no GPU) · **Script:** `scripts/benchmark_model_series.py` (reproducible) · **Raw results:** `results/model_series_benchmark.json`

## Purpose

Archival record taken **before** retiring the legacy model generation. Answers:
"was the current deployment actually better than what it replaced?" — verified
on the standardized splits used throughout the defense evaluation before any
deletion.

## Protocol

| Benchmark | Split | n | Notes |
|---|---|---|---|
| Stage 1 (binary gate) | `data/stage1_splits.json` val | 1,155 | same split used for stage 1 training |
| Stage 2/3 (29 classes) | stratified 90/10 of v1.3, seed 42 | 1,695 | identical to `scripts/eval_zero_shot.py` |
| Phase 4 (24 classes) | same seed-42 val, filtered to the 24 labels `phase4_final_model` supports | 1,445 | excludes the 5 rescued formal classes; current model evaluated on the same subset |

Metrics: macro-F1 and accuracy. Models loaded via HuggingFace (safetensors);
class indices mapped through each model's own `id2label` to the shared label
list so label ordering differences cannot distort scores.

## Results

### Stage 1 — gatekeeper (binary)

| Model | Macro F1 | Accuracy |
|---|---|---|
| `stage1_v12` (retired 2026-08-05) | 0.4954 | 0.9818 |
| **`stage1_v13_classifier` (current)** | **0.9272** | **0.9948** |

`stage1_v12` was confirmed degenerate (constant salience 1.000 → majority-class
macro F1). The retrained model nearly doubles macro F1 while improving accuracy.
→ **Retirement justified.**

### Stage 2/3 — 29-class fine classifier

| Model | Macro F1 | Accuracy |
|---|---|---|
| **`stage3_v12` (RoBERTa-base, 12 layers — archived)** | **0.9134** | **0.8985** |
| `stage3_v13_classifier` (DeBERTa-v3-small, 6 layers — current) | 0.8971 | 0.8796 |

**Finding: the old RoBERTa-base model scores slightly HIGHER (+0.016 macro F1)
than the current deployment on this split — including on the natural-text
classes** (hasty_generalization 0.636 vs 0.550, false_cause 0.764 vs 0.688,
straw_man 0.983 vs 0.921, appeal_to_authority 0.814 vs 0.761). The v13 swap was
an architecture-consolidation decision (single-head 29-label DeBERTa, matching
the Phase-4 architecture, ONNX CPU deployment), not an accuracy win on this
benchmark.

**Consequence:** `stage3_v12` is **kept on disk as an archival baseline** rather
than deleted. Current production remains `stage3_v13_classifier`, whose
variance is measured across split seeds (0.885 ± 0.0069, `results/seed_variation.json`).
If a future accuracy re-evaluation favors the archival model, re-deploying it
(ONNX export, path switch) is a documented option.

### Phase 4 — 24-class predecessor (retired)

| Model | Macro F1 | Accuracy |
|---|---|---|
| `phase4_final_model` (retired 2026-08-05) | 0.8024 | 0.8048 |
| **`stage3_v13_classifier` (current, same 24-class subset)** | **0.8756** | **0.8588** |

The current model adds the 5 rescued formal classes and still beats Phase 4 on
the shared 24-class subset. → **Retirement justified.**

## Caveats

- Single-split point estimates; the seed-variation study (`results/seed_variation.json`)
  quantifies split sensitivity for the current model (std ≈ 0.007).
- The seed-42 val split is template-optimistic for synthetic classes (F1 = 1.00
  rows); natural-text classes are the honest signal, and the archive model
  leads there too — see slide 09 caveat.
- Phase-4's legacy 0.79 report was measured on a different eval set/protocol
  and is not comparable to the 0.8024 figure above.

## Disposition

| Model | Verdict | Reason |
|---|---|---|
| `stage1_v12` | **Deleted** | degenerate; new model far superior |
| `phase4_final_model` | **Deleted** | superseded on both accuracy and class coverage |
| `stage3_v12` | **Archived (kept)** | scores higher on the standardized split; kept for reference/re-deployment option |
| `stage3_v13_classifier` | **Production** | consolidated architecture, ONNX, measured variance |
| `stage1_v13_classifier` | **Production** | retrained gatekeeper (val F1 0.9974 / test F1 0.9991) |
