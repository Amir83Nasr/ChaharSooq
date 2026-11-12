"""Shared pytest fixtures — in-memory DB + seeded admin client."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import Base, get_engine, reset_engine
from app.core.rate_limit import reset_rate_limits
from app.core.security import hash_password
from app.main import create_app
from app.models import Admin

_ISOLATED_SETTINGS_ENV = frozenset(
    {
        "APP_ENV",
        "DEPLOYMENT_ENV",
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
        "SECRETS_DIR",
        "SESSION_SECRET",
        "SESSION_COOKIE_NAME",
        "SESSION_TTL_HOURS",
        "SESSION_SAMESITE",
        "OWNER_USERNAME",
        "OWNER_PASSWORD",
        "ADMIN_USER",
        "ADMIN_PASSWORD",
        "REDIS_URL",
        "CORS_ORIGINS",
        "PRODUCTS_CSV_PATH",
        "DEV_DATABASE_URL",
        "RUN_MIGRATIONS_ON_STARTUP",
        "RUN_OWNER_BOOTSTRAP_ON_STARTUP",
        "MIGRATION_LOCK_TIMEOUT_SECONDS",
    }
)


@pytest.fixture()
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hermetic settings: no real env files, secrets, or unrelated variables."""
    from app.core import config

    for name in _ISOLATED_SETTINGS_ENV:
        monkeypatch.delenv(name, raising=False)
    for name in list(os.environ):
        if name.startswith("PARSINA_") or name.startswith("COMPETITOR_"):
            monkeypatch.delenv(name, raising=False)
    for model in (
        config.SecretFileSettings,
        config.DatabaseSettings,
        config.MigrationSettings,
        config.ProvisioningSettings,
        config.Settings,
        config.ParsinaSettings,
    ):
        monkeypatch.setitem(model.model_config, "env_file", ())

    # Capture the originals: a test may monkeypatch the cached accessor itself.
    clear_database_settings = config.get_database_settings.cache_clear
    clear_settings = config.get_settings.cache_clear
    clear_parsina_settings = config.get_parsina_settings.cache_clear
    clear_database_settings()
    clear_settings()
    clear_parsina_settings()
    yield
    clear_database_settings()
    clear_settings()
    clear_parsina_settings()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    reset_engine()
    reset_rate_limits()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(
            Admin(
                username="root",
                password_hash=hash_password("root-pass-123"),
                role="owner",
            )
        )
        s.add(Admin(username="admin", password_hash=hash_password("secret123")))
        s.commit()
    with TestClient(create_app()) as c:
        yield c
