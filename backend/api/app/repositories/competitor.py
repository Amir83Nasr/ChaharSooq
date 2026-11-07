"""SQL access for manually managed competitor listings."""

from datetime import datetime
from decimal import Decimal
from typing import Any, NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CompetitorListing, CompetitorPriceObservation, Product


class DailyPriceChange(NamedTuple):
    """Latest observation and the one before the trailing daily window."""

    latest_observed_at: datetime
    previous_price: Decimal | None
    previous_currency: str | None
    previous_observed_at: datetime | None
    price_change_percent: float | None


def _to_toman(price: Decimal, currency: str | None) -> Decimal:
    return price / 10 if currency == "IRR" else price


class CompetitorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def product(self, product_id: int) -> Product | None:
        return self._session.get(Product, product_id)

    def daily_price_changes(self, listing_ids: set[int]) -> dict[int, DailyPriceChange]:
        """Latest and previous daily observation per listing.

        Observations are upserted once per UTC day, so the second row is the
        previous day's snapshot. A listing with only one day of history has no
        change yet; a same-day duplicate from older data is skipped.
        """
        if not listing_ids:
            return {}
        rows = self._session.execute(self._ranked_observations(listing_ids)).all()
        by_listing: dict[int, list[tuple[int, Decimal, str, datetime]]] = {}
        for row in rows:
            by_listing.setdefault(int(row.listing_id), []).append(
                (int(row.id), row.price, row.currency, row.observed_at)
            )
        changes: dict[int, DailyPriceChange] = {}
        for listing_id, observations in by_listing.items():
            latest_id, latest_price, latest_currency, latest_at = observations[0]
            previous: tuple[int, Decimal, str, datetime] | None = None
            for candidate in observations[1:]:
                if candidate[3].date() < latest_at.date():
                    previous = candidate
                    break
            if previous is None:
                changes[listing_id] = DailyPriceChange(
                    latest_observed_at=latest_at,
                    previous_price=None,
                    previous_currency=None,
                    previous_observed_at=None,
                    price_change_percent=None,
                )
                continue
            previous_id, previous_price, previous_currency, previous_at = previous
            change: float | None = None
            if previous_id != latest_id:
                latest_toman = _to_toman(latest_price, latest_currency)
                previous_toman = _to_toman(previous_price, previous_currency)
                if previous_toman > 0:
                    change = round(
                        float((latest_toman - previous_toman) / previous_toman * 100),
                        4,
                    )
            changes[listing_id] = DailyPriceChange(
                latest_observed_at=latest_at,
                previous_price=previous_price,
                previous_currency=previous_currency,
                previous_observed_at=previous_at,
                price_change_percent=change,
            )
        return changes

    def _ranked_observations(self, listing_ids: set[int]) -> Any:
        observations = CompetitorPriceObservation
        rank = func.row_number().over(
            partition_by=observations.listing_id,
            order_by=(observations.observed_at.desc(), observations.id.desc()),
        )
        stmt = select(
            observations.id,
            observations.listing_id,
            observations.price,
            observations.currency,
            observations.observed_at,
            rank.label("rn"),
        ).where(
            observations.listing_id.in_(listing_ids),
            observations.price.is_not(None),
        )
        ranked = stmt.subquery()
        return (
            select(
                ranked.c.id,
                ranked.c.listing_id,
                ranked.c.price,
                ranked.c.currency,
                ranked.c.observed_at,
            )
            .where(ranked.c.rn <= 2)
            .order_by(ranked.c.listing_id, ranked.c.rn)
        )

    def list_for_product(self, product_id: int) -> list[CompetitorListing]:
        return list(
            self._session.execute(
                select(CompetitorListing)
                .where(CompetitorListing.product_id == product_id)
                .order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def list_for_products(self, product_ids: set[int]) -> list[CompetitorListing]:
        if not product_ids:
            return []
        return list(
            self._session.execute(
                select(CompetitorListing)
                .where(
                    CompetitorListing.product_id.in_(product_ids),
                    CompetitorListing.is_active.is_(True),
                )
                .order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def list_active(self) -> list[CompetitorListing]:
        return list(
            self._session.execute(
                select(CompetitorListing)
                .where(CompetitorListing.is_active.is_(True))
                .order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def list_all(self) -> list[CompetitorListing]:
        return list(
            self._session.execute(
                select(CompetitorListing).order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def get(self, listing_id: int) -> CompetitorListing | None:
        return self._session.get(CompetitorListing, listing_id)

    def get_by_product_store(
        self, product_id: int, store: str, exclude_id: int | None = None
    ) -> CompetitorListing | None:
        query = select(CompetitorListing).where(
            CompetitorListing.product_id == product_id,
            CompetitorListing.store == store,
        )
        if exclude_id is not None:
            query = query.where(CompetitorListing.id != exclude_id)
        return self._session.execute(query).scalars().first()

    def add(self, listing: CompetitorListing) -> CompetitorListing:
        self._session.add(listing)
        self._session.flush()
        return listing

    def delete(self, listing: CompetitorListing) -> None:
        self._session.delete(listing)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
