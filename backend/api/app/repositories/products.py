"""Product repository — filters, paging, summary aggregate."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import ColumnElement, and_, case, delete, exists, func, not_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import CompetitorListing, Product

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

    def delete_all(self) -> int:
        """Drop the whole mirror — used only by the dev CSV seed (replace mode)."""
        total = self._session.execute(select(func.count()).select_from(Product)).scalar_one()
        self._session.execute(delete(Product))
        return total

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
        threshold = max(low_stock_threshold, 0)
        active = Product.is_active.is_(True)
        total = self._session.execute(
            select(func.count()).select_from(Product).where(active)
        ).scalar_one()
        out_of_stock = self._session.execute(
            select(func.count()).select_from(Product).where(active, Product.stock <= 0)
        ).scalar_one()
        low = self._session.execute(
            select(func.count())
            .select_from(Product)
            .where(active, Product.stock > 0, Product.stock <= threshold)
        ).scalar_one()
        in_stock = total - out_of_stock - low
        stock_value = self._session.execute(
            select(func.coalesce(func.sum(Product.stock * Product.price), 0)).where(active)
        ).scalar_one()
        return {
            "total": total,
            "in_stock": in_stock,
            "low": low,
            "out": out_of_stock,
            "stock_value": int(stock_value),
        }

    def list(
        self,
        *,
        query: str,
        category_id: int | None,
        top_group: str | None,
        main_group: str | None,
        min_price: int | None,
        max_price: int | None,
        competitor_store: str | None,
        min_competitor_price: int | None,
        max_competitor_price: int | None,
        competitor_price_since: datetime,
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
        if top_group:
            if top_group == "فرش":
                criteria.append(Product.main_group_name.ilike("فرش%"))
            elif top_group == "مبلمان":
                criteria.append(Product.main_group_name.ilike("مبلمان%"))
            elif top_group == "لوازم خانگی":
                criteria.append(Product.main_group_name.is_not(None))
                criteria.append(not_(Product.main_group_name.ilike("فرش%")))
                criteria.append(not_(Product.main_group_name.ilike("مبلمان%")))
        if min_price is not None:
            criteria.append(Product.price >= min_price)
        if max_price is not None:
            criteria.append(Product.price <= max_price)
        if competitor_store or min_competitor_price is not None or max_competitor_price is not None:
            manual_fresh = and_(
                CompetitorListing.manual_price.is_not(None),
                CompetitorListing.manual_updated_at >= competitor_price_since,
            )
            fetched_fresh = and_(
                CompetitorListing.fetched_price.is_not(None),
                CompetitorListing.last_success_at >= competitor_price_since,
            )
            manual_toman = case(
                (CompetitorListing.manual_currency == "IRR", CompetitorListing.manual_price / 10),
                else_=CompetitorListing.manual_price,
            )
            fetched_toman = case(
                (CompetitorListing.fetched_currency == "IRR", CompetitorListing.fetched_price / 10),
                else_=CompetitorListing.fetched_price,
            )
            current_price = case(
                (manual_fresh, manual_toman),
                (fetched_fresh, fetched_toman),
                else_=None,
            )
            price_criteria: list[ColumnElement[bool]] = [
                CompetitorListing.product_id == Product.id,
                CompetitorListing.is_active.is_(True),
                current_price.is_not(None),
            ]
            if competitor_store:
                price_criteria.append(CompetitorListing.store == competitor_store)
            if min_competitor_price is not None:
                price_criteria.append(current_price >= min_competitor_price)
            if max_competitor_price is not None:
                price_criteria.append(current_price <= max_competitor_price)
            criteria.append(exists(select(1).where(*price_criteria)))
        if in_stock is True:
            criteria.append(Product.stock > 0)
        elif in_stock is False:
            criteria.append(Product.stock <= 0)
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
        # Hard cap for the legacy `page_size=0` ("show all") path: an uncapped
        # select on a large catalog can OOM the worker, so treat it as a
        # bounded export (first N rows, no offset).
        if page_size and page_size > 0:
            start = (page - 1) * page_size
            stmt = base.order_by(order).offset(start).limit(page_size)
        else:
            stmt = base.order_by(order).limit(500)
        rows = self._session.execute(stmt).unique().scalars().all()
        return list(rows), total

    def add(self, product: Product) -> Product:
        self._session.add(product)
        self._session.flush()
        return product

    def stage(self, product: Product) -> Product:
        """Attach a new row without flushing — caller flushes in bulk."""
        self._session.add(product)
        return product
