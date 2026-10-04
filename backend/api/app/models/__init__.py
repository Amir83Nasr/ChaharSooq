"""SQLAlchemy models — machine-readable values only, never Jalali/Persian strings."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Admin(Base):
    """Single admin row seeded from ADMIN_PASSWORD_HASH env at deploy time."""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (Index("ix_admin_sessions_expires_at", "expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Category(Base):
    """Product category — Persian display name, machine id in API/DB."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    """Example domain row — prices are integer toman, datetimes stay tz-aware."""

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_created_at", "created_at"),
        Index("ix_products_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # toman, integer
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    category: Mapped["Category | None"] = relationship(back_populates="products")
