# LogiScan — Logical Fallacy Detection Engine

A sovereign, resource-optimized system for detecting logical fallacies in natural language text using a neuro-symbolic pipeline.

## Index
* [Quick Start](#quick-start)
* [Architecture](#architecture)
* [Offline Usage](#offline-usage)
* [Windows Setup](#windows-setup)
* [Linux Setup](#linux-setup)
* [Documentation](#documentation)
* [API](#api)
* [Limitations](#limitations)
* [Requirements](#requirements)
* [License](#license)

## Architecture

LogiScan employs a hybrid neuro-symbolic approach to identify and verify reasoning errors.

```
Input Text
    │
    ▼
Stage 1: Gatekeeper (DistilBERT — ONNX or safetensors)
    │ Is this a logical claim? (Salience Filter)
    ▼
Stage 2: Coarse Classifier (DistilBERT — 6 coarse labels)
    │ Broad fallacy category (Formal, Informal x4, Non-Fallacious)
    ▼
Stage 3: Fine-Grained (RoBERTa — 29 fallacy labels)
    │ Specific fallacy type detection
    ▼
Stage 3: Formal Verification & Synthesis
    ├── Z3 SMT Solver (formal checks from SMT-LIBv2)
    └── Local SMT translator / LLM fallback (SmolLM2-1.7B-Instruct) or Hugging Face Inference API
    (configurable via HF_MODEL_ID; API fallback can be disabled with DISABLE_API_FALLBACK)
```

## Quick Start

**Linux/macOS:**
```bash
./run_native.sh
```

**Windows:**
```
run_native.bat
```

The script builds the React frontend automatically (`frontend/dist/`), then starts the FastAPI backend
which serves both the API and the SPA at `http://localhost:8000`.

Open `http://localhost:8000` in your browser to access the SPA dashboard with:
- **Analysis** — text input with fallacy highlighting, scan button, logic score, correction
- **Health** — logic score trend chart (Recharts) + 5 summary metrics
- **Status** — system health, device info, cache stats (auto-refresh 15s)
- **History** — past analyses saved to localStorage, sortable by score/timestamp
- **Debate** — slide-over chat panel with optimistic streaming, typing indicator (click "Debate" in nav)

A **Chrome extension** (`frontend/extension/`) is available — load it as an unpacked extension to analyze
selected text on any page via context menu or `Ctrl+Shift+L`. Results render in a toast with logic score,
fallacy tags, argument structure, Z3 status, degradation tier, and in-page span highlighting. The backend
URL is configurable from the popup (default `http://localhost:8000`, live health probe).

For production or team deployments, use Docker:
```bash
sudo docker compose -f deployment/docker-compose.yml up -d --build
```

If you need to force local-only inference in offline environments, set `DISABLE_API_FALLBACK=true` in your `.env`.

## Windows Setup

### Option 1: Docker (Recommended)
1. Install [Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)
2. Run `.\run_docker.ps1` or `run_docker.bat`.

### Option 2: WSL2
1. Install WSL: `wsl --install`
2. Run `./setup_models.sh` and then `./run_native.sh`.

### Option 3: Native Python + Frontend Build
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
cd frontend
npm install
npm run build
cd ..
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Linux Setup

### Option 1: Native Python (auto-builds frontend)
```bash
./setup_models.sh
./run_native.sh
```

### Option 2: Docker
```bash
sudo docker compose -f deployment/docker-compose.yml up -d --build
```

### Option 3: Manual Frontend Build
```bash
cd frontend
npm install
npm run build
cd ..
./run_native.sh
```

## Documentation

Technical documentation is available in the `docs/` directory:
- [Architecture](docs/ARCHITECTURE.md) — system overview, data flow, frontend components, Streamlit comparison
- [Roadmap](docs/ROADMAP.md) — phase planning, completed items, future work
- [Model Scorecard](docs/MODEL_SCORECARD.md)
- [Configuration](docs/CONFIGURATION.md)
- [Performance Audit](docs/PERFORMANCE_AUDIT.md)
- [Known Issues](docs/KNOWN_ISSUES.md)
- [UI Audit](docs/archive/UI_AUDIT.md) — Streamlit limitation analysis

## API

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "If it rains, the ground is wet. The ground is wet, therefore it rained."}'
```

## Limitations

- Optimized for English language arguments.
- Formal verification (Z3) requires the LLM to successfully translate natural language to SMT-LIBv2.
- CPU inference is supported but GPU (CUDA/MPS) is recommended for best latency.

## Requirements

- **Python:** 3.11+
- **RAM:** 8GB minimum (16GB recommended)
- **Disk:** ~5GB for models and dependencies
- **GPU (Optional):** NVIDIA (4GB+ VRAM) or Apple Silicon

## License

MIT
