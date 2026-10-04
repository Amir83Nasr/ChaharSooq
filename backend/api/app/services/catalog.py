"""Category service — thin wrapper over CategoryRepository."""

from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from app.models import Category
from app.repositories import CategoryRepository
from app.schemas import CategoryIn


class CategoryService:
    def __init__(self, session: Session) -> None:
        self._repos = CategoryRepository(session)

    def list(self) -> list[Category]:
        return self._repos.list()

    def create(self, payload: CategoryIn) -> Category:
        return self._repos.add(Category(name=payload.name.strip()))

    def delete(self, category_id: int) -> Category | None | Literal["in_use"]:
        """Return None when missing, "in_use" when products reference it."""
        category = self._repos.get(category_id)
        if category is None:
            return None
        if self._repos.product_count(category_id) > 0:
            return "in_use"
        self._repos.delete(category)
        return category
