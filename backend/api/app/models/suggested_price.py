"""Per-pricing-mode suggested price configuration.

Suggested prices use two fixed formulas — ``weight × competitor +
(1 − weight) × Parsina base`` for ``exact_competitor`` and
``base × (1 + weight × daily change)`` for ``similar_product`` — selected by
each product's persisted `pricing_mode`, not by its catalog section."""

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SuggestedPriceFormula(Base):
    __tablename__ = "suggested_price_formulas"

    mode: Mapped[str] = mapped_column(String(32), primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
