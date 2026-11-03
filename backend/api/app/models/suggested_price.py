"""Per-top-group suggested price formula configuration.

Formulas are keyed by the store's three top-level groups (فرش، مبلمان،
لوازم خانگی) — the same groups shown in the products table — not by the
manual `categories` table."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SuggestedPriceFormula(Base):
    __tablename__ = "suggested_price_formulas"

    top_group: Mapped[str] = mapped_column(String(32), primary_key=True)
    expression: Mapped[str] = mapped_column(String(256), nullable=False)
