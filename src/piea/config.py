"""Application settings loaded from environment variables.

All configuration is read at import time via pydantic-settings.
Environment variables take precedence over .env file values.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for PIEA.

    Every field maps to an environment variable of the same name (uppercased).
    Required fields (no default) will raise a startup error if absent.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Infrastructure ---
    database_url: str = "postgresql+asyncpg://piea:password@localhost:5432/piea"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    # --- API keys (required in production; defaults allow local dev without keys) ---
    hibp_api_key: str = ""
    google_cse_api_key: str = ""
    google_cse_engine_id: str = ""
    github_token: str = ""
    hunter_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    # --- Scan limits ---
    scan_max_depth: int = 3
    scan_timeout_seconds: int = 120
    scan_max_nodes: int = 500
    scan_rate_limit_per_hour: int = 10

    # --- Cache TTLs (seconds) ---
    cache_ttl_breach: int = 86400  # 24 hours
    cache_ttl_profile: int = 3600  # 1 hour

    # --- Application ---
    log_level: str = "INFO"
    environment: str = "development"

    @field_validator("scan_max_depth")
    @classmethod
    def depth_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("scan_max_depth must be >= 1")
        return v

    @field_validator("scan_timeout_seconds")
    @classmethod
    def timeout_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("scan_timeout_seconds must be >= 1")
        return v


# Module-level singleton — import this everywhere instead of re-instantiating.
settings = Settings()
