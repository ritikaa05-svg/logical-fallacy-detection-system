# LogiScan Defense-Prep — Data Upload (scripts are embedded in the notebook)

You only upload the DATA. The training scripts are embedded in the notebook
`cloud_training/notebooks/defense_prep_training.ipynb` — no script uploads needed.

## Steps

1. Create a private Kaggle dataset named **`logiscan-data`** (New Dataset → upload
   files) containing exactly 2 files:
   - `stage1_splits.json`
   - `unified_training_data_v1.3.json`
   (They may sit at the dataset root or inside a `data/` subfolder — the notebook
   finds them anywhere under `/kaggle/input`.)

2. Create a notebook: **T4x2** accelerator, **Internet ON**, add the
   `logiscan-data` dataset as input, replace the source with
   `defense_prep_training.ipynb`, **Run all**.

3. Download from the last cell:
   - `models/stage1_v13_classifier.zip` — unzip into repo `models/`, set
     `STAGE1_MODEL_PATH=./models/stage1_v13_classifier` in `.env`
   - `cloud_training/results/seed_variation.json` — macro F1 per seed with mean ± std
     (paste into slide 09 placeholders)

Expected wall time on T4x2: stage 1 ~10-20 min, 3× stage 3 ~1.5-2.5 h
(12 h Kaggle session limit).

## If the notebook is missing

Regenerate it after editing a training script:
`venv/bin/python cloud_training/scripts/build_selfcontained_notebook.py`
