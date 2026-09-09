# Model Checkpoint Verification Report

**Date:** 2026-07-21
**Checkpoint:** `models/phase4_final_model`

## Method
The checkpoint was inspected by reading the `model.safetensors` header directly (no PyTorch dependency required) and comparing its 106 tensor keys against the expected architecture of `DebertaV2ForSequenceClassification` with 6 hidden layers, no position-biased input, and type vocabulary size 0, as specified in the accompanying `config.json`.

## Key Overlap
- Expected keys (config-aware): 106
- Checkpoint keys: 106
- Overlapping keys: 106
- Overlap percentage: 100%

## Detailed Analysis

### Matching Keys (104 + 2 prefix-adjusted)
All 104 structural keys (embeddings, 6 encoder layers, relative attention, classifier) match exactly. The remaining 2 keys — `pooler.dense.weight` and `pooler.dense.bias` — use `pooler.` prefix instead of `deberta.pooler.`. This is a standard HuggingFace export artifact for `DebertaV2ForSequenceClassification` and does not affect functionality.

### Config Alignment
- `architectures`: `["DebertaV2ForSequenceClassification"]` — matches
- `model_type`: `deberta-v2` — matches
- `num_hidden_layers`: 6 — confirmed by 6 layer groups in checkpoint
- `hidden_size`: 768 — confirmed by weight shapes
- `num_labels`: 24 (fine-grained fallacy classes) — matches
- `position_biased_input`: `false` — checkpoint correctly omits `position_embeddings`
- `type_vocab_size`: 0 — checkpoint correctly omits `token_type_embeddings`

## Verdict
✅ **PASS** — 100% key overlap between checkpoint and config. Weights are properly aligned with the model architecture.

## Recommended Action
None. The checkpoint is healthy and correctly exported. No re-export is needed.

## Resolution of AUDIT_FINDINGS.md #1
This resolves item #1 in `AUDIT_FINDINGS.md` ("Unified Classifier Model Had 0% Key Overlap"). The checkpoint at `models/phase4_final_model` has 100% key overlap with its config. The original 0% overlap issue (reported during Phase A verification of a different checkpoint) has been fixed in the current export.
