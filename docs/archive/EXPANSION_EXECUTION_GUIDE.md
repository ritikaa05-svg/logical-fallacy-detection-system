# Expansion Execution Guide

## Overview
This guide covers how to generate, validate, and merge new training data to reach the 10,000-sample target.

## How to Generate New Samples
Use the scripts in `scripts/expansion/` to generate batches for specific fallacies or categories. The scripts are now fully implemented and integrate directly with the `LLMSynthesisService`.

```bash
# Example: Generate 10 Hard Negatives for Appeal to Authority
python3 scripts/expansion/generate_hard_negatives.py --target-class appeal_to_authority --batch-size 10 --output-file data/batch_auth_neg.json
```

## How to Validate
Run the validation script on a batch before merging to check for schema compliance, duplicates, and quality:
```bash
python3 scripts/expansion/validate_generated_samples.py --input-file data/batch_auth_neg.json
```

## Merging and Rebuilding
1. **Merge**: Append the validated JSON list of samples to `data/final_training_data.json`.
2. **Deduplicate**: The `validate_generated_samples.py` script checks for duplicates within the batch, but you should run `scripts/clean_dataset.py` after merging to ensure no collisions with the existing 8,707 samples.
3. **Rebuild**: The resulting `data/final_training_data.json` is ready for training.

## Expected Output Example
A successful generation will produce a JSON array:
```json
[
  {
    "text": "The scientific consensus indicates that vaccination programs reduce mortality.",
    "fallacy": "none",
    "source": "hard_negative_gen",
    "target_class": "appeal_to_authority"
  }
]
```
