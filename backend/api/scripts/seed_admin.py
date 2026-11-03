"""Seed a dev admin user — idempotent, safe to re-run.

Reads ADMIN_USER / ADMIN_PASSWORD from the environment (see Makefile).
Run via `make seed` from the repository root.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import Base, get_engine
from app.core.security import hash_password
from app.models import Admin
from scripts.common import session_scope


def main() -> None:
    username = os.environ.get("ADMIN_USER", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "secret123")
    if not password:
        raise SystemExit("ADMIN_PASSWORD must not be empty")
    Base.metadata.create_all(get_engine())
    with session_scope(commit=True) as session:
        exists: int | None = session.scalar(select(Admin.id).limit(1))
        if exists is not None:
            print("admin already exists, skipping")
            return
        session.add(Admin(username=username, password_hash=hash_password(password)))
    print(f"admin user '{username}' created")


if __name__ == "__main__":
    main()
