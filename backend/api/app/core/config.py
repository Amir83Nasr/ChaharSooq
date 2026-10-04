from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env.local", ".env"), extra="ignore")

    app_env: str = Field(default="development")
    database_url: str = Field(
        default="postgresql+psycopg://charsooq:charsooq@localhost:5433/charsooq"
    )
    session_secret: str = Field(default="dev-only-secret-change-me-min-32-chars")
    session_cookie_name: str = Field(default="charsooq_session")
    session_ttl_hours: int = Field(default=12)
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
