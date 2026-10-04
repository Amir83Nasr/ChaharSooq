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


@lru_cache
def get_settings() -> Settings:
    return Settings()
