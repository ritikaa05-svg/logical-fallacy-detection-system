# Phase A Verification Audit — 2026-06-11

## Scope
Full audit of model architecture, dataset, labels, training pipeline, inference pipeline,
backend integration, and deployment configuration.

---

## 1. Dataset Verification

**File**: `data/unified_training_data.json`
**Samples**: 10,786
**Unique labels**: 24

| Label | Count |
|---|---|
| ad_hominem | 537 |
| affirming_consequent | 288 |
| appeal_to_authority | 774 |
| appeal_to_emotion | 541 |
| appeal_to_nature | 627 |
| appeal_to_tradition | 607 |
| bandwagon | 704 |
| begging_the_question | 311 |
| composition | 100 |
| denying_antecedent | 100 |
| division | 100 |
| equivocation | 100 |
| factual_statement | 599 |
| false_cause | 446 |
| false_dilemma | 672 |
| hasty_generalization | 1044 |
| moving_goalposts | 125 |
| no_true_scotsman | 125 |
| red_herring | 928 |
| slippery_slope | 685 |
| straw_man | 599 |
| tu_quoque | 50 |
| tu_quoque_contextual | 124 |
| valid_reasoning | 600 |

**Verdict**: ✅ Dataset is valid — 24 classes present, no empty texts, label names are consistent.

**Imbalance ratio**: hasty_generalization (1044) : tu_quoque (50) = 20.9:1

---

## 2. Checkpoint Verification

### 2a. phase4_final_model
| Property | Value |
|---|---|
| Path | `models/phase4_final_model/model.safetensors` |
| Config architecture | `DebertaV2ForSequenceClassification` |
| Model type | `deberta-v2` |
| Hidden layers | 6 |
| Hidden size | 768 |
| Intermediate size | 3072 |
| Attention heads | 12 |
| Classifier weight | `[24, 768]` |
| Classifier bias | `[24]` |
| Key prefix | `deberta.*` (standard HF) |
| Total keys | 106 |
| Tokenizer | `DebertaV2Tokenizer`, vocab_size=128001 |
| Load test | ✅ Loads via `AutoModelForSequenceClassification.from_pretrained` |
| Inference test | ✅ Returns 24-class logits |

### 2b. phase4_stabilized_model
| Property | Value |
|---|---|
| Path | `models/phase4_stabilized_model/model.safetensors` |
| Architecture | Same as phase4_final_model (6 layers, 24-class single head) |
| Transformer version | `5.9.0` (vs `5.10.1` in final) |
| Load test | ✅ |

### 2c. unified_classifier ❌ CRITICAL
| Property | Value | Issue |
|---|---|---|
| Path | `models/unified_classifier/pytorch_model.bin` | |
| Config architecture | Default `DebertaV2Config` (24L, 1536H, 24 attn heads) | **Config has no arch params** — falls back to Deberta-large defaults |
| Actual weights | 12 layers, 768 hidden | Config mismatch |
| Fine labels | 22 | Missing `factual_statement` and `valid_reasoning` |
| Coarse labels | 4 | Present |
| Key prefix | `encoder.encoder.layer.*` | **Extra `encoder.` wrapper** vs expected `deberta.encoder.layer.*` or `encoder.layer.*` |
| Model keys | 388 (AutoModel.from_config) | |
| Checkpoint keys | 202 | |
| Key overlap | **0 of 388** | **All weights randomly initialized** |
| Head: coarse_head | `[4, 768]` in ckpt | Model creates `[4, 1536]` (config says 1536) |
| Head: fine_head | `[22, 768]` in ckpt | Model creates `[22, 1536]` |
| Load test | ❌ `from_pretrained` with `ignore_mismatched_sizes=True` loads with 0 matched keys | |

---

## 3. Architecture Mismatches

### M1 — Primary Model is Untrained Random Weights
- `DebertaV3MultiHead` class uses `AutoModel.from_config(config)` which creates `encoder.layer.*` keys
- Checkpoint stores `encoder.encoder.layer.*` keys (extra `encoder.` wrapper)
- Config defaults create 24-layer/1536-hidden architecture, but checkpoint is 12-layer/768-hidden
- **Result**: `ignore_mismatched_sizes=True` causes 0% weight transfer. Model is random.

### M2 — 22 vs 24 Label Mismatch
- `unified_classifier/config.json` lists 22 fine labels
- `UnifiedClassifier.DEFAULT_FINE_LABELS` lists 22
- Phase 4 taxonomy requires 24 (adds `factual_statement`, `valid_reasoning`)

### M3 — Config Defaults vs Checkpoint Reality
```
AutoConfig.from_pretrained(unified_classifier):
    num_hidden_layers: 24    # wrong, should be 12
    hidden_size: 1536        # wrong, should be 768
    num_attention_heads: 24  # wrong, should be 12
```

### M4 — .env Path Override
- `config.py` defaults `STAGE2_MODEL_PATH` to `./models/unified_classifier`
- `.env` overrides to `models/stage2_fallacy_classifier` (does not exist)

---

## 4. Contradictions

| Ref | Claim | Evidence | Contradiction |
|---|---|---|---|
| C1 | `ARCHITECTURE.md` says "24-way classification" | `unified_classifier` has 22 labels | Deployed model doesn't match doc |
| C2 | `BLOCKERS.md` lists current blockers | Architecture mismatch undocumented | Most critical blocker is missing from list |
| C3 | `PHASE4_EVAL_RESULTS.json` reports Macro-F1=0.906 | This is for `phase4_final_model`, not deployed model | Eval is for a different model than production |
| C4 | `training_config.yaml` says v3-base, 3 epochs | Notebooks use v3-small, 6 epochs | Config not followed during training |
| C5 | `MODEL_REALITY_CHECK.md` documented the mismatch | Document was created but not actioned | Known CRITICAL bug never fixed |
| C6 | `.env` API token was live | Token (redacted) | Credential exposure in committed file — now revoked |

---

## 5. Root Causes

### R1: Key Prefix Mismatch
The `DebertaV3MultiHead` class saves checkpoints via `save_pretrained`, which serializes `model.state_dict()`. The `AutoModel.from_config()` submodule creates keys under `encoder.layer.*`, but an earlier save was done from a module-wrapped version that added `encoder.encoder.layer.*`. The class was redesigned but the re-save was never performed.

**Fix**: Replace custom `DebertaV3MultiHead` class with standard `AutoModelForSequenceClassification` and re-point to `phase4_final_model`.

### R2: Incomplete Taxonomy Update
When Phase 4 added `factual_statement` and `valid_reasoning`, the `unified_classifier/config.json` and `DEFAULT_FINE_LABELS` constants were not updated. The Phase 4 model itself (`phase4_final_model`) has the correct 24 labels.

**Fix**: Replace primary model path with `phase4_final_model`.

### R3: Config Drift
`training_config.yaml` was written before the final training runs and never updated to match actual parameters. The config is documentation-only and not consumed by any automated pipeline.

**Fix**: Update config to match actual training runs, or remove it.

### R4: Configuration Override
`.env` sets model paths that override `config.py` defaults. The `.env` values point to non-existent directories.

**Fix**: Remove or correct `.env` overrides.

### R5: Credential Exposure
A live HF API token was committed to the repository.

**Fix**: Revoke the token and remove from `.env`.

---

## 6. Recommended Changes Summary

| # | Change | Target | Severity |
|---|---|---|---|
| 1 | Point `STAGE2_MODEL_PATH` and `STAGE3_MODEL_PATH` to `models/phase4_final_model` | `config.py:35-41`, `.env` | CRITICAL |
| 2 | Replace `DebertaV3MultiHead` with standard `AutoModelForSequenceClassification` | `unified_classifier.py:17-84` | CRITICAL |
| 3 | Adapt `_run_inference_unified` and `_process_logits` for single-head model | `unified_classifier.py:299-518` | HIGH |
| 4 | Remove broken fallback chain (`_load_fallbacks`, `model_s2/s3`) | `unified_classifier.py:184-212` | MEDIUM |
| 5 | Update `DEFAULT_FINE_LABELS` to 24 | `unified_classifier.py:98-104` | HIGH |
| 6 | Update `LOW_SUPPORT_CLASSES` with new labels | `orchestrator.py:41-51` | MEDIUM |
| 7 | Remove HF token from `.env` | `.env` | HIGH |
| 8 | Update `training_config.yaml` to match actual runs or delete | `training_config.yaml` | LOW |

---

## 7. Deployment Impact

- **Before**: Backend loads broken `unified_classifier` → 0% key match → falls to mock mode → produces fake data
- **After**: Backend loads verified `phase4_final_model` → 24-class inference → real predictions at Macro-F1≈0.906
- **Coarse category**: Derived from `SHADOW_COARSE_MAP` instead of separate coarse head
- **Latency**: Decreases (6L model vs 24L random init)
- **Memory**: Decreases (6L model vs 24L random init)
- **Shadow mode**: Already running `phase4_final_model` — logic stays, can validate before/after

---

*Auditor: Principal ML Engineer / AI Systems Architect*
*Date: 2026-06-11*
*Status: Awaiting implementation approval*
