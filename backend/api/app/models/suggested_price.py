"""Per-top-group suggested price configuration.

Suggested prices use one fixed formula — ``weight × competitor +
(1 − weight) × Parsina base`` — keyed by the store's three top-level groups
(فرش، مبلمان، لوازم خانگی), the same groups shown in the products table."""

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SuggestedPriceFormula(Base):
    __tablename__ = "suggested_price_formulas"

    top_group: Mapped[str] = mapped_column(String(32), primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
