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
        Index("ix_products_is_active", "is_active"),
        Index("ix_products_price", "price"),
        Index("ix_products_stock", "stock"),
        # Matches 0012_search_indexes: composite active-first paths for the
        # product list filter/sort (top_group, category, price, stock).
        Index("ix_products_active_main_group", "is_active", "main_group_name"),
        Index("ix_products_active_category", "is_active", "category_id"),
        Index("ix_products_active_price_id", "is_active", "price", "id"),
        Index("ix_products_active_stock", "is_active", "stock"),
        # Matches 0012_search_indexes: trigram GIN for %q% Persian search.
        # `postgresql_*` kwargs only render on PostgreSQL; SQLite (tests)
        # gets plain indexes with the same names — same schema truth,
        # so `alembic check` stays green in CI.
        Index(
            "ix_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_products_sku_trgm",
            "sku",
            postgresql_using="gin",
            postgresql_ops={"sku": "gin_trgm_ops"},
        ),
        Index(
            "ix_products_main_group_trgm",
            "main_group_name",
            postgresql_using="gin",
            postgresql_ops={"main_group_name": "gin_trgm_ops"},
        ),
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
    # Allowed deviation from the base price for the suggested price clamp:
    # floor = price × (1 − allowed_decrease_percent / 100),
    # ceiling = price × (1 + allowed_increase_percent / 100). NULL disables
    # that side of the clamp for manually added rows.
    allowed_decrease_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, default=None
    )
    allowed_increase_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, default=None
    )
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
        back_populates="product", passive_deletes=True
    )
