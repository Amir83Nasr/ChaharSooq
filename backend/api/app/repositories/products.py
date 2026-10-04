"""Product repository — filters, paging, summary aggregate."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Product

ProductSort = Literal["newest", "cheapest", "most_expensive"]


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self, *, low_stock_threshold: int) -> dict[str, int]:
        rows = self._session.execute(select(Product.stock, Product.price)).all()
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
            "stock_value": stock_value,
        }

    def list(
        self,
        *,
        query: str,
        category_id: int | None,
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
        criteria = []
        if query:
            like = f"%{query}%"
            criteria.append(or_(Product.name.ilike(like), Product.sku.ilike(like)))
        if category_id is not None:
            criteria.append(Product.category_id == category_id)
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
