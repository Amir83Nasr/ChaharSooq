"""Explicit owner bootstrap CLI — no create_all, idempotent, schema-aware."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import scripts.bootstrap_owner as bootstrap_script
import scripts.common as common_script
from app.core.config import get_database_settings, get_settings
from app.core.database import Base, get_engine, reset_engine
from app.core.security import verify_password
from app.models import Admin
from app.models.auth import ROLE_OWNER

pytestmark = pytest.mark.usefixtures("isolated_settings")

OWNER_PASSWORD = "cli-owner-pass"


def _clear_caches() -> None:
    get_database_settings.cache_clear()
    get_settings.cache_clear()


@pytest.fixture()
def owner_database(
    isolated_settings: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[Path]:
    database = tmp_path / "owner.db"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("OWNER_USERNAME", "cli-owner")
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)
    _clear_caches()
    reset_engine()
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    engine.dispose()
    try:
        yield database
    finally:
        reset_engine()
        _clear_caches()


def _owner_rows() -> list[Admin]:
    with Session(get_engine()) as session:
        return list(session.scalars(select(Admin).where(Admin.role == ROLE_OWNER)))


def test_cli_creates_the_owner_without_create_all(
    owner_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden_create_all(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("owner bootstrap must never create tables")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden_create_all)

    bootstrap_script.main()

    owners = _owner_rows()
    assert len(owners) == 1
    assert owners[0].username == "cli-owner"
    assert verify_password(owners[0].password_hash, OWNER_PASSWORD)
    assert "cli-owner" in capsys.readouterr().out


def test_cli_is_idempotent(owner_database: Path) -> None:
    bootstrap_script.main()
    first = _owner_rows()
    assert len(first) == 1

    bootstrap_script.main()
    second = _owner_rows()

    assert len(second) == 1
    assert second[0].id == first[0].id
    assert second[0].username == first[0].username
    assert verify_password(second[0].password_hash, OWNER_PASSWORD)


def test_cli_requires_a_migrated_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty.db'}")
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)
    _clear_caches()
    reset_engine()

    with pytest.raises(SystemExit) as exc:
        bootstrap_script.main()

    assert exc.value.code == 1
    assert "run migrations" in capsys.readouterr().err
    reset_engine()


def test_cli_refuses_the_test_environment(
    owner_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    _clear_caches()

    with pytest.raises(SystemExit) as exc:
        bootstrap_script.main()

    assert exc.value.code == 1
    assert "APP_ENV=test" in capsys.readouterr().err


def test_cli_requires_an_explicit_deployment_identity(
    owner_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)

    def forbidden_engine() -> None:
        raise AssertionError("the identity guard must fail before the database")

    monkeypatch.setattr(bootstrap_script, "get_engine", forbidden_engine)

    with pytest.raises(SystemExit) as exc:
        bootstrap_script.main()

    assert exc.value.code == 1
    assert "DEPLOYMENT_ENV" in capsys.readouterr().err


def test_cli_requires_owner_password(
    owner_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OWNER_PASSWORD", raising=False)
    _clear_caches()

    with pytest.raises(SystemExit) as exc:
        bootstrap_script.main()

    assert exc.value.code == 1
    assert "OWNER_PASSWORD" in capsys.readouterr().err


def test_cli_is_the_explicit_production_path(
    owner_database: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production identity passes configuration; the database engine is injected.

    A real Production run uses PostgreSQL. This test still never opens one: it
    keeps a valid remote PostgreSQL URL for configuration validation and binds
    the CLI and session helper to the temporary SQLite file.
    """
    sqlite_engine = create_engine(f"sqlite:///{owner_database}")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:test@db.invalid/charsooq")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    _clear_caches()
    monkeypatch.setattr(bootstrap_script, "get_engine", lambda: sqlite_engine)
    monkeypatch.setattr(common_script, "get_engine", lambda: sqlite_engine)

    bootstrap_script.main()

    with Session(sqlite_engine) as session:
        owners = list(session.scalars(select(Admin).where(Admin.role == ROLE_OWNER)))
    sqlite_engine.dispose()

    assert len(owners) == 1
    assert owners[0].username == "cli-owner"


def test_cli_refuses_production_with_a_sqlite_database(
    owner_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    _clear_caches()

    def forbidden_engine() -> None:
        raise AssertionError("configuration must fail before the database engine")

    monkeypatch.setattr(bootstrap_script, "get_engine", forbidden_engine)

    with pytest.raises(SystemExit) as exc:
        bootstrap_script.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "PostgreSQL" in err
    assert "sqlite" not in err.lower()


def test_cli_configuration_error_does_not_leak_secret_values(
    owner_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://app:database-secret@db.invalid/charsooq"
    )
    monkeypatch.setenv("SESSION_SECRET", "leaky-session-secret")
    _clear_caches()

    with pytest.raises(SystemExit) as exc:
        bootstrap_script.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "SESSION_SECRET" in err
    assert "leaky-session-secret" not in err
    assert "database-secret" not in err
    assert "postgresql" not in err
