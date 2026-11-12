# pyright: reportUnusedImport=false
"""Alembic environment — autogenerate from app.models metadata.

Run from backend/api so `import app...` resolves (prepend_sys_path = .).
The database URL comes from `MigrationSettings` only: `MIGRATION_DATABASE_URL`
or a `migration_database_url` file under `SECRETS_DIR`, with the usual
environment precedence. Development and Staging fall back to `DATABASE_URL`
when the dedicated value is absent; Production requires it. The full
application `Settings` and the API's application credential are never used
here, so migrating does not depend on authentication or unrelated application
configuration.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context  # noqa: E402
from sqlalchemy import Connection, engine_from_config, pool  # noqa: E402

from app.core.config import get_migration_settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.migration_lock import migration_lock  # noqa: E402

import app.models  # noqa: E402,F401  (register models)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# One settings source for migrations: a bare `alembic upgrade head` must use
# the same migration credential as `python scripts/migrate.py`. An explicit
# Production deployment refuses a missing or loopback migration URL, so offline
# and online runs fail before opening a connection.
migration_settings = get_migration_settings()
db_url = migration_settings.resolved_migration_database_url.strip()
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _upgrade(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
    # The advisory-lock SELECT runs before Alembic and therefore opens a
    # SQLAlchemy transaction. When Alembic sees that external transaction it
    # deliberately does not commit it (``begin_transaction`` becomes a
    # no-op), so the caller must. Without this, ``engine.connect()`` closes
    # the connection by rolling back and every migration is lost. A
    # transaction that Alembic itself started is already closed here.
    if connection.in_transaction():
        connection.commit()


def run_migrations_online() -> None:
    # The runner (app.core.migrations) acquires the advisory lock and passes the
    # very same connection through config.attributes. Trusting it here is what
    # keeps the migration and the lock on one database session.
    provided = config.attributes.get("connection")
    if provided is not None:
        _upgrade(cast(Connection, provided))
        return

    # A plain `alembic upgrade head` still gets the lock. NullPool makes the
    # connection close after the run, so PostgreSQL releases the session lock
    # even if the process fails before the explicit unlock.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        with migration_lock(
            connection,
            timeout_seconds=migration_settings.migration_lock_timeout_seconds,
        ):
            _upgrade(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
