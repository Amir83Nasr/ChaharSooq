"""Charsooq admin API application package."""

import app.models  # noqa: F401,E402
from app.core.database import Base  # noqa: F401  (model registration entrypoint)
