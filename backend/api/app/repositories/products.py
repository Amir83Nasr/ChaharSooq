"""Product repository — filters, paging, summary aggregate."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, NamedTuple

from sqlalchemy import ColumnElement, and_, case, delete, exists, func, not_, or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.elements import Case

from app.models import CompetitorListing, Product

ProductSort = Literal["newest", "cheapest", "most_expensive"]


class CompetitorGapRow(NamedTuple):
    product_id: int
    name: str
    our_price: float
    store: str
    competitor_price: float


def effective_competitor_price(since: datetime) -> Case:
    """One fresh competitor price in toman, or NULL.

    Manual prices win over fetched ones; IRR values are converted to toman.
    A price only counts while its observation is newer than `since`.
    """
    manual_fresh = and_(
        CompetitorListing.manual_price.is_not(None),
        CompetitorListing.manual_updated_at >= since,
    )
    fetched_fresh = and_(
        CompetitorListing.fetched_price.is_not(None),
        CompetitorListing.last_success_at >= since,
    )
    manual_toman = case(
        (CompetitorListing.manual_currency == "IRR", CompetitorListing.manual_price / 10),
        else_=CompetitorListing.manual_price,
    )
    fetched_toman = case(
        (CompetitorListing.fetched_currency == "IRR", CompetitorListing.fetched_price / 10),
        else_=CompetitorListing.fetched_price,
    )
    return case(
        (manual_fresh, manual_toman),
        (fetched_fresh, fetched_toman),
        else_=None,
    )


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
        """Soft-delete every active mirror row absent from a *complete* source listing.

        The catalog is an exact mirror of the source (CSV in development,
        Parsina in production): manual rows (`external_id IS NULL`) are also
        deactivated when they are not in the listing, otherwise the table
        can never shrink back to the source.
        """
        stmt = select(Product).where(Product.is_active.is_(True))
        if keep_external_ids:
            # NULL never matches NOT IN (three-valued logic), so manual rows
            # need an explicit IS NULL branch — otherwise they survive forever.
            stmt = stmt.where(
                or_(
                    Product.external_id.is_(None),
                    Product.external_id.not_in(keep_external_ids),
                )
            )
        stale = list(self._session.execute(stmt).scalars())
        for product in stale:
            product.is_active = False
        return len(stale)

    def summary(self, *, low_stock_threshold: int) -> dict[str, int]:
        threshold = max(low_stock_threshold, 0)
        active = Product.is_active.is_(True)
        # One aggregate round-trip instead of five count queries; CASE keeps
        # the buckets consistent on PostgreSQL and SQLite alike.
        row = self._session.execute(
            select(
                func.sum(case((active, 1), else_=0)).label("total"),
                func.sum(case((and_(active, Product.stock <= 0), 1), else_=0)).label("out"),
                func.sum(
                    case(
                        (
                            and_(
                                active,
                                Product.stock > 0,
                                Product.stock <= threshold,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("low"),
                func.coalesce(
                    func.sum(case((active, Product.stock * Product.price), else_=0)),
                    0,
                ).label("stock_value"),
            )
        ).one()
        total = int(row.total or 0)
        out_of_stock = int(row.out or 0)
        low = int(row.low or 0)
        in_stock = total - out_of_stock - low
        return {
            "total": total,
            "in_stock": in_stock,
            "low": low,
            "out": out_of_stock,
            "stock_value": int(row.stock_value or 0),
        }

    def stock_by_group(self, *, limit: int) -> list[tuple[str, int, int]]:
        """Top groups by stock value — one row per display group.

        Blank/`NULL` group names collapse to "سایر" so the chart always
        has a label. Only active products count.
        """
        group_name = func.coalesce(func.nullif(Product.main_group_name, ""), "سایر").label(
            "group_name"
        )
        group_value = func.coalesce(func.sum(Product.stock * Product.price), 0)
        rows = self._session.execute(
            select(
                group_name,
                func.count().label("item_count"),
                group_value.label("stock_value"),
            )
            .where(Product.is_active.is_(True))
            .group_by(group_name)
            .order_by(group_value.desc())
            .limit(max(limit, 1))
        ).all()
        return [(str(name), int(count), int(value)) for name, count, value in rows]

    def catalog_breakdown(self) -> list[tuple[str | None, int, int]]:
        """One row per raw `main_group_name` — the service maps rows to
        top groups (بخش) and brands. Only active products count."""
        group_value = func.coalesce(func.sum(Product.stock * Product.price), 0)
        rows = self._session.execute(
            select(
                Product.main_group_name,
                func.count().label("item_count"),
                group_value.label("stock_value"),
            )
            .where(Product.is_active.is_(True))
            .group_by(Product.main_group_name)
            .order_by(func.count().desc(), Product.main_group_name)
        ).all()
        return [
            (str(name) if name else None, int(count), int(value)) for name, count, value in rows
        ]

    def competitor_coverage(self, *, since: datetime) -> int:
        """Active products with at least one fresh competitor price."""
        price = effective_competitor_price(since)
        return self._session.execute(
            select(func.count(func.distinct(Product.id)))
            .select_from(Product)
            .join(CompetitorListing, CompetitorListing.product_id == Product.id)
            .where(
                Product.is_active.is_(True),
                CompetitorListing.is_active.is_(True),
                price.is_not(None),
            )
        ).scalar_one()

    def competitor_gap_rows(self, *, since: datetime) -> list[CompetitorGapRow]:
        """One row per fresh (product, listing) pair — the service picks
        the best price per product and ranks the gaps."""
        price = effective_competitor_price(since)
        rows = self._session.execute(
            select(
                Product.id,
                Product.name,
                Product.price,
                CompetitorListing.store,
                price.label("comp_price"),
            )
            .join(CompetitorListing, CompetitorListing.product_id == Product.id)
            .where(
                Product.is_active.is_(True),
                CompetitorListing.is_active.is_(True),
                price.is_not(None),
            )
            .order_by(Product.id)
        ).all()
        return [
            CompetitorGapRow(
                product_id=int(product_id),
                name=str(name),
                our_price=float(our_price),
                store=str(store),
                competitor_price=float(comp_price),
            )
            for product_id, name, our_price, store, comp_price in rows
        ]

    def appliance_total(self) -> int:
        """Active لوازم خانگی items — denominator for competitor coverage.

        Mirrors the product-list `top_group` filter: any non-NULL group
        that is neither فرش nor مبلمان.
        """
        return self._session.execute(
            select(func.count())
            .select_from(Product)
            .where(
                Product.is_active.is_(True),
                Product.main_group_name.is_not(None),
                not_(Product.main_group_name.ilike("فرش%")),
                not_(Product.main_group_name.ilike("مبلمان%")),
            )
        ).scalar_one()

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
            current_price = effective_competitor_price(competitor_price_since)
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
        # `page_size=0` means "show all": return every matching row without a
        # limit or offset so the table truly shows the whole filtered list.
        if page_size and page_size > 0:
            start = (page - 1) * page_size
            stmt = base.order_by(order).offset(start).limit(page_size)
        else:
            stmt = base.order_by(order)
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
