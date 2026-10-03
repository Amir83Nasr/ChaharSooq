"""Charsooq admin API application package."""

from app import models
from app.core.database import Base

__all__ = ["Base", "models"]
