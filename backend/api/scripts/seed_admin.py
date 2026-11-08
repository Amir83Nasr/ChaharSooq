"""Ensure the env-managed owner account — idempotent, safe to re-run.

Reads OWNER_USERNAME / OWNER_PASSWORD (legacy ADMIN_USER / ADMIN_PASSWORD are
accepted aliases) through the shared settings, so the seed script and API boot
always agree. Run via `make db-seed` / `make db-seed-prod`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.database import Base, get_engine
from app.services.owner import OwnerBootstrapService
from scripts.common import session_scope


def main() -> None:
    settings = get_settings()
    if not settings.owner_password:
        raise SystemExit("OWNER_PASSWORD must be set")
    if len(settings.owner_password) < 8:
        raise SystemExit("OWNER_PASSWORD must be at least 8 characters")
    Base.metadata.create_all(get_engine())
    with session_scope(commit=True) as session:
        OwnerBootstrapService(session).apply(settings.owner_username, settings.owner_password)
    print(f"owner account '{settings.owner_username}' ensured")


if __name__ == "__main__":
    main()
