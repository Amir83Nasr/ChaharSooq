"""Shared helpers for backend/api/scripts — keeps standalone scripts runnable.

Each script stays executable directly (`python backend/api/scripts/<name>.py`)
with a one-line `sys.path` bootstrap, then imports from here. Nothing in
`app/` may import from this module.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.core.database import get_engine


def require_env(name: str) -> str:
    """Read a required env var or exit with a actionable message."""
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is required (see backend/api/.env.example)")
    return value


@contextmanager
def session_scope(*, commit: bool = False) -> Iterator[Session]:
    """Yield a Session bound to the configured engine; commit optionally."""
    with Session(get_engine()) as session:
        yield session
        if commit:
            session.commit()
