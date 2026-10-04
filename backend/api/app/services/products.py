"""Product service — listing rules, category guard, summary."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Category, Product
from app.repositories import ProductRepository, ProductSort
from app.schemas import ProductIn

INVALID_CATEGORY_ERROR = "دسته‌بندی نامعتبر است"


class InvalidCategoryError(ValueError):
    pass


class ProductService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repos = ProductRepository(session)

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
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        if min_price is not None and max_price is not None and min_price > max_price:
            min_price, max_price = max_price, min_price
        return self._repos.list(
            query=query.strip(),
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            min_stock=min_stock,
            max_stock=max_stock,
            in_stock=in_stock,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def create(self, payload: ProductIn) -> Product:
        if (
            payload.category_id is not None
            and self._session.get(Category, payload.category_id) is None
        ):
            raise InvalidCategoryError
        return self._repos.add(Product(**payload.model_dump()))

    def summary(self, *, low_stock_threshold: int) -> dict[str, int]:
        return self._repos.summary(low_stock_threshold=low_stock_threshold)
