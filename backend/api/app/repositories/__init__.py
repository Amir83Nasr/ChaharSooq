from __future__ import annotations

from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Product

ProductSort = Literal["newest", "cheapest", "most_expensive"]


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[Category]:
        return list(self._session.execute(select(Category).order_by(Category.name)).scalars().all())

    def get(self, category_id: int) -> Category | None:
        return self._session.get(Category, category_id)

    def add(self, category: Category) -> Category:
        self._session.add(category)
        self._session.flush()
        return category

    def product_count(self, category_id: int) -> int:
        return self._session.execute(
            select(func.count()).select_from(Product).where(Product.category_id == category_id)
        ).scalar_one()

    def delete(self, category: Category) -> None:
        self._session.delete(category)


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        *,
        query: str,
        category_id: int | None,
        min_price: int | None,
        max_price: int | None,
        in_stock: bool | None,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        base = select(Product).options(joinedload(Product.category))
        count_stmt = select(func.count()).select_from(Product)
        if query:
            like = f"%{query}%"
            criterion = or_(Product.name.ilike(like), Product.sku.ilike(like))
            base = base.where(criterion)
            count_stmt = count_stmt.where(criterion)
        if category_id is not None:
            base = base.where(Product.category_id == category_id)
            count_stmt = count_stmt.where(Product.category_id == category_id)
        if min_price is not None:
            base = base.where(Product.price >= min_price)
            count_stmt = count_stmt.where(Product.price >= min_price)
        if max_price is not None:
            base = base.where(Product.price <= max_price)
            count_stmt = count_stmt.where(Product.price <= max_price)
        if in_stock is True:
            base = base.where(Product.stock > 0)
            count_stmt = count_stmt.where(Product.stock > 0)
        elif in_stock is False:
            base = base.where(Product.stock == 0)
            count_stmt = count_stmt.where(Product.stock == 0)
        total = self._session.execute(count_stmt).scalar_one()
        order = {
            "newest": Product.id.desc(),
            "cheapest": Product.price.asc(),
            "most_expensive": Product.price.desc(),
        }[sort]
        start = (page - 1) * page_size
        rows = (
            self._session.execute(base.order_by(order).offset(start).limit(page_size))
            .scalars()
            .unique()
            .all()
        )
        return list(rows), total

    def add(self, product: Product) -> Product:
        self._session.add(product)
        self._session.flush()
        return product
