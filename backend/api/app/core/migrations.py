"""Database migrations at startup — zero manual `alembic upgrade` anywhere.

Every process that serves the API (local `uvicorn`, Docker `api`, FastAPI
Cloud) calls :func:`upgrade_to_head` in the FastAPI lifespan, so a fresh or
stale database is migrated automatically before the first request. Alembic
upgrades are idempotent, so the one-shot `migrate` service in compose.yml and
this lifespan hook can safely coexist — whichever runs first wins.

Skipped when ``APP_ENV=test``: tests manage their own schema with
``Base.metadata.create_all`` (see tests/conftest.py).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("charsooq.migrations")

# backend/api/app/core/migrations.py → parents[2] is backend/api.
_BACKEND_DIR = Path(__file__).resolve().parents[2]

#: How many times to retry a failed upgrade (covers multi-replica races on
#: the alembic_version row at deploy time). A genuinely broken migration
#: still fails fast after the last attempt.
_UPGRADE_ATTEMPTS = 3
_UPGRADE_RETRY_SECONDS = 2.0


def _database_url() -> str:
    """Same resolution as migrations/env.py: env wins, settings fallback."""
    from app.core.config import get_settings

    return (os.environ.get("DATABASE_URL") or get_settings().database_url).strip()


def upgrade_to_head() -> None:
    """Apply all pending Alembic migrations. Raises on failure."""
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    if get_settings().app_env == "test":
        return

    cfg = Config()
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _database_url())

    last_error: Exception | None = None
    for attempt in range(1, _UPGRADE_ATTEMPTS + 1):
        try:
            command.upgrade(cfg, "head")
        except Exception as error:
            last_error = error
            log.warning("migration attempt %d failed: %s", attempt, error)
            if attempt < _UPGRADE_ATTEMPTS:
                time.sleep(_UPGRADE_RETRY_SECONDS)
                continue
            raise
        log.info("database migrations at head")
        return
    if last_error is not None:  # pragma: no cover — loop always raises or returns
        raise last_error
