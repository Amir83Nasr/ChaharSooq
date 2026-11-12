"""Alembic configuration isolation — MigrationSettings only, no full Settings.

These tests are offline: ``alembic upgrade --sql`` renders SQL without opening a
connection, and the URL-resolution helpers never create an engine.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

import app.core.config as config_module
import app.core.migrations as migration_module
from app.core.config import get_migration_settings

pytestmark = pytest.mark.usefixtures("isolated_settings")

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_DATABASE_URL = "postgresql+psycopg://env:test@db.invalid/env"
FILE_DATABASE_URL = "postgresql+psycopg://file:test@db.invalid/file"
ENV_MIGRATION_URL = "postgresql+psycopg://migrator:test@db.invalid/env"
FILE_MIGRATION_URL = "postgresql+psycopg://migrator:test@db.invalid/file"


def _alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def _write_secret(directory: Path, name: str, value: str) -> None:
    (directory / name).write_text(f"{value}\n", encoding="utf-8")


def test_migration_helper_falls_back_to_database_url_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"  {ENV_DATABASE_URL}  ")
    get_migration_settings.cache_clear()

    assert migration_module._database_url() == ENV_DATABASE_URL  # pyright: ignore[reportPrivateUsage]


def test_migration_helper_reads_migration_url_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", ENV_DATABASE_URL)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", f"  {ENV_MIGRATION_URL}  ")
    get_migration_settings.cache_clear()

    assert migration_module._database_url() == ENV_MIGRATION_URL  # pyright: ignore[reportPrivateUsage]


def test_migration_helper_reads_migration_url_from_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "migration_database_url", FILE_MIGRATION_URL)
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    get_migration_settings.cache_clear()

    assert migration_module._database_url() == FILE_MIGRATION_URL  # pyright: ignore[reportPrivateUsage]


def test_migration_helper_falls_back_to_database_url_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "database_url", FILE_DATABASE_URL)
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    get_migration_settings.cache_clear()

    assert migration_module._database_url() == FILE_DATABASE_URL  # pyright: ignore[reportPrivateUsage]


def test_offline_sql_generation_uses_migration_settings_not_full_settings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MIGRATION_DATABASE_URL", ENV_MIGRATION_URL)
    get_migration_settings.cache_clear()

    class ForbiddenSettings:
        def __new__(cls, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("Alembic must not instantiate the full Settings model")

    def forbidden_get_settings() -> None:
        raise AssertionError("Alembic must not call get_settings()")

    with monkeypatch.context() as forbidden:
        forbidden.setattr(config_module, "Settings", ForbiddenSettings)
        forbidden.setattr(config_module, "get_settings", forbidden_get_settings)
        command.upgrade(_alembic_config(), "head", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE TABLE alembic_version" in sql
    assert "CREATE TABLE products" in sql


def test_offline_migrations_require_the_migration_url_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", ENV_DATABASE_URL)
    get_migration_settings.cache_clear()

    with pytest.raises(ValidationError, match="MIGRATION_DATABASE_URL must be set explicitly"):
        command.upgrade(_alembic_config(), "head", sql=True)


def test_offline_migrations_accept_a_remote_migration_url_in_production(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("MIGRATION_DATABASE_URL", ENV_MIGRATION_URL)
    get_migration_settings.cache_clear()

    command.upgrade(_alembic_config(), "head", sql=True)

    assert "CREATE TABLE products" in capsys.readouterr().out


def test_online_migration_uses_the_provided_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A caller-supplied connection is used instead of a second engine.

    Only the initial revision runs here: SQLite cannot execute later
    ``ALTER CONSTRAINT`` revisions, and this test is about connection sharing,
    not SQLite migration parity.
    """
    database = tmp_path / "shared-connection.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_migration_settings.cache_clear()
    engine = create_engine(url)

    def forbidden_engine(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Alembic must use config.attributes['connection']")

    monkeypatch.setattr("sqlalchemy.engine_from_config", forbidden_engine)

    with engine.connect() as connection:
        cfg = _alembic_config()
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "0001_init")

    assert inspect(engine).has_table("alembic_version")
    assert inspect(engine).has_table("admins")
    engine.dispose()


def test_online_migration_commits_an_external_transaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The advisory-lock SELECT opens a transaction before Alembic runs.

    Alembic intentionally does not commit a transaction it did not start, so
    ``migrations/env.py`` commits it after the upgrade. Without that commit the
    connection close rolls every migration back.
    """
    database = tmp_path / "external-transaction.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_migration_settings.cache_clear()
    engine = create_engine(url)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        assert connection.in_transaction()
        cfg = _alembic_config()
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "0001_init")
        assert not connection.in_transaction()

    assert inspect(engine).has_table("alembic_version")
    assert inspect(engine).has_table("admins")
    engine.dispose()
