"""Per-category suggested price formula configuration."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SuggestedPriceFormula(Base):
    __tablename__ = "suggested_price_formulas"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    expression: Mapped[str] = mapped_column(String(256), nullable=False)
