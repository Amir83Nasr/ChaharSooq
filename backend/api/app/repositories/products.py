"""Product repository — filters, paging, summary aggregate."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast

from sqlalchemy import ColumnElement, and_, case, exists, func, not_, or_, select, update
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import Case

from app.models import CompetitorListing, Product

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

ProductSort = Literal["newest", "cheapest", "most_expensive"]


class ProductFilters(NamedTuple):
    """Every product filter, shared by the paged list and the CSV export."""

    query: str
    category_id: int | None
    top_group: str | None
    main_group: str | None
    min_price: int | None
    max_price: int | None
    competitor_store: str | None
    min_competitor_price: int | None
    max_competitor_price: int | None
    competitor_price_since: datetime
    min_stock: int | None
    max_stock: int | None
    in_stock: bool | None


# Safety cap for the "show all" path (page_size=0): never serialize an
# unbounded result set — the UI windows rows but the API still builds them.
SHOW_ALL_MAX = 2000


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


def product_base_criteria(filters: ProductFilters) -> list[ColumnElement[bool]]:
    """Product WHERE clauses without competitor-price EXISTS checks.

    Competitor export joins `competitor_listings` itself, so a correlated
    price EXISTS would resolve against the wrong table there.
    """
    criteria: list[ColumnElement[bool]] = [Product.is_active.is_(True)]
    if filters.query:
        like = f"%{filters.query}%"
        criteria.append(
            or_(
                Product.name.ilike(like),
                Product.sku.ilike(like),
                Product.main_group_name.ilike(like),
                Product.sub_group_name.ilike(like),
            )
        )
    if filters.category_id is not None:
        criteria.append(Product.category_id == filters.category_id)
    if filters.main_group:
        criteria.append(Product.main_group_name == filters.main_group)
    if filters.top_group:
        if filters.top_group == "فرش":
            criteria.append(Product.main_group_name.ilike("فرش%"))
        elif filters.top_group == "مبلمان":
            criteria.append(Product.main_group_name.ilike("مبلمان%"))
        elif filters.top_group == "لوازم خانگی":
            criteria.append(Product.main_group_name.is_not(None))
            criteria.append(not_(Product.main_group_name.ilike("فرش%")))
            criteria.append(not_(Product.main_group_name.ilike("مبلمان%")))
    if filters.min_price is not None:
        criteria.append(Product.price >= filters.min_price)
    if filters.max_price is not None:
        criteria.append(Product.price <= filters.max_price)
    if filters.in_stock is True:
        criteria.append(Product.stock > 0)
    elif filters.in_stock is False:
        criteria.append(Product.stock <= 0)
    if filters.min_stock is not None:
        criteria.append(Product.stock >= filters.min_stock)
    if filters.max_stock is not None:
        criteria.append(Product.stock <= filters.max_stock)
    return criteria


def product_criteria(filters: ProductFilters) -> list[ColumnElement[bool]]:
    """WHERE clauses for one product list query (list + export share these)."""
    criteria = product_base_criteria(filters)
    if (
        filters.competitor_store
        or filters.min_competitor_price is not None
        or filters.max_competitor_price is not None
    ):
        current_price = effective_competitor_price(filters.competitor_price_since)
        price_criteria: list[ColumnElement[bool]] = [
            CompetitorListing.product_id == Product.id,
            CompetitorListing.is_active.is_(True),
            current_price.is_not(None),
        ]
        if filters.competitor_store:
            price_criteria.append(CompetitorListing.store == filters.competitor_store)
        if filters.min_competitor_price is not None:
            price_criteria.append(current_price >= filters.min_competitor_price)
        if filters.max_competitor_price is not None:
            price_criteria.append(current_price <= filters.max_competitor_price)
        criteria.append(exists(select(1).where(*price_criteria)))
    return criteria


def product_order(sort: ProductSort) -> ColumnElement[Any]:
    return {
        "newest": Product.id.desc(),
        "cheapest": Product.price.asc(),
        "most_expensive": Product.price.desc(),
    }[sort]


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

    def deactivate_missing(self, keep_external_ids: set[int]) -> int:
        """Soft-delete every active mirror row absent from a *complete* source listing.

        The catalog is an exact mirror of the source (CSV in development,
        Parsina in production): manual rows (`external_id IS NULL`) are also
        deactivated when they are not in the listing, otherwise the table
        can never shrink back to the source.

        Bulk UPDATE (no ORM object load) — one round-trip even for 10k rows.
        """
        criteria: list[ColumnElement[bool]] = [Product.is_active.is_(True)]
        if keep_external_ids:
            # NULL never matches NOT IN (three-valued logic), so manual rows
            # need an explicit IS NULL branch — otherwise they survive forever.
            criteria.append(
                or_(
                    Product.external_id.is_(None),
                    Product.external_id.not_in(keep_external_ids),
                )
            )
        result = self._session.execute(update(Product).where(*criteria).values(is_active=False))
        # UPDATE rowcount is reliable on PostgreSQL and SQLite (unlike SELECT,
        # which reports -1 on SQLite) — same cast pattern as SyncStateRepository.
        return cast("CursorResult[Any]", result).rowcount or 0

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

    def coverage_and_appliance_total(self, *, since: datetime) -> tuple[int, int]:
        """Competitor coverage + لوازم خانگی denominator in ONE round-trip.

        Replaces the two former single-purpose COUNT helpers
        (`competitor_coverage`, `appliance_total`): two scalar subqueries
        instead of two round-trips, so the dashboard overview costs 3
        (summary, groups, this) not 4.

        Both sides share the appliance filter: carpet/furniture track the
        linked product's daily change instead of a direct competitor price,
        so counting them in the numerator would push the KPI past 100%.
        """
        appliance_criteria: tuple[ColumnElement[bool], ...] = (
            Product.is_active.is_(True),
            Product.main_group_name.is_not(None),
            not_(Product.main_group_name.ilike("فرش%")),
            not_(Product.main_group_name.ilike("مبلمان%")),
        )
        price = effective_competitor_price(since)
        coverage_sq = (
            select(func.count(func.distinct(Product.id)))
            .select_from(Product)
            .join(CompetitorListing, CompetitorListing.product_id == Product.id)
            .where(
                *appliance_criteria,
                CompetitorListing.is_active.is_(True),
                price.is_not(None),
            )
            .scalar_subquery()
        )
        appliance_sq = (
            select(func.count()).select_from(Product).where(*appliance_criteria).scalar_subquery()
        )
        row = self._session.execute(select(coverage_sq, appliance_sq)).one()
        return int(row[0] or 0), int(row[1] or 0)

    def _filtered(self, filters: ProductFilters) -> tuple[Select[Product], Select[int]]:
        base = select(Product).options(joinedload(Product.category))
        count_stmt = select(func.count()).select_from(Product)
        for criterion in product_criteria(filters):
            base = base.where(criterion)
            count_stmt = count_stmt.where(criterion)
        return base, count_stmt

    def count(self, *, filters: ProductFilters) -> int:
        _, count_stmt = self._filtered(filters)
        return int(self._session.execute(count_stmt).scalar_one())

    def list(
        self,
        *,
        filters: ProductFilters,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        base, count_stmt = self._filtered(filters)
        total = int(self._session.execute(count_stmt).scalar_one())
        stmt = base.order_by(product_order(sort))
        # `page_size=0` means "show all": capped (never unbounded) with no
        # offset so the table truly shows the whole filtered list up to the cap.
        if page_size and page_size > 0:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        else:
            stmt = stmt.limit(SHOW_ALL_MAX)
        rows = self._session.execute(stmt).unique().scalars().all()
        return list(rows), total

    def iter_batches(
        self,
        *,
        filters: ProductFilters,
        sort: ProductSort,
        batch_size: int = 500,
    ) -> Iterator[list[Product]]:
        """Stream every matching product for CSV export (no show-all cap).

        The caller applies the export ceiling; batching keeps competitor-price
        lookups and CSV buffers bounded for a large catalog.
        """
        stmt = (
            self._filtered(filters)[0]
            .order_by(product_order(sort))
            .execution_options(yield_per=batch_size)
        )
        batch: list[Product] = []
        for product in self._session.scalars(stmt):
            batch.append(product)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def add(self, product: Product) -> Product:
        self._session.add(product)
        self._session.flush()
        return product

    def get(self, product_id: int) -> Product | None:
        return self._session.get(Product, product_id)

    def update_price_bounds(
        self,
        product: Product,
        *,
        allowed_decrease_percent: Decimal | None,
        allowed_increase_percent: Decimal | None,
    ) -> None:
        product.allowed_decrease_percent = allowed_decrease_percent
        product.allowed_increase_percent = allowed_increase_percent
        self._session.flush()

    def stage(self, product: Product) -> Product:
        """Attach a new row without flushing — caller flushes in bulk."""
        self._session.add(product)
        return product
