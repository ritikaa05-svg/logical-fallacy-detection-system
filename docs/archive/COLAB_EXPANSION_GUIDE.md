# Colab Expansion Execution Workflow

## 1. Environment Setup
- Mount Google Drive to persist generated batches.
- Ensure `backend` and `scripts` are in the system path.
- Install dependencies: `pip install transformers torch accelerate bitsandbytes`

## 2. Execution Loop (Per Batch)
Execute the following steps for every generation batch:

1. **Generate**: Run `python3 scripts/expansion/generate_hard_negatives.py --batch-size 20 ...`
2. **Validate**: Run `python3 scripts/expansion/validate_generated_samples.py --input-file ...`
3. **Audit**: Run `python3 scripts/audit_lexical_bias.py` on the batch.
4. **Manifest**: Use `scripts/expansion/manifest_utils.py` to record the batch.
5. **Merge**: Run `cat batch.json >> data/final_training_data.json`.
6. **Deduplicate**: Run `python3 scripts/clean_dataset.py`.
7. **Inventory**: Run `python3 scripts/expansion/update_inventory.py` (if script exists) or manually sync `docs/DATASET_INVENTORY.md`.

## 3. Batch Plan
| Phase | Focus | Target |
| :--- | :--- | :--- |
| **A** | Hard Negatives, Counterfactuals | 800 samples |
| **B** | Multi-Turn Reasoning | 500 samples |
| **C** | Domain Diversification | 1,000 samples |
| **D** | Final Balancing | ~500 samples |

## 4. Resilience
- **Resume Support**: The system checks `data/generation_manifest.json` on startup. If a batch is interrupted, check the manifest and re-run the specific target-class batch.
- **Checkpointing**: Use `colab_utils.ExpansionState` in your training loop to log progress after every merge.
