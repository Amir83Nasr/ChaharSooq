"""Standalone migration runner — one controlled step before the API starts.

Usage from the repository root::

    DEPLOYMENT_ENV=development uv run --project backend/api \
      python backend/api/scripts/migrate.py
    # Read-only check used by deploy.sh before starting the API:
    python backend/api/scripts/migrate.py --check

The runner resolves the database through ``MigrationSettings`` only
(``MIGRATION_DATABASE_URL``; Development/Staging may still fall back to
``DATABASE_URL``), applies Alembic to ``head`` under the ChaharSooq PostgreSQL
advisory lock, and exits non-zero on failure or lock timeout. It never reads
the API's application credential in Production, never calls ``create_all``,
and never prints a database URL or a password.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.deployment import KNOWN_DEPLOYMENT_ENVS, enforce_deployment_env
from app.core.migration_lock import MigrationLockTimeoutError
from app.core.migrations import apply_migrations, has_pending_migrations, safe_error_message


def main() -> None:
    enforce_deployment_env("migrate", KNOWN_DEPLOYMENT_ENVS)
    args = sys.argv[1:]
    if args not in ([], ["--check"]):
        raise SystemExit("usage: migrate.py [--check]")
    check_only = bool(args)
    try:
        if check_only:
            pending = has_pending_migrations()
            message = (
                "migrate: migrations pending" if pending else "migrate: database already at head"
            )
            print(message)
            return
        apply_migrations()
    except MigrationLockTimeoutError as error:
        print(f"migrate: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:  # noqa: BLE001 — turn every failure into a clean exit
        message = safe_error_message(error)
        print(
            f"migrate: migration failed ({type(error).__name__}): {message}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print("migrate: database is at head")


if __name__ == "__main__":
    main()
