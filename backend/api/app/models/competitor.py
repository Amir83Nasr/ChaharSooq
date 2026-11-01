"""Manually managed competitor product links and price observations."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import utcnow

if TYPE_CHECKING:
    from app.models.catalog import Product

CompetitorStore = Literal["digikala", "technolife"]
CompetitorStatus = Literal[
    "pending", "success", "not_found", "unavailable", "blocked", "failed", "manual"
]


class CompetitorListing(Base):
    """A product's link on one competitor; manual values survive later checks."""

    __tablename__ = "competitor_listings"
    __table_args__ = (
        Index("ix_competitor_listings_product_id", "product_id"),
        Index("ix_competitor_listings_store", "store"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    store: Mapped[str] = mapped_column(String(30), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    fetched_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    fetched_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    fetched_in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    manual_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    manual_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    manual_in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    manual_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    product: Mapped["Product"] = relationship(back_populates="competitor_listings")
