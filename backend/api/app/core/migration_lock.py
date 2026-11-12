"""Single-runner guard for Alembic migrations (PostgreSQL advisory lock).

Alembic itself is happy to run the same ``upgrade head`` from several
processes at once. Two API replicas or a one-shot job racing the API's lifespan
can then both try to create the same revision, which produces duplicate-key or
``relation already exists`` errors. A PostgreSQL **session-level** advisory lock
makes the whole Alembic run single-flight:

* the lock is acquired on the same connection Alembic uses;
* it is held for the complete migration, not only for one transaction;
* it is released explicitly in ``finally``, and closing the connection (or the
  process dying) makes PostgreSQL release it as a final safety net.

Session-level rather than transaction-level is deliberate: Alembic manages its
own transaction and may commit between revisions. A transaction-level lock
would disappear at the first commit and stop protecting the rest of the run.

For SQLite (Development tests and local workflows) the lock is a no-op. When
``DEPLOYMENT_ENV=production`` is explicit, a non-PostgreSQL dialect fails
closed instead of silently running without protection.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Connection, text

from app.core.deployment import is_production_deployment

log = logging.getLogger("charsooq.migrations")

#: Fixed advisory-lock key for ChaharSooq migrations.
#:
#: ``int.from_bytes(b"charsooq", "big")``: stable across processes, documented
#: here, and inside PostgreSQL's signed 64-bit advisory-lock range.
MIGRATION_LOCK_KEY = 0x63686172736F6F71  # ASCII "charsooq"

#: How often a blocked runner retries ``pg_try_advisory_lock``.
LOCK_POLL_INTERVAL_SECONDS = 0.25


class MigrationLockError(RuntimeError):
    """The migration lock cannot be used for this database."""


class MigrationLockTimeoutError(MigrationLockError):
    """Another process held the migration lock past the configured timeout."""


def _acquire(connection: Connection, timeout_seconds: float) -> None:
    """Wait for the session-level lock or raise a clear timeout error."""
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        held = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": MIGRATION_LOCK_KEY},
        ).scalar()
        if held:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MigrationLockTimeoutError(
                "timed out waiting for the ChaharSooq migration advisory lock "
                f"(key {MIGRATION_LOCK_KEY}) after {timeout_seconds:g}s; "
                "another migration process is still running"
            )
        time.sleep(min(LOCK_POLL_INTERVAL_SECONDS, remaining))


def _release(connection: Connection) -> None:
    """Release the session lock; closing the connection is the safety net."""
    try:
        released = connection.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": MIGRATION_LOCK_KEY},
        ).scalar()
    except Exception:  # noqa: BLE001 — never mask the migration's own failure
        # A broken connection is closed by the caller (NullPool), and
        # PostgreSQL releases session locks when the session ends.
        log.warning("could not release the migration advisory lock explicitly")
        return
    if not released:
        log.warning("migration advisory lock was not held at release time")


@contextmanager
def migration_lock(
    connection: Connection, *, timeout_seconds: float
) -> Generator[None, None, None]:
    """Hold the ChaharSooq migration lock for the duration of the block.

    The caller must run Alembic on ``connection``; the lock only protects the
    run when both use the same database session.
    """
    dialect = connection.dialect.name
    if dialect != "postgresql":
        if is_production_deployment():
            raise MigrationLockError(
                "Production migrations require PostgreSQL session advisory locks; "
                f"the configured database dialect is {dialect!r}"
            )
        # Development/test databases (including SQLite) keep the previous behavior.
        yield
        return

    _acquire(connection, timeout_seconds)
    try:
        yield
    finally:
        _release(connection)
