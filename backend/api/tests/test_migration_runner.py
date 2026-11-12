"""Migration runner and CLI — shared connection, exit codes, safe output.

All database objects here are mocks or temporary files. No PostgreSQL server and
no real environment database is used.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

import app.core.migrations as migrations_module
import scripts.migrate as migrate_script
from app.core.config import Settings, get_database_settings, get_settings
from app.core.migration_lock import MigrationLockTimeoutError

pytestmark = pytest.mark.usefixtures("isolated_settings")

DATABASE_URL = "postgresql+psycopg://app:super-secret@db.invalid/charsooq"


def _fake_connection() -> tuple[MagicMock, list[str]]:
    connection = MagicMock()
    connection.dialect.name = "postgresql"
    executed: list[str] = []

    def execute(statement: object, parameters: dict[str, Any] | None = None) -> MagicMock:
        executed.append(str(statement))
        result = MagicMock()
        result.scalar.return_value = True
        return result

    connection.execute.side_effect = execute
    return connection, executed


def _fake_engine(connection: MagicMock) -> MagicMock:
    engine = MagicMock()
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = False
    engine.connect.return_value = context_manager
    return engine


def _no_upgrade(_config: object, _revision: str) -> None:
    return None


def _use_fake_database(
    monkeypatch: pytest.MonkeyPatch,
    *,
    connection: MagicMock,
    engine: MagicMock,
) -> None:
    settings = SimpleNamespace(
        database_url=DATABASE_URL,
        migration_lock_timeout_seconds=0,
    )
    monkeypatch.setattr(migrations_module, "get_database_settings", lambda: settings)

    def use_engine(_url: str) -> MagicMock:
        return engine

    monkeypatch.setattr(migrations_module, "_build_migration_engine", use_engine)


def test_runner_passes_the_locked_connection_to_alembic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection, executed = _fake_connection()
    engine = _fake_engine(connection)
    _use_fake_database(monkeypatch, connection=connection, engine=engine)
    captured: dict[str, object] = {}

    def fake_upgrade(config: object, revision: str) -> None:
        captured["config"] = config
        captured["revision"] = revision

    monkeypatch.setattr("alembic.command.upgrade", fake_upgrade)

    migrations_module.apply_migrations()

    config = cast(Any, captured["config"])
    assert config.attributes["connection"] is connection
    assert captured["revision"] == "head"
    assert any("pg_try_advisory_lock" in sql for sql in executed)
    assert any("pg_advisory_unlock" in sql for sql in executed)
    engine.dispose.assert_called_once()


def test_runner_releases_lock_and_closes_engine_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection, executed = _fake_connection()
    engine = _fake_engine(connection)
    _use_fake_database(monkeypatch, connection=connection, engine=engine)

    def failing_upgrade(_config: object, _revision: str) -> None:
        raise RuntimeError("migration failed")

    monkeypatch.setattr("alembic.command.upgrade", failing_upgrade)

    with pytest.raises(RuntimeError, match="migration failed"):
        migrations_module.apply_migrations()

    assert any("pg_advisory_unlock" in sql for sql in executed)
    engine.dispose.assert_called_once()


def test_runner_uses_database_settings_only(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, _ = _fake_connection()
    engine = _fake_engine(connection)
    used_urls: list[str] = []
    settings = SimpleNamespace(
        database_url=DATABASE_URL,
        migration_lock_timeout_seconds=0,
    )

    monkeypatch.setattr(migrations_module, "get_database_settings", lambda: settings)

    def build_engine(url: str) -> MagicMock:
        used_urls.append(url)
        return engine

    monkeypatch.setattr(migrations_module, "_build_migration_engine", build_engine)
    monkeypatch.setattr("alembic.command.upgrade", _no_upgrade)

    def forbidden_get_settings() -> None:
        raise AssertionError("the runner must not instantiate full application Settings")

    monkeypatch.setattr("app.core.config.get_settings", forbidden_get_settings)

    migrations_module.apply_migrations()

    assert used_urls == [DATABASE_URL]


def test_runner_never_calls_create_all(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.database import Base

    connection, _ = _fake_connection()
    engine = _fake_engine(connection)
    _use_fake_database(monkeypatch, connection=connection, engine=engine)
    monkeypatch.setattr("alembic.command.upgrade", _no_upgrade)

    def forbidden_create_all(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("migrations must never call create_all")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden_create_all)

    migrations_module.apply_migrations()


def test_startup_wrapper_skips_only_the_test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(migrations_module, "apply_migrations", lambda: calls.append("run"))
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(app_env="test"),
    )

    migrations_module.upgrade_to_head()
    assert calls == []

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(app_env="staging"),
    )
    migrations_module.upgrade_to_head()
    assert calls == ["run"]


def test_redact_migration_error_hides_url_and_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    get_database_settings.cache_clear()

    message = f"could not connect to {DATABASE_URL} with password super-secret"
    redacted = migrations_module.redact_migration_error(message)

    assert DATABASE_URL not in redacted
    assert "super-secret" not in redacted
    assert "<database-url>" in redacted
    assert "<redacted>" in redacted


def test_safe_error_message_omits_pydantic_input_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("SESSION_SECRET", "leaky-session-secret")
    monkeypatch.setenv("OWNER_PASSWORD", "owner-pass")
    get_database_settings.cache_clear()
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc:
        Settings()

    message = migrations_module.safe_error_message(exc.value)

    assert "SESSION_SECRET" in message
    assert "leaky-session-secret" not in message


# ── CLI ──────────────────────────────────────────────────────


def test_cli_success_prints_no_database_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setattr(migrate_script, "apply_migrations", lambda: None)

    migrate_script.main()

    captured = capsys.readouterr()
    assert "at head" in captured.out
    assert captured.err == ""
    assert DATABASE_URL not in captured.out + captured.err


def test_cli_requires_an_explicit_deployment_identity(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
    called = False

    def apply() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(migrate_script, "apply_migrations", apply)

    with pytest.raises(SystemExit) as exc:
        migrate_script.main()

    assert exc.value.code == 1
    assert called is False
    assert "DEPLOYMENT_ENV" in capsys.readouterr().err


def test_cli_timeout_exits_non_zero_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")

    def timeout() -> None:
        raise MigrationLockTimeoutError("timed out waiting for the advisory lock")

    monkeypatch.setattr(migrate_script, "apply_migrations", timeout)

    with pytest.raises(SystemExit) as exc:
        migrate_script.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "timed out" in err
    assert "migrate:" in err


def test_cli_failure_exits_non_zero_without_leaking_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    get_database_settings.cache_clear()

    def failure() -> None:
        raise RuntimeError(f"connection to {DATABASE_URL} failed; password super-secret")

    monkeypatch.setattr(migrate_script, "apply_migrations", failure)

    with pytest.raises(SystemExit) as exc:
        migrate_script.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "migration failed" in err
    assert DATABASE_URL not in err
    assert "super-secret" not in err


def test_cli_does_not_require_full_application_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setattr(migrate_script, "apply_migrations", lambda: None)
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: (_ for _ in ()).throw(AssertionError("full Settings must not load")),
    )

    migrate_script.main()
