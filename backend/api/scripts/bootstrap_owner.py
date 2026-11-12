"""Explicit owner bootstrap — no ``create_all``, requires a migrated schema.

The API still ensures the env-managed owner on startup when
``RUN_OWNER_BOOTSTRAP_ON_STARTUP`` is enabled (the default). This standalone
command is the explicit path a Production deploy can use instead, after the
schema is at head::

    DEPLOYMENT_ENV=production uv run --project backend/api \
      python backend/api/scripts/bootstrap_owner.py

It reads ``OWNER_USERNAME`` / ``OWNER_PASSWORD`` through the normal settings and
secret sources. Re-running is idempotent: the account is created only when
missing, the password is re-hashed only when it changed, and the single-owner
invariant is preserved. The script never creates tables.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.database import get_engine
from app.core.deployment import KNOWN_DEPLOYMENT_ENVS, enforce_deployment_env
from app.core.migrations import safe_error_message
from app.services.owner import OwnerBootstrapService
from scripts.common import session_scope


def _fail(message: str) -> NoReturn:
    print(f"bootstrap_owner: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    enforce_deployment_env("bootstrap_owner", KNOWN_DEPLOYMENT_ENVS)
    try:
        settings: Settings = get_settings()
    except Exception as error:  # noqa: BLE001 — configuration errors must not print secrets
        detail = safe_error_message(error)
        _fail(f"invalid configuration ({type(error).__name__}): {detail}")

    if settings.app_env == "test":
        _fail("refuses APP_ENV=test; tests manage their own accounts")
    if not settings.owner_password:
        _fail("OWNER_PASSWORD must be set")
    if len(settings.owner_password) < 8:
        _fail("OWNER_PASSWORD must be at least 8 characters")

    engine = get_engine()
    try:
        if not inspect(engine).has_table("admins"):
            _fail("the 'admins' table is missing; run migrations before owner bootstrap")
        with session_scope(commit=True) as session:
            OwnerBootstrapService(session).apply(
                settings.owner_username,
                settings.owner_password,
            )
    except SystemExit:
        raise
    except SQLAlchemyError as error:
        _fail(f"database error ({type(error).__name__}): {safe_error_message(error)}")

    print(f"bootstrap_owner: owner account '{settings.owner_username}' ensured")


if __name__ == "__main__":
    main()
