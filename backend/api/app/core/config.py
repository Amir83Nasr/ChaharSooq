import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env.local", ".env"), extra="ignore")

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
            "http://192.168.1.20:3000",
            "http://192.168.1.21:3000",
        ]
    )

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

    model_config = SettingsConfigDict(env_file=(".env.local", ".env"), extra="ignore")

    parsina_base_url: str = Field(default="")
    parsina_username: str = Field(default="")
    parsina_password: str = Field(default="")
    parsina_org_id: int | None = Field(default=None)
    parsina_year: int | None = Field(default=None)
    parsina_ware_id: int | None = Field(default=None, description="optional LoadByFilter Ware")
    parsina_sale_type_id: int | None = Field(default=None, description="optional Saletype")
    parsina_timeout_seconds: float = Field(default=15.0, gt=0)
    parsina_sync_interval_minutes: int = Field(default=15, ge=1)
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
