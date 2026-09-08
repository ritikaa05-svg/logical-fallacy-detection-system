#!/bin/bash
# Downloads pre-trained models for LogiScan
# Run once before starting the application

set -e

echo "==========================================="
echo "  LogiScan Model Downloader"
echo "==========================================="

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Install minimal dependencies
pip install -q transformers torch

python << 'PYEOF'
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from pathlib import Path

models = {
    "models/stage1_v12": ("distilbert-base-uncased", 2),
    "models/phase4_final_model": ("microsoft/deberta-v3-base", None),
}

for path_str, (model_name, num_labels) in models.items():
    p = Path(path_str)
    if (p / "config.json").exists():
        print(f"✅ {path_str} already exists")
        continue

    print(f"Downloading {model_name} → {path_str}...")
    p.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(model_name)
    mod = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=num_labels,
        ignore_mismatched_sizes=True
    )

    mod.save_pretrained(str(p))
    tok.save_pretrained(str(p))
    print(f"   Done. Classes: {mod.config.num_labels}")

print("\n✅ All models downloaded")
PYEOF

echo ""
echo "Models ready. Run ./run_native.sh to start LogiScan."
