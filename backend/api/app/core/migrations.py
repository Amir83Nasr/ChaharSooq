"""Database migrations and the single-runner guard.

The same migration path serves three entry points:

* the API lifespan (:func:`upgrade_to_head`, controlled by
  ``RUN_MIGRATIONS_ON_STARTUP``);
* the standalone CLI (``scripts/migrate.py``, :func:`apply_migrations`);
* a plain ``alembic upgrade head``, whose ``migrations/env.py`` acquires the
  same advisory lock when it opens its own connection.

Every run uses ``DatabaseSettings`` only, so migrating never requires
authentication secrets. On PostgreSQL the Alembic upgrade and the advisory lock
share one connection (see :mod:`app.core.migration_lock`). Production must run
on PostgreSQL and fails closed without lock support.

Skipped when ``APP_ENV=test`` for the lifespan only: tests manage their own
schema with ``Base.metadata.create_all`` (see tests/conftest.py). The explicit
CLI remains usable in tests with a temporary SQLite file.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import get_database_settings
from app.core.migration_lock import migration_lock

log = logging.getLogger("charsooq.migrations")

# backend/api/app/core/migrations.py → parents[2] is backend/api.
_BACKEND_DIR = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    """Same resolution as migrations/env.py: DatabaseSettings only.

    Environment variables still win over ``SECRETS_DIR`` files through the
    shared settings sources; the full application Settings is never required.
    """
    return get_database_settings().database_url.strip()


def _build_migration_engine(url: str) -> Engine:
    """Build a short-lived engine whose connection really closes after the run.

    Session-level advisory locks are released when the PostgreSQL session ends,
    so the runner must not return the connection to a long-lived pool after an
    unexpected failure. ``NullPool`` guarantees the physical connection closes.
    """
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database in (None, "", ":memory:"):
            return create_engine(
                parsed,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
        return create_engine(parsed)
    return create_engine(parsed, poolclass=NullPool)


def _run_upgrade(connection: Connection) -> None:
    """Run Alembic's ``upgrade head`` on the caller's connection."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    # migrations/env.py uses this connection instead of creating its own, so
    # the advisory lock and the migration share one database session.
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


def apply_migrations() -> None:
    """Apply all pending migrations under the ChaharSooq advisory lock.

    Used by both the standalone CLI and the API lifespan. Raises on failure;
    the caller decides the process exit code. The advisory lock replaces the
    old multi-replica retry loop: a second runner waits, then finds the
    database already at head instead of racing the first one.
    """
    settings = get_database_settings()
    engine = _build_migration_engine(_database_url())
    try:
        with engine.connect() as connection:
            with migration_lock(
                connection,
                timeout_seconds=settings.migration_lock_timeout_seconds,
            ):
                _run_upgrade(connection)
    finally:
        engine.dispose()
    log.info("database migrations at head")


def upgrade_to_head() -> None:
    """API-startup wrapper: skip tests, otherwise run the shared locked path."""
    from app.core.config import get_settings

    if get_settings().app_env == "test":
        return
    apply_migrations()


def redact_migration_error(message: str) -> str:
    """Remove the database URL and password from an error shown by the CLI."""
    try:
        url = get_database_settings().database_url.strip()
    except Exception:  # noqa: BLE001 — config errors must still be printable
        url = os.environ.get("DATABASE_URL", "").strip()

    if not url:
        return message
    message = message.replace(url, "<database-url>")
    try:
        parsed = make_url(url)
        password = parsed.password
        rendered = parsed.render_as_string(hide_password=False)
    except Exception:  # noqa: BLE001 — a malformed URL is already being reported
        return message
    message = message.replace(rendered, "<database-url>")
    if password:
        message = message.replace(password, "<redacted>")
    return message


def safe_error_message(error: Exception) -> str:
    """Format an exception without Pydantic input values or database secrets.

    Pydantic's default string form can include the rejected input, which may be
    an owner password or a URL with credentials. Only the field location and
    message are kept; non-validation errors go through URL/password redaction.
    """
    from pydantic import ValidationError

    if isinstance(error, ValidationError):
        parts: list[str] = []
        for detail in error.errors():
            location = ".".join(str(part) for part in detail["loc"])
            parts.append(f"{location}: {detail['msg']}")
        return "; ".join(parts) or "invalid configuration"
    return redact_migration_error(str(error)) or type(error).__name__
