"""Generate the class-distribution (imbalance) chart for the defense slides.

Reads `data/unified_training_data_v1.3.json`, counts labeled samples per
fallacy class, and renders a horizontal bar chart to
`docs/slides/assets/class_distribution.png`.

Usage:
    venv/bin/python scripts/plot_class_distribution.py
"""
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "unified_training_data_v1.3.json"
OUT = ROOT / "docs" / "slides" / "assets" / "class_distribution.png"

COARSE_COLORS = {
    "Non-Fallacious": "#2e8b57",
    "Formal": "#1f77b4",
    "Relevance": "#ff7f0e",
    "Presumption": "#9467bd",
    "Ambiguity": "#8c564b",
}

FORMAL_RESCUED = {
    "undistributed_middle",
    "illicit_major",
    "illicit_minor",
    "exclusive_premises",
    "existential_fallacy",
}


def coarse_of(label: str) -> str:
    if label in {"factual_statement", "valid_reasoning"}:
        return "Non-Fallacious"
    if label in {
        "affirming_consequent",
        "denying_antecedent",
        "undistributed_middle",
        "illicit_major",
        "illicit_minor",
        "exclusive_premises",
        "existential_fallacy",
    }:
        return "Formal"
    if label in {
        "ad_hominem",
        "straw_man",
        "red_herring",
        "tu_quoque",
        "tu_quoque_contextual",
        "appeal_to_authority",
        "appeal_to_emotion",
        "bandwagon",
        "moving_goalposts",
    }:
        return "Relevance"
    if label == "equivocation":
        return "Ambiguity"
    return "Presumption"


def main() -> None:
    with open(DATA) as f:
        records = json.load(f)
    labeled = [r for r in records if "fallacy" in r]
    counts = Counter(r["fallacy"] for r in labeled)

    labels = sorted(counts, key=lambda k: counts[k])
    values = [counts[k] for k in labels]
    colors = [COARSE_COLORS[coarse_of(k)] for k in labels]

    fig, ax = plt.subplots(figsize=(11, 9))
    bars = ax.barh(labels, values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xscale("log")
    ax.set_xlabel("Samples per class (log scale)", fontsize=12)
    ax.set_title(
        "Class Distribution — 29 Fallacy Types (Dataset v1.3, n=16,942)\n"
        "max:min imbalance = 29.9:1",
        fontsize=13,
    )

    for bar, label, value in zip(bars, labels, values):
        if label in FORMAL_RESCUED:
            ax.annotate(
                f"{value}  (rescued)",
                xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=9,
                fontweight="bold",
                color="#1f77b4",
            )
        elif value < 200:
            ax.annotate(
                str(value),
                xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=8,
            )

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.grid(axis="x", alpha=0.3)
    ax.axvline(500, color="red", linestyle="--", linewidth=1, alpha=0.6)
    ax.text(500, len(labels) - 0.3, " 500 (rescue target)", color="red", fontsize=9)

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=c, label=k)
        for k, c in COARSE_COLORS.items()
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=10)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
