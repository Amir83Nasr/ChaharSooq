"""Advisory-lock behavior — no PostgreSQL server required.

PostgreSQL calls and lock timing are mocked; the SQLite development path is the
only real connection used here.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Connection

import app.core.migration_lock as lock_module
from app.core.migration_lock import (
    MIGRATION_LOCK_KEY,
    MigrationLockError,
    MigrationLockTimeoutError,
    migration_lock,
)

pytestmark = pytest.mark.usefixtures("isolated_settings")


def _fake_connection(
    dialect: str,
    try_results: list[bool],
) -> tuple[MagicMock, list[tuple[str, dict[str, Any] | None]]]:
    connection = MagicMock()
    connection.dialect.name = dialect
    executed: list[tuple[str, dict[str, Any] | None]] = []

    def execute(statement: object, parameters: dict[str, Any] | None = None) -> MagicMock:
        sql = str(statement)
        executed.append((sql, parameters))
        result = MagicMock()
        if "pg_try_advisory_lock" in sql:
            result.scalar.return_value = try_results.pop(0)
        elif "pg_advisory_unlock" in sql:
            result.scalar.return_value = True
        else:  # pragma: no cover — tests only issue the two lock statements
            result.scalar.return_value = None
        return result

    connection.execute.side_effect = execute
    return connection, executed


def _no_sleep(_seconds: float) -> None:
    return None


def test_lock_key_is_fixed_and_documented() -> None:
    assert MIGRATION_LOCK_KEY == int.from_bytes(b"charsooq", "big")
    assert 0 <= MIGRATION_LOCK_KEY < 2**63


def test_lock_is_acquired_and_released_on_success() -> None:
    connection, executed = _fake_connection("postgresql", [True])

    with migration_lock(cast(Connection, connection), timeout_seconds=0):
        pass

    statements = [sql for sql, _ in executed]
    assert any("pg_try_advisory_lock" in sql for sql in statements)
    assert any("pg_advisory_unlock" in sql for sql in statements)
    assert executed[-1][1] == {"key": MIGRATION_LOCK_KEY}


def test_lock_is_released_after_an_exception() -> None:
    connection, executed = _fake_connection("postgresql", [True])

    with pytest.raises(RuntimeError, match="migration broke"):
        with migration_lock(cast(Connection, connection), timeout_seconds=0):
            raise RuntimeError("migration broke")

    assert any("pg_advisory_unlock" in sql for sql, _ in executed)


def test_lock_release_failure_does_not_mask_migration_failure() -> None:
    connection, _ = _fake_connection("postgresql", [True])

    def execute(statement: object, parameters: dict[str, Any] | None = None) -> MagicMock:
        if "pg_advisory_unlock" in str(statement):
            raise RuntimeError("connection lost during unlock")
        result = MagicMock()
        result.scalar.return_value = True
        return result

    connection.execute.side_effect = execute

    with pytest.raises(RuntimeError, match="migration broke"):
        with migration_lock(cast(Connection, connection), timeout_seconds=0):
            raise RuntimeError("migration broke")


def test_lock_waits_until_available(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, executed = _fake_connection("postgresql", [False, True])
    monkeypatch.setattr(lock_module.time, "sleep", _no_sleep)

    with migration_lock(cast(Connection, connection), timeout_seconds=5):
        pass

    statements = [sql for sql, _ in executed]
    assert sum("pg_try_advisory_lock" in sql for sql in statements) == 2
    assert sum("pg_advisory_unlock" in sql for sql in statements) == 1


def test_lock_timeout_is_clear_and_does_not_run_the_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection, executed = _fake_connection("postgresql", [False])
    monkeypatch.setattr(lock_module.time, "sleep", _no_sleep)
    entered = False

    with pytest.raises(MigrationLockTimeoutError, match="another migration process"):
        with migration_lock(cast(Connection, connection), timeout_seconds=0):
            entered = True

    assert entered is False
    statements = [sql for sql, _ in executed]
    assert sum("pg_try_advisory_lock" in sql for sql in statements) == 1
    assert not any("pg_advisory_unlock" in sql for sql in statements)


def test_sqlite_development_keeps_current_behavior() -> None:
    connection, executed = _fake_connection("sqlite", [])

    with migration_lock(cast(Connection, connection), timeout_seconds=0):
        pass

    assert executed == []


def test_production_refuses_a_non_postgresql_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    connection, executed = _fake_connection("sqlite", [])

    with pytest.raises(MigrationLockError, match="require PostgreSQL"):
        with migration_lock(cast(Connection, connection), timeout_seconds=0):
            pass

    assert executed == []
