"""Manually managed competitor product links and price observations."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import utcnow

if TYPE_CHECKING:
    from app.models.catalog import Product

CompetitorStore = Literal["digikala", "technolife"]
CompetitorStatus = Literal[
    "pending", "success", "not_found", "unavailable", "blocked", "failed", "manual"
]

COMPETITOR_SYNC_STATE_ID = 1


class CompetitorListing(Base):
    """A product's link on one competitor; manual values survive later checks."""

    __tablename__ = "competitor_listings"
    __table_args__ = (
        Index("ix_competitor_listings_product_id", "product_id"),
        Index("ix_competitor_listings_store", "store"),
        # Matches 0010_query_indexes: a real constraint, not just a unique
        # index, so concurrent inserts cannot create duplicates.
        UniqueConstraint(
            "product_id",
            "store",
            name="uq_competitor_listings_product_store",
        ),
        Index("ix_competitor_listings_last_success", "last_success_at"),
        Index(
            "ix_competitor_listings_product_active",
            "product_id",
            "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT is deliberate: a stray product delete must fail instead of
    # silently cascading into manually curated competitor links.
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
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


class CompetitorSyncState(Base):
    """Single row. Lock + last bulk-refresh bookkeeping for all listings."""

    __tablename__ = "competitor_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    running_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
