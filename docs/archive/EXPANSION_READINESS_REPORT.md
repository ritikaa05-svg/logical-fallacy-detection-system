# Expansion Readiness Report

## 1. Dataset Baseline
- **Version**: `v1.1.0-final-ready`
- **Count**: 8,686
- **Status**: Verified and cleansed.

## 2. Expansion Targets
- **Total Samples Target**: 10,000
- **Primary Focus**: `moving_goalposts`, `no_true_scotsman`, `tu_quoque_contextual`.
- **Buffer**: 1,000 samples of `none` (valid/factual).

## 3. Validation & Provenance
- **Validation Pipeline**: `scripts/expansion/validate_generated_samples.py` ensures schema and quality.
- **Provenance**: Every batch must be registered in `data/generation_manifest.json` using `scripts/expansion/manifest_utils.py`.

## 4. Rollback Process
1. **Detect**: Check for regression in `scripts/audit_lexical_bias.py`.
2. **Revert**: If a batch corrupts the dataset, restore the baseline: `cp data/cleaned_training_data.json data/final_training_data.json`.
3. **Clean**: Remove the corresponding entry in `data/generation_manifest.json`.

## 5. Final Readiness
- **Repository Readiness**: Fully ready for expansion execution.
- **Workflow**: Generate (Script) -> Validate (Validation script) -> Manifest (Manifest script) -> Merge (Manual) -> Deduplicate (Clean script).
