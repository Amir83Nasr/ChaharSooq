"""Category repository — direct Category queries."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Product


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
