"""Product service — listing rules, category guard, summary."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Product
from app.repositories import (
    CategoryRepository,
    ProductFilters,
    ProductRepository,
    ProductSort,
)
from app.schemas import (
    ProductCompetitorFlagUpdate,
    ProductIn,
    ProductPriceBoundsUpdate,
    ProductPricingModeUpdate,
)

INVALID_CATEGORY_ERROR = "دسته‌بندی نامعتبر است"

# NOTE: the "show all" cap (`SHOW_ALL_MAX`) lives in
# `app.repositories.products`, next to the query that applies it.


class InvalidCategoryError(ValueError):
    pass


class ProductNotFoundError(LookupError):
    pass


class ProductService:
    def __init__(self, session: Session) -> None:
        self._repos = ProductRepository(session)
        self._categories = CategoryRepository(session)

    def filters(
        self,
        *,
        query: str,
        category_id: int | None,
        top_groups: Sequence[str] | None,
        main_group: str | None,
        min_price: int | None,
        max_price: int | None,
        competitor_store: str | None = None,
        min_competitor_price: int | None = None,
        max_competitor_price: int | None = None,
        min_stock: int | None,
        max_stock: int | None,
        in_stock: bool | None,
        no_competitor_price: bool = False,
    ) -> ProductFilters:
        """Normalise query params once; the list and the CSV export share it."""
        if min_price is not None and max_price is not None and min_price > max_price:
            min_price, max_price = max_price, min_price
        return ProductFilters(
            query=query.strip(),
            category_id=category_id,
            top_groups=tuple(
                dict.fromkeys(group.strip() for group in (top_groups or []) if group.strip())
            ),
            main_group=(main_group or "").strip() or None,
            min_price=min_price,
            max_price=max_price,
            competitor_store=competitor_store,
            min_competitor_price=min_competitor_price,
            max_competitor_price=max_competitor_price,
            no_competitor_price=no_competitor_price,
            competitor_price_since=datetime.now(UTC)
            - timedelta(hours=get_settings().competitor_price_ttl_hours),
            min_stock=min_stock,
            max_stock=max_stock,
            in_stock=in_stock,
        )

    def list(
        self,
        *,
        query: str,
        category_id: int | None,
        top_groups: Sequence[str] | None,
        main_group: str | None,
        min_price: int | None,
        max_price: int | None,
        competitor_store: str | None = None,
        min_competitor_price: int | None = None,
        max_competitor_price: int | None = None,
        min_stock: int | None,
        max_stock: int | None,
        in_stock: bool | None,
        no_competitor_price: bool = False,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        page = max(page, 1)
        # `page_size=0` is the "show all" path: capped, no offset.
        # Any explicit size is paginated and clamped to 1..500.
        if page_size <= 0:
            page_size = 0
        else:
            page_size = min(max(page_size, 1), 500)
        filters = self.filters(
            query=query,
            category_id=category_id,
            top_groups=top_groups,
            main_group=main_group,
            min_price=min_price,
            max_price=max_price,
            competitor_store=competitor_store,
            min_competitor_price=min_competitor_price,
            max_competitor_price=max_competitor_price,
            min_stock=min_stock,
            max_stock=max_stock,
            in_stock=in_stock,
            no_competitor_price=no_competitor_price,
        )
        return self._repos.list(
            filters=filters,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def count_export(self, *, filters: ProductFilters) -> int:
        return self._repos.count(filters=filters)

    def iter_export(self, *, filters: ProductFilters, sort: ProductSort) -> Iterator[list[Product]]:
        return self._repos.iter_batches(filters=filters, sort=sort)

    def create(self, payload: ProductIn) -> Product:
        if payload.category_id is not None and self._categories.get(payload.category_id) is None:
            raise InvalidCategoryError
        return self._repos.add(Product(**payload.model_dump()))

    def update_price_bounds(self, product_id: int, payload: ProductPriceBoundsUpdate) -> Product:
        product = self._repos.get(product_id)
        if product is None:
            raise ProductNotFoundError
        values = payload.model_dump(exclude_unset=True)
        decrease = values.get("allowed_decrease_percent", product.allowed_decrease_percent)
        increase = values.get("allowed_increase_percent", product.allowed_increase_percent)
        self._repos.update_price_bounds(
            product,
            allowed_decrease_percent=(Decimal(str(decrease)) if decrease is not None else None),
            allowed_increase_percent=(Decimal(str(increase)) if increase is not None else None),
        )
        return product

    def set_pricing_mode(self, product_id: int, payload: ProductPricingModeUpdate) -> Product:
        product = self._repos.get(product_id)
        if product is None:
            raise ProductNotFoundError
        self._repos.set_pricing_mode(product, value=payload.pricing_mode)
        return product

    def set_no_competitor_price(
        self, product_id: int, payload: ProductCompetitorFlagUpdate
    ) -> Product:
        product = self._repos.get(product_id)
        if product is None:
            raise ProductNotFoundError
        self._repos.set_no_competitor_price(product, value=payload.no_competitor_price)
        return product

    def summary(self, *, low_stock_threshold: int) -> dict[str, int]:
        return self._repos.summary(low_stock_threshold=low_stock_threshold)

    def groups(self) -> list[str]:
        return self._repos.list_groups()
