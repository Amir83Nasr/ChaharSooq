import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repository layout: backend/api/app/core/config.py → backend/api → repo root.
# Env files are resolved from this module, not the working directory, so the API,
# Alembic, and the seed scripts always read the same configuration.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[4]
# Shared root env (optional) is loaded first so per-app files can override it.
_ENV_FILES = (
    str(_REPO_ROOT / ".env.local"),
    str(_REPO_ROOT / ".env"),
    str(_BACKEND_DIR / ".env.local"),
    str(_BACKEND_DIR / ".env"),
)

# Only the development source reads this file; production uses Parsina.
_DEFAULT_PRODUCTS_CSV_PATH = _REPO_ROOT / "data" / "parsina.csv"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    app_env: str = Field(default="development")
    database_url: str = Field(
        default="postgresql+psycopg://charsooq:charsooq@localhost:5433/charsooq"
    )
    session_secret: str = Field(default="dev-only-secret-change-me-min-32-chars")
    session_cookie_name: str = Field(default="charsooq_session")
    session_ttl_hours: int = Field(default=12)
    session_samesite: Literal["lax", "none"] = Field(default="lax")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    # Development-only product catalog (app_env=development); ignored in production.
    products_csv_path: str = Field(default=str(_DEFAULT_PRODUCTS_CSV_PATH))
    # Production sync simulation: when set, APP_ENV=production syncs products
    # from this dev database instead of the live Parsina API, through the same
    # ProductSyncService path (button + scheduler behave identically).
    dev_database_url: str = Field(default="")
    competitor_request_interval_seconds: float = Field(default=5.0, ge=1, le=300)
    competitor_price_ttl_hours: int = Field(default=24, ge=1, le=720)

    @field_validator("database_url", mode="before")
    @classmethod
    def _strip_database_url(cls, value: object) -> object:
        # Pasted Neon URLs can carry trailing whitespace ("sslmode=require "),
        # which psycopg rejects. Strip before SQLAlchemy sees it.
        return value.strip() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        # ponytail: رشته env تکی؛ لیست کامل هنگام CORS_ORIGINS صریح.
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return parsed
            return [o.strip() for o in raw.split(",") if o.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


class ParsinaSettings(BaseSettings):
    """Parsina accounting API connection — secrets only via env, never logged."""

    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    parsina_base_url: str = Field(default="")
    parsina_username: str = Field(default="")
    parsina_password: str = Field(default="")
    parsina_org_id: int | None = Field(default=None)
    parsina_year: int | None = Field(default=None)
    parsina_ware_id: int | None = Field(default=None, description="optional LoadByFilter Ware")
    parsina_sale_type_id: int | None = Field(default=None, description="optional Saletype")
    parsina_timeout_seconds: float = Field(default=15.0, gt=0)
    parsina_sync_interval_minutes: int = Field(default=1440, ge=1)
    parsina_sync_enabled: bool = Field(default=True)

    @property
    def base_url(self) -> str:
        return self.parsina_base_url.strip().rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(
            self.base_url
            and self.parsina_username
            and self.parsina_password
            and self.parsina_org_id is not None
            and self.parsina_year is not None
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_parsina_settings() -> ParsinaSettings:
    return ParsinaSettings()
