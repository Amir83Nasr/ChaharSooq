"""Product service — listing rules, category guard, summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
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
        top_group: str | None,
        main_group: str | None,
        min_price: int | None,
        max_price: int | None,
        competitor_store: str | None = None,
        min_competitor_price: int | None = None,
        max_competitor_price: int | None = None,
        min_stock: int | None,
        max_stock: int | None,
        in_stock: bool | None,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        page = max(page, 1)
        if page_size <= 0:
            page_size = 0
        else:
            page_size = min(max(page_size, 1), 500)
        if min_price is not None and max_price is not None and min_price > max_price:
            min_price, max_price = max_price, min_price
        return self._repos.list(
            query=query.strip(),
            category_id=category_id,
            top_group=(top_group or "").strip() or None,
            main_group=(main_group or "").strip() or None,
            min_price=min_price,
            max_price=max_price,
            competitor_store=competitor_store,
            min_competitor_price=min_competitor_price,
            max_competitor_price=max_competitor_price,
            competitor_price_since=datetime.now(UTC)
            - timedelta(hours=get_settings().competitor_price_ttl_hours),
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

    def groups(self) -> list[str]:
        return self._repos.list_groups()
