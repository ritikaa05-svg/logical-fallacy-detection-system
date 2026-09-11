"""Build the defense-prep Kaggle notebook: scripts embedded, data uploaded.

Embeds the two training scripts (train_stage1_v13, train_stage3_v13) directly into
`cloud_training/notebooks/defense_prep_training.ipynb` — NO script uploads needed.
The data is NOT embedded: upload the 2 JSON files as a private Kaggle dataset
(`logiscan-data`) and attach it; the notebook locates them under /kaggle/input.

Usage:
    venv/bin/python cloud_training/scripts/build_selfcontained_notebook.py
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_NB = ROOT / "cloud_training" / "notebooks" / "defense_prep_training.ipynb"


def script_body(rel: str) -> str:
    src = (ROOT / rel).read_text()
    marker = 'if __name__ == "__main__":'
    idx = src.find(marker)
    return src if idx == -1 else src[:idx].rstrip() + "\n"


def code_cell(source: str) -> dict:
    lines = source.splitlines()
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [l + "\n" for l in lines],
    }


def md_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [l + "\n" for l in source.splitlines()],
    }


def build() -> list[dict]:
    data_cell = '''import shutil
from pathlib import Path

# --- locate the uploaded data (attached as the 'logiscan-data' dataset) ---
TARGETS = ["stage1_splits.json", "unified_training_data_v1.3.json"]
Path("data").mkdir(exist_ok=True)
missing = []
for name in TARGETS:
    dest = Path("data") / name
    if dest.exists():
        print(f"found local: data/{name}")
        continue
    hits = list(Path("/kaggle/input").rglob(name))
    if hits:
        shutil.copy(hits[0], dest)
        print(f"copied from input: {hits[0]} -> data/{name}")
    else:
        missing.append(name)
if missing:
    raise SystemExit(
        "!! missing data files: "
        + ", ".join(missing)
        + "\\nattach the 'logiscan-data' dataset (2 JSONs) or put them in ./data"
    )

# --- single place to tweak training knobs ---
EPOCHS_STAGE1 = 6          # stage 1 gatekeeper epochs (best-val-F1 checkpointing)
SEEDS_STAGE3 = [42, 2024, 7]
BATCH_STAGE1 = 32          # per-GPU (loader auto x2 on T4x2)
BATCH_STAGE3 = 16          # per-GPU (loader auto x2 on T4x2)'''

    stage1_code = script_body("cloud_training/scripts/train_stage1_v13.py")
    stage1_b64 = base64.b64encode(stage1_code.encode()).decode()
    stage1_def_cell = f'''import argparse, base64

_STAGE1_SRC = base64.b64decode("{stage1_b64}").decode()
_NS1 = {{}}
exec(_STAGE1_SRC, _NS1)
print("stage 1 code loaded:", _NS1["train"].__name__)'''

    stage1_run_cell = '''args = argparse.Namespace(
    data="data/stage1_splits.json",
    output_dir="models/stage1_v13_classifier",
    base_model="distilbert-base-uncased",
    epochs=EPOCHS_STAGE1,
    batch_size=BATCH_STAGE1,
    lr=3e-5,
    seed=42,
    max_length=512,
    export_onnx=False,
)
_NS1["train"](args)'''

    sanity_cell = '''import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

m = AutoModelForSequenceClassification.from_pretrained("models/stage1_v13_classifier").to("cuda")
t = AutoTokenizer.from_pretrained("models/stage1_v13_classifier")
for s in ["Therefore, all humans are mortal.", "Click the blue button to submit.", "Physics is the fundamental natural science that studies matter."]:
    inp = t(s, return_tensors="pt", truncation=True, max_length=512).to("cuda")
    with torch.no_grad():
        p = torch.softmax(m(**inp).logits, dim=-1)[0][1].item()
    print(f"salience={p:.3f}  |  {s[:50]}")'''

    stage3_code = script_body("cloud_training/scripts/train_stage3_v13.py")
    stage3_b64 = base64.b64encode(stage3_code.encode()).decode()
    stage3_def_cell = f'''import argparse, base64

_STAGE3_SRC = base64.b64decode("{stage3_b64}").decode()
_NS3 = {{}}
exec(_STAGE3_SRC, _NS3)
print("stage 3 code loaded:", _NS3["train"].__name__)'''

    seed_cell = '''import json
from pathlib import Path

Path("cloud_training/results").mkdir(parents=True, exist_ok=True)
results = {"data": "data/unified_training_data_v1.3.json", "seeds": {}, "status": "running"}

for seed in SEEDS_STAGE3:
    args = argparse.Namespace(
        data="data/unified_training_data_v1.3.json",
        output_dir=f"models/seed_variation/seed_{seed}",
        base_model="microsoft/deberta-v3-small",
        epochs=6, batch_size=BATCH_STAGE3, lr=1e-5,
        seed=seed, max_length=256, val_split=0.1, export_onnx=False,
    )
    print(f"===== SEED {seed} =====")
    try:
        f1 = _NS3["train"](args)
        results["seeds"][str(seed)] = round(float(f1), 4)
        print(f"Seed {seed}: best val macro F1 = {f1:.4f}")
    except Exception as e:
        results["seeds"][str(seed)] = f"ERROR: {e}"
        print(f"Seed {seed} FAILED: {e}")
    # incremental write so a partial run still leaves a results file
    with open("cloud_training/results/seed_variation.json", "w") as f:
        json.dump(results, f, indent=2)

f1s = [v for v in results["seeds"].values() if isinstance(v, (int, float))]
if len(f1s) == len(SEEDS_STAGE3):
    import statistics
    results["macro_f1_mean"] = round(statistics.mean(f1s), 4)
    results["macro_f1_std"] = round(statistics.stdev(f1s), 4)
    results["status"] = "complete"
    print(f"\\nMean macro F1: {results['macro_f1_mean']:.4f} +/- {results['macro_f1_std']:.4f}")
else:
    results["status"] = "partial"
    print("\\nSome seeds failed - partial results saved. Check the errors above.")

with open("cloud_training/results/seed_variation.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved cloud_training/results/seed_variation.json")'''

    results_cell = '''import json, os, zipfile

print("--- seed variation results ---")
if os.path.exists("cloud_training/results/seed_variation.json"):
    with open("cloud_training/results/seed_variation.json") as f:
        print(json.dumps(json.load(f), indent=2))
else:
    print("!! seed_variation.json missing - the seed-variation cell above did not complete.")

if not os.path.exists("models/stage1_v13_classifier.zip") and os.path.isdir("models/stage1_v13_classifier"):
    with zipfile.ZipFile("models/stage1_v13_classifier.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk("models/stage1_v13_classifier"):
            for fn in files:
                fp = os.path.join(root, fn)
                z.write(fp, os.path.relpath(fp, "models"))
    print("\\nZipped models/stage1_v13_classifier.zip")

print("\\nOutputs ready for download:")
for f in ["models/stage1_v13_classifier.zip", "cloud_training/results/seed_variation.json"]:
    print(" -", f, f"({os.path.getsize(f)/1e6:.1f} MB)" if os.path.exists(f) else "(MISSING)")'''

    intro_md = """# LogiScan Defense-Prep Training Run — scripts embedded, data from input

The two TRAINING SCRIPTS are embedded in this notebook (no script uploads needed).
The DATA is uploaded by you: create a private dataset **`logiscan-data`** containing
the 2 JSON files (`stage1_splits.json` and `unified_training_data_v1.3.json` — at
the root or inside a `data/` subfolder; the cell below finds them anywhere under
`/kaggle/input`). Attach the dataset, select the **T4x2** accelerator, enable
**Internet**, run all cells.

Jobs:
1. Stage 1 gatekeeper retrain (DistilBERT, replaces the degenerate stage1_v12)
2. Stage 3 train/test split variation (seeds 42/2024/7) — answers the
   "train/test split variation" supervisor question with mean +/- std.

Notes:
- Both training loops use nn.DataParallel: the batch-size constants are
  PER-GPU; the loader batch auto-scales x2 on T4x2.
- Stage 1 saves best-val-F1 checkpoint; tune `EPOCHS_STAGE1` / `SEEDS_STAGE3`
  in the data cell if desired.
- Expected wall time on T4x2: stage 1 ~10-20 min, 3x stage 3 ~1.5-2.5 h.
  Kaggle sessions allow 12 h — let it run.

After the run, download (from the last cell):
- `models/stage1_v13_classifier.zip` -> unzip into repo `models/`, set
  `STAGE1_MODEL_PATH=./models/stage1_v13_classifier` in `.env`
- `cloud_training/results/seed_variation.json` -> paste mean +/- std into
  `docs/slides/09-validation-results.md` (two placeholder cells)"""

    return [
        md_cell(intro_md),
        md_cell("## 0. Environment setup"),
        code_cell(
            "!pip install -q transformers scikit-learn tqdm accelerate onnxscript pandas numpy\n"
            "import torch\n"
            "print('torch', torch.__version__, '| cuda:', torch.cuda.is_available())\n"
            "print('GPUs visible:', torch.cuda.device_count())\n"
            "for i in range(torch.cuda.device_count()):\n"
            "    print(f'  [{i}]', torch.cuda.get_device_name(i))\n"
            "assert torch.cuda.device_count() >= 1, 'no GPU allocated - set accelerator to T4x2'"
        ),
        md_cell("## 1. Data from input + training knobs"),
        code_cell(data_cell),
        md_cell("## 2. Stage 1 gatekeeper retrain"),
        code_cell(stage1_def_cell),
        code_cell(stage1_run_cell),
        code_cell(sanity_cell),
        md_cell("## 3. Stage 3 seed variation (3 runs)"),
        code_cell(stage3_def_cell),
        code_cell(seed_cell),
        md_cell("## 4. Results & download"),
        code_cell(results_cell),
    ]


def main() -> None:
    cells = build()
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    OUT_NB.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_NB, "w") as f:
        json.dump(nb, f, indent=1)
    print(f"Notebook written: {OUT_NB} ({OUT_NB.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
