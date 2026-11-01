"""Catalog models — categories + products (machine values, Parsina-synced)."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import utcnow

if TYPE_CHECKING:
    from app.models.competitor import CompetitorListing


class Category(Base):
    """Product category — Persian display name, machine id in API/DB."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    """Local mirror of an accounting product — `external_id` is Parsina's goodId.

    `price`/`stock` are the display pair (salePrice / remain); the remaining
    columns keep the raw accounting data. Market prices (Toru) will live in a
    separate table keyed by `id`, never mixed into these accounting fields.
    """

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_created_at", "created_at"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_sku", "sku"),
        Index("ix_products_main_group_name", "main_group_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True, default=None
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    stock: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, default=None
    )
    main_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    sub_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    main_group_name: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    sub_group_name: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    unit_name: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True, default=None)
    is_special: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    buy_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True, default=None)
    sale_pack_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True, default=None
    )
    sale_box_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True, default=None
    )
    use_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True, default=None)
    discount: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True, default=None)
    extra: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True, default=None)
    number_in_box: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 3), nullable=True, default=None
    )
    number_in_pack: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 3), nullable=True, default=None
    )
    ware_remain: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True, default=None)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    category: Mapped["Category | None"] = relationship(back_populates="products")
    competitor_listings: Mapped[list["CompetitorListing"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
