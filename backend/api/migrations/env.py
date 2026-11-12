# pyright: reportUnusedImport=false
"""Alembic environment — autogenerate from app.models metadata.

Run from backend/api so `import app...` resolves (prepend_sys_path = .).
The database URL comes from `DatabaseSettings` only: `DATABASE_URL` or a
`database_url` file under `SECRETS_DIR`, with the usual environment precedence.
The full application `Settings` is never instantiated here, so migrations do
not depend on authentication or unrelated application configuration.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context  # noqa: E402
from sqlalchemy import Connection, engine_from_config, pool  # noqa: E402

from app.core.config import get_database_settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.migration_lock import migration_lock  # noqa: E402

import app.models  # noqa: E402,F401  (register models)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# One settings source for migrations and seeds: a bare `alembic upgrade head`
# must never target a different database than `python scripts/seed_*.py`.
# DatabaseSettings refuses the localhost default when Production is explicitly
# identified, so offline and online runs fail before opening a connection.
db_url = get_database_settings().database_url.strip()
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
            timeout_seconds=get_database_settings().migration_lock_timeout_seconds,
        ):
            _upgrade(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
