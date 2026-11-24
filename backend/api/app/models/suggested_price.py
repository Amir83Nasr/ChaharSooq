"""Per-top-group suggested price configuration.

Weights stay keyed by catalog section (فرش، مبلمان، لوازم خانگی، کالای
دیجیتال): one weight per category, shared by both formulas. The per-product
`pricing_mode` only selects which formula consumes that weight — the weighted
blend for `exact_competitor`, or the scaled daily change for `similar_product`."""

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SuggestedPriceFormula(Base):
    __tablename__ = "suggested_price_formulas"

    top_group: Mapped[str] = mapped_column(String(32), primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
