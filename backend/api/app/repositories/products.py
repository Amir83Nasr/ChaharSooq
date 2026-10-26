"""Product repository — filters, paging, summary aggregate."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Product

ProductSort = Literal["newest", "cheapest", "most_expensive"]


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def by_external_ids(self, external_ids: set[int]) -> dict[int, Product]:
        """Existing mirror rows for one sync batch, keyed by Parsina goodId."""
        if not external_ids:
            return {}
        rows = self._session.execute(
            select(Product).where(Product.external_id.in_(external_ids))
        ).scalars()
        return {p.external_id: p for p in rows if p.external_id is not None}

    def sku_in_use(self, skus: set[str]) -> set[str]:
        """SKUs already taken by rows with a different (or no) Parsina identity."""
        if not skus:
            return set()
        return set(
            self._session.execute(select(Product.sku).where(Product.sku.in_(skus))).scalars()
        )

    def list_groups(self) -> list[str]:
        rows = self._session.execute(
            select(Product.main_group_name)
            .where(Product.main_group_name.is_not(None))
            .distinct()
            .order_by(Product.main_group_name)
        ).scalars()
        return [name for name in rows if name]

    def deactivate_missing(self, keep_external_ids: set[int]) -> int:
        """Soft-delete mirror rows absent from a *complete* Parsina listing."""
        stmt = select(Product).where(Product.external_id.is_not(None), Product.is_active.is_(True))
        if keep_external_ids:
            stmt = stmt.where(Product.external_id.not_in(keep_external_ids))
        stale = list(self._session.execute(stmt).scalars())
        for product in stale:
            product.is_active = False
        return len(stale)

    def summary(self, *, low_stock_threshold: int) -> dict[str, int]:
        rows = self._session.execute(
            select(Product.stock, Product.price).where(Product.is_active.is_(True))
        ).all()
        total = len(rows)
        out = sum(1 for s, _ in rows if s <= 0)
        low = sum(1 for s, _ in rows if 0 < s <= max(low_stock_threshold, 0))
        in_stock = total - out - low
        stock_value = sum(s * p for s, p in rows)
        return {
            "total": total,
            "in_stock": in_stock,
            "low": low,
            "out": out,
            "stock_value": int(stock_value),
        }

    def list(
        self,
        *,
        query: str,
        category_id: int | None,
        main_group: str | None,
        min_price: int | None,
        max_price: int | None,
        min_stock: int | None,
        max_stock: int | None,
        in_stock: bool | None,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        base = select(Product).options(joinedload(Product.category))
        count_stmt = select(func.count()).select_from(Product)
        criteria: list[ColumnElement[bool]] = [Product.is_active.is_(True)]
        if query:
            like = f"%{query}%"
            criteria.append(
                or_(
                    Product.name.ilike(like),
                    Product.sku.ilike(like),
                    Product.main_group_name.ilike(like),
                    Product.sub_group_name.ilike(like),
                )
            )
        if category_id is not None:
            criteria.append(Product.category_id == category_id)
        if main_group:
            criteria.append(Product.main_group_name == main_group)
        if min_price is not None:
            criteria.append(Product.price >= min_price)
        if max_price is not None:
            criteria.append(Product.price <= max_price)
        if in_stock is True:
            criteria.append(Product.stock > 0)
        elif in_stock is False:
            criteria.append(Product.stock == 0)
        if min_stock is not None:
            criteria.append(Product.stock >= min_stock)
        if max_stock is not None:
            criteria.append(Product.stock <= max_stock)
        for criterion in criteria:
            base = base.where(criterion)
            count_stmt = count_stmt.where(criterion)
        total = self._session.execute(count_stmt).scalar_one()
        order = {
            "newest": Product.id.desc(),
            "cheapest": Product.price.asc(),
            "most_expensive": Product.price.desc(),
        }[sort]
        start = (page - 1) * page_size
        rows = (
            self._session.execute(base.order_by(order).offset(start).limit(page_size))
            .unique()
            .scalars()
            .all()
        )
        return list(rows), total

    def add(self, product: Product) -> Product:
        self._session.add(product)
        self._session.flush()
        return product
