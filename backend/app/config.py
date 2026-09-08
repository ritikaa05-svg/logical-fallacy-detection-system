"""
LogiScan Central Configuration
Uses Pydantic Settings for environment variable management with strict validation.
"""

import os
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.staging", ".env.production"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, __context):
        if self.LOGISCAN_ENV in ("production", "staging"):
            required = ["REDIS_URL", "STAGE1_MODEL_PATH", "STAGE2_MODEL_PATH", "STAGE3_MODEL_PATH"]
            missing = [k for k in required if not getattr(self, k, None)]
            if missing:
                raise ConfigError(f"Missing required settings in {self.LOGISCAN_ENV}: {missing}")

    # --- Application ---
    APP_NAME: str = "LogiScan"
    APP_VERSION: str = Field(
        default="1.2.0-rc1",
        alias="LOGISCAN_VERSION",
        description="Application version (overridable via LOGISCAN_VERSION env var).",
    )
    DEBUG: bool = Field(default=False, description="Enable debug mode with verbose logging.")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1024, le=65535)

    # --- Model Paths ---
    STAGE1_MODEL_PATH: str = Field(
        default="./models/stage1_gatekeeper", description="Path to the Stage 1 DistilBERT gatekeeper model."
    )
    STAGE2_MODEL_PATH: str = Field(
        default="./models/stage3_v13_classifier",
        description="Path to the authoritative classifier (Stage-3 v1.3, 29-class DeBERTa-v3-small).",
    )
    STAGE3_MODEL_PATH: str = Field(
        default="./models/stage3_v13_classifier",
        description="Path to the authoritative classifier (Stage-3 v1.3, 29-class DeBERTa-v3-small).",
    )
    SHADOW_MODEL_PATH: str | None = Field(
        default=None, description="Path to the legacy model for shadow-mode comparison (optional)."
    )
    ENABLE_SHADOW_MODE: bool = Field(
        default=False, description="Run shadow model in parallel with production for comparison."
    )
    STAGE4_SYNTHESIS_MODEL: str = Field(
        default="HuggingFaceTB/SmolLM2-1.7B-Instruct",
        description="Hugging Face repo ID or local path for the synthesis model.",
    )
    STAGE4_IS_LOCAL_PATH: bool = Field(
        default=False,
        description="If True, STAGE4_SYNTHESIS_MODEL is treated as a local filesystem path. "
        "If False, it is treated as a Hugging Face repo ID for API inference.",
    )

    # --- Inference Thresholds ---
    SALIENCE_THRESHOLD: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Minimum Stage 1 salience score to proceed with analysis."
    )
    Z3_PARSING_CONFIDENCE_THRESHOLD: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum SMT translation confidence to invoke Z3 solver."
    )
    Z3_TIMEOUT_MS: int = Field(default=200, ge=50, le=1000, description="Z3 solver timeout in milliseconds.")

    # --- API Fallback ---
    HUGGINGFACE_API_TOKEN: str | None = Field(
        default=None, description="Hugging Face API token for serverless inference fallback."
    )
    HUGGINGFACE_API_URL: str = Field(
        default="https://api-inference.huggingface.co/models", description="Base URL for Hugging Face Inference API."
    )
    # Model identifier to use with the Hugging Face Inference API (e.g. 'owner/repo')
    HF_MODEL_ID: str | None = Field(
        default=None,
        description="Hugging Face model id to call via the Inference API (owner/repo). None disables the API path.",
    )

    DISABLE_API_FALLBACK: bool = Field(
        default=False,
        description="If True, skip HuggingFace API fallback entirely and use only local models, even on low-VRAM hardware.",
    )

    # --- Redis ---
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL for caching.")
    REDIS_CACHE_TTL_SECONDS: int = Field(
        default=86400, ge=3600, le=604800, description="Time-to-live for cached inference results (default: 24 hours)."
    )

    # --- PostgreSQL ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://logiscan:REPLACE_ME_IN_PRODUCTION@localhost:5432/logiscan",
        description="Async PostgreSQL connection URL for debate logs.",
    )

    # --- Security ---
    MAX_INPUT_TOKENS: int = Field(
        default=2000, ge=256, le=4096, description="Maximum allowed input tokens per request."
    )
    RATE_LIMIT_DEFAULT: int = Field(
        default=60, ge=10, le=600, description="Default maximum requests per minute per IP address."
    )
    RATE_LIMIT_AUTHENTICATED: int = Field(
        default=120, ge=10, le=600, description="Maximum requests per minute for authenticated users."
    )
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:8501"],
        description="CORS allowed exact origins (e.g. Streamlit).",
    )
    ALLOWED_ORIGIN_REGEX: str = Field(
        default=r"^(chrome-extension://[a-p]{32}|https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?)$",
        description=(
            "CORS allowed origin regex pattern. Covers any Chrome extension origin "
            "(chrome-extension://<32-char-id>) and localhost dev origins. "
            "Exact origins (ALLOWED_ORIGINS) take precedence."
        ),
    )

    # --- RL Engine ---
    DQN_MODEL_PATH: str = Field(
        default="./models/dqn_debate_policy.pt", description="Path to the trained DQN model for debate actions."
    )
    RL_EPSILON_START: float = Field(default=0.9, ge=0.0, le=1.0)
    RL_EPSILON_END: float = Field(default=0.05, ge=0.0, le=1.0)
    RL_EPSILON_DECAY: float = Field(default=0.995, ge=0.9, le=0.999)
    RL_GAMMA: float = Field(default=0.9, ge=0.8, le=0.99)
    RL_REPLAY_BUFFER_SIZE: int = Field(default=10000, ge=1000, le=100000)
    RL_POINT_CONF_FLOOR: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum top fine-label confidence before the debate agent asserts POINT_OUT_FALLACY. Matches the pipeline reranker boundary; below this the agent downgrades to ASK_SOCRATIC.",
    )
    LOGISCAN_ENV: Literal["development", "staging", "production"] = Field(
        default="development", description="Deployment environment for config loading and runtime behaviour."
    )

    # --- Phase 6: Document Ingestion ---
    MAX_FILE_SIZE_MB: int = Field(
        default=20, ge=1, le=100, description="Maximum allowed document file size in megabytes."
    )
    SUPPORTED_DOCUMENT_FORMATS: list[str] = Field(
        default=[".pdf", ".docx", ".txt"], description="Allowed document file extensions for the upload endpoint."
    )

    # --- Phase 9.4: Symbolic Traces ---
    TRACE_STORAGE_DIR: str = Field(
        default="data/traces", description="Directory for persisted symbolic trace trees (JSON files)."
    )
    TRACE_MAX_FILES: int = Field(
        default=100, ge=10, le=10000, description="Maximum number of trace files retained on disk."
    )

    @field_validator("HUGGINGFACE_API_TOKEN")
    @classmethod
    def validate_hf_token(cls, v, info):
        if v and v.startswith("hf_"):
            env = os.environ.get("LOGISCAN_ENV", "development")
            if env == "production":
                raise ValueError(
                    "HUGGINGFACE_API_TOKEN must not be a plain 'hf_' token in production. "
                    "Use a vault-backed secret injection instead."
                )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_db_url(cls, v):
        if "asyncpg" not in v:
            raise ValueError("DATABASE_URL must use asyncpg driver for async operations")
        return v


# Singleton settings instance
settings = Settings()
