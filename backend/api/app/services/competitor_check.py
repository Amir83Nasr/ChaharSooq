"""Shared competitor row refresh — single place for fetch + row mutation.

Both the manual per-listing check (``CompetitorService``) and the bulk
background refresh (``CompetitorSyncService``) apply the same rule: record
``last_checked_at``, map ``PriceFetchError`` to a row status, otherwise store
the fetched price/currency/stock. Keeping it here avoids the two services
drifting apart.
"""

from datetime import datetime

from app.integrations.competitor_prices import PriceFetchError, fetch_competitor_price
from app.models.competitor import CompetitorListing, CompetitorPriceObservation


def apply_competitor_check(row: CompetitorListing, now: datetime) -> bool:
    """Refresh one row in place; True when the fetch succeeded."""
    row.last_checked_at = now
    try:
        result = fetch_competitor_price(row.store, row.url)
    except PriceFetchError as exc:
        row.status = exc.status
        row.last_error = str(exc)[:500]
        return False
    observed_at = result.observed_at or now
    row.fetched_price = result.amount
    row.fetched_currency = result.currency
    row.fetched_in_stock = result.in_stock
    row.last_success_at = observed_at
    row.status = "success"
    row.last_error = None
    if result.amount is not None and result.currency is not None:
        # One observation per UTC day: repeated checks update today's snapshot
        # instead of flooding the table, while yesterday's row stays available
        # as the daily-change baseline.
        existing = next(
            (
                observation
                for observation in row.price_observations
                if observation.observed_at.date() == observed_at.date()
            ),
            None,
        )
        if existing is not None:
            existing.price = result.amount
            existing.currency = result.currency
            existing.in_stock = result.in_stock
            existing.observed_at = observed_at
        else:
            row.price_observations.append(
                CompetitorPriceObservation(
                    price=result.amount,
                    currency=result.currency,
                    in_stock=result.in_stock,
                    observed_at=observed_at,
                )
            )
    return True
