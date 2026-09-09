# Configuration (Environment variables)

Configure these in `.env` (or `.env.staging` / `.env.production` for environment-specific configs). The system loads them in order, with later files overriding earlier ones.

> **See also**: `backend/app/config.py` for the authoritative schema with validators and defaults.

## Application

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LOGISCAN_VERSION` | `1.1.0-robust-xai` | Override the app version reported in API responses |
| `LOGISCAN_ENV` | `development` | Deployment environment: `development`, `staging`, or `production`. Controls config validation strictness and RL training mode. |
| `DEBUG` | `false` | Enable verbose debug logging |
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

## Model Paths

| Variable | Default | Description |
| :--- | :--- | :--- |
| `STAGE1_MODEL_PATH` | `./models/stage1_v13_classifier` | Path to Stage 1 DistilBERT gatekeeper (binary argument/non-argument). Production/staging override: `./models/stage1_v13_classifier` |
| `STAGE2_MODEL_PATH` | `./models/stage3_v13_classifier` | Path to the authoritative classifier — Stage-3 v1.3 DeBERTa-v3-small (single-head, 29 labels); coarse categories are derived from the fine-label distribution via `SHADOW_COARSE_MAP`. Production/staging override: `./models/stage3_v13_classifier` |
| `STAGE3_MODEL_PATH` | `./models/stage3_v13_classifier` | Path to the authoritative classifier — Stage-3 v1.3 DeBERTa-v3-small (single-head, 29 labels). Production/staging override: `./models/stage3_v13_classifier` |
| `STAGE4_SYNTHESIS_MODEL` | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | Synthesis model — HF repo ID or local path |
| `STAGE4_IS_LOCAL_PATH` | `false` | If `true`, `STAGE4_SYNTHESIS_MODEL` is a local filesystem path; if `false`, it's an HF repo ID |
| `ENABLE_SHADOW_MODE` | `false` | Run shadow model in parallel with production for comparison |
| `SHADOW_MODEL_PATH` | *(none)* | Optional path to a legacy model to run in shadow mode (requires `ENABLE_SHADOW_MODE=true`; ignored when unset) |

## Inference Thresholds

| Variable | Default | Range | Description |
| :--- | :--- | :--- | :--- |
| `SALIENCE_THRESHOLD` | `0.6` | 0.0–1.0 | Minimum Stage 1 salience to proceed with deeper analysis |
| `Z3_PARSING_CONFIDENCE_THRESHOLD` | `0.7` | 0.0–1.0 | Minimum SMT translation confidence to invoke Z3 |
| `Z3_TIMEOUT_MS` | `200` | 50–1000 | Z3 solver timeout in milliseconds |
| `MAX_INPUT_TOKENS` | `2000` | 256–4096 | Upper bound on input tokens per request |

## Hugging Face / API Fallback

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HUGGINGFACE_API_TOKEN` | *(none)* | Token for HF Inference API. Must start with `hf_`. **Only for development** — production must use vault-backed injection. |
| `HUGGINGFACE_API_URL` | `https://api-inference.huggingface.co/models` | Base URL for the HF Inference API |
| `HF_MODEL_ID` | *(none)* | HF model id for Inference API (`owner/repo`). `None` disables the API path. |
| `DISABLE_API_FALLBACK` | `false` | When `true`, forces local-only inference and disables any HF API fallback |

## Caching & Persistence

| Variable | Default | Description |
| :--- | :--- | :--- |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string for cache |
| `REDIS_CACHE_TTL_SECONDS` | `86400` | TTL for cached inference responses (24 h) |
| `DATABASE_URL` | *(asyncpg URL)* | Async PostgreSQL URL for debate logs and persistence. Must use `asyncpg` driver. |

## Security & Rate Limiting

| Variable | Default | Range | Description |
| :--- | :--- | :--- | :--- |
| `RATE_LIMIT_DEFAULT` | `60` | 10–600 | Default max requests per minute per IP |
| `RATE_LIMIT_AUTHENTICATED` | `120` | 10–600 | Max requests per minute for authenticated users |
| `ALLOWED_ORIGINS` | `["chrome-extension://*", "http://localhost:8501"]` | — | CORS allowed origins |

## Document Ingestion (Phase 6)

| Variable | Default | Range | Description |
| :--- | :--- | :--- | :--- |
| `MAX_FILE_SIZE_MB` | `20` | 1–100 | Maximum document file size in MB |
| `SUPPORTED_DOCUMENT_FORMATS` | `[".pdf", ".docx", ".txt"]` | — | Allowed file extensions for upload |

## Symbolic Traces (Phase 9.4)

| Variable | Default | Range | Description |
| :--- | :--- | :--- | :--- |
| `TRACE_STORAGE_DIR` | `data/traces` | — | Directory for persisted symbolic trace trees (JSON files) |
| `TRACE_MAX_FILES` | `100` | 10–10000 | Maximum number of trace files retained on disk (oldest pruned first) |

## RL Engine (Debate Agent)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DQN_MODEL_PATH` | `./models/dqn_debate_policy.pt` | Path to trained DQN model |
| `RL_EPSILON_START` | `0.9` | Initial exploration rate |
| `RL_EPSILON_END` | `0.05` | Minimum exploration rate |
| `RL_EPSILON_DECAY` | `0.995` | Epsilon decay per step |
| `RL_GAMMA` | `0.9` | Discount factor |
| `RL_REPLAY_BUFFER_SIZE` | `10000` | Replay buffer capacity |

## Environment Files

| File | Purpose |
| :--- | :--- |
| `.env` | Development defaults |
| `.env.staging` | Staging overrides |
| `.env.production` | Production overrides |

Notes
- For offline use, set `DISABLE_API_FALLBACK=true` in `.env` to force local-only inference.
- Do NOT commit secrets (`HUGGINGFACE_API_TOKEN`) into source control.
- `.env` files are excluded from git via `.gitignore`, but **not** excluded from Docker build context — ensure they are stripped before building images.
- In `production` or `staging` mode, the system requires `REDIS_URL`, `STAGE1_MODEL_PATH`, `STAGE2_MODEL_PATH`, and `STAGE3_MODEL_PATH` to be set or will raise `ConfigError` on startup.
- **Production model paths**: `models/stage3_v13_classifier` (DeBERTa-v3-small, single-head 29-label, ONNX) is the authoritative classifier used by both Stage 2 and Stage 3, alongside `models/stage1_v13_classifier` for the Stage 1 gatekeeper. The v1.3 model adds the five rescued formal classes (`undistributed_middle`, `illicit_major`, `illicit_minor`, `exclusive_premises`, `existential_fallacy`). The earlier `phase4_final_model` (24-label) was superseded; override via `.env` or `.env.production`.
