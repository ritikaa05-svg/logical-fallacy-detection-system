# Training Configuration Guide

> **Synced 2026-08-03**: values below reflect the production v1.3 training run.
> Production entry point: `cloud_training/scripts/train_stage3_v13.py`.
> Config reference: `cloud_training/configs/training_config.yaml`.

## Overview
Class-weighted loss functions address the 29.9:1 class imbalance (max:min count
ratio in v1.3) without relying on synthetic oversampling.

## Production Training Configuration (v1.3)

| Item | Value |
|---|---|
| Base model | `microsoft/deberta-v3-small` (off-the-shelf HF, fine-tuned) |
| Loss | Single-head CrossEntropy with sqrt-inverse-frequency class weights |
| Optimizer | AdamW, LR 1e-5, weight decay 0.01, grad clip 1.0 |
| Schedule | Linear warmup 10% of steps → linear decay |
| Epochs / batch | 6 epochs, BS 16 per GPU (DataParallel ×n_gpus) |
| Precision | FP16 AMP (autocast + GradScaler) on CUDA |
| Split | Stratified 90/10, `--seed 42` (any seed configurable) |
| Freezing | 0% (full fine-tune) |
| Callbacks | Best-val-F1 checkpoint; no early stopping |

## Configuration
Update `cloud_training/configs/training_config.yaml` to modify weighting behavior:

```yaml
  loss_weighting:
    enabled: true
    strategy: 'sqrt_inverse_frequency' # Options: inverse_frequency, sqrt_inverse_frequency, effective_num_samples
```

## Implementation Details
- **`backend/app/core/weighting.py`**: Contains the weighting logic for different strategies.
- **Oversampling**: Removed from training scripts. Rely on `loss_weighting` in your configuration instead.

## Training in Google Colab / Kaggle
1.  **Prepare Environment**: Ensure `backend/` and `cloud_training/` are in the path.
2.  **Import Weights**:
    ```python
    from backend.app.core.weighting import get_class_weights

    # Calculate weights from your label counts (y_train)
    counts = np.bincount(y_train)
    weights = get_class_weights(counts, strategy=config['model']['loss_weighting']['strategy'])

    # Apply to Loss Function
    criterion = nn.CrossEntropyLoss(weight=weights.to(device))
    ```
3.  **Baseline vs Weighted**:
    - **Baseline**: Set `loss_weighting.enabled: false`.
    - **Weighted**: Set `loss_weighting.enabled: true` and select a `strategy`.

## Split-Variation Study (defense preparation)
To quantify train/test split variance, run all three seeds and compare:

```bash
python cloud_training/scripts/run_seed_variation.py --seeds 42 2024 7
# Output: cloud_training/results/seed_variation.json  (mean ± std of val macro F1)
```

## Standardized Evaluation (defense preparation)
One command reproduces every number on slide 09:

```bash
venv/bin/python scripts/eval_zero_shot.py            # baselines + zero-shot + fine-tuned macro F1
venv/bin/python scripts/eval_zero_shot.py --report-only  # full per-class report, seed-42 val split
```

## Stage 1 Gatekeeper Retrain (defense preparation)

The deployed `models/stage1_v12` checkpoint is degenerate (salience = 1.000 for
every input, no ONNX export). Retrain it in the cloud:

```bash
python cloud_training/scripts/train_stage1_v13.py \
    --data data/stage1_splits.json \
    --output-dir models/stage1_v13_classifier \
    --epochs 3 --batch-size 32 --lr 3e-5 --seed 42
```

Afterwards update `STAGE1_MODEL_PATH=./models/stage1_v13_classifier` in `.env`.

## One-Notebook Cloud Run (Kaggle)

Both cloud jobs (stage 1 retrain + stage 3 seed variation) are packaged in a
single notebook: `cloud_training/notebooks/defense_prep_training.ipynb`.
The two training scripts are **embedded in the notebook** (no script uploads);
you only upload the data.

1. Create a private Kaggle dataset `logiscan-data` with the 2 JSON files
   (`data/stage1_splits.json`, `data/unified_training_data_v1.3.json` — root or
   `data/` subfolder; the notebook locates them anywhere under `/kaggle/input`).
2. Create a notebook: **T4x2** accelerator, **Internet ON**, attach the dataset,
   replace the source with the .ipynb, **Run all**.

Outputs (listed in the final cell, ready for download):
- `models/stage1_v13_classifier.zip` — unzip into repo `models/`, then set
  `STAGE1_MODEL_PATH=./models/stage1_v13_classifier` in `.env`.
- `cloud_training/results/seed_variation.json` — per-seed macro F1 (42/2024/7)
  with mean ± std for the split-variation slide.

Details: `cloud_training/README_UPLOAD.md`. Regenerate the notebook after editing
either training script: `venv/bin/python cloud_training/scripts/build_selfcontained_notebook.py`.
