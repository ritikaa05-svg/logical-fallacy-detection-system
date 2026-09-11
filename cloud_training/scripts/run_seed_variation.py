"""Train/test split variation study (run on Kaggle, T4/P100 GPU).

Re-trains the Stage 3 v1.3 classifier under multiple train/val split seeds and
reports the spread of val macro F1. Answers the supervisor's
"train/test split variation" question with mean +/- std instead of a single
seed-42 point estimate.

Usage (Kaggle notebook cell):
    import sys; sys.path.insert(0, "/kaggle/working")
    !python cloud_training/scripts/run_seed_variation.py --seeds 42 2024 7

Output: cloud_training/results/seed_variation.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_stage3_v13 import train  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = ROOT / "cloud_training" / "results"


def build_args(seed: int, data_path: Path, base_out: Path) -> argparse.Namespace:
    return argparse.Namespace(
        data=str(data_path),
        output_dir=str(base_out / f"seed_{seed}"),
        base_model="microsoft/deberta-v3-small",
        epochs=6,
        batch_size=16,
        lr=1e-5,
        seed=seed,
        max_length=256,
        val_split=0.1,
        export_onnx=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 2024, 7])
    parser.add_argument(
        "--data",
        default=str(ROOT / "data" / "unified_training_data_v1.3.json"),
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    base_out = Path(args.data).parent.parent / "models" / "seed_variation"
    data_path = Path(args.data)

    results = {"data": args.data, "seeds": {}, "macro_f1_mean": None, "macro_f1_std": None}
    for seed in args.seeds:
        print(f"\n===== SEED {seed} =====")
        best_f1 = train(build_args(seed, data_path, base_out))
        results["seeds"][str(seed)] = round(float(best_f1), 4)
        print(f"Seed {seed}: best val macro F1 = {best_f1:.4f}")

    f1s = np.array(list(results["seeds"].values()))
    results["macro_f1_mean"] = round(float(f1s.mean()), 4)
    results["macro_f1_std"] = round(float(f1s.std()), 4)

    out_file = RESULTS_DIR / "seed_variation.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nMean macro F1: {results['macro_f1_mean']:.4f} ± {results['macro_f1_std']:.4f}")
    print(f"Saved {out_file}")


if __name__ == "__main__":
    main()
