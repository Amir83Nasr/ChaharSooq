"""Shared competitor row refresh — single place for fetch + row mutation.

Both the manual per-listing check (``CompetitorService``) and the bulk
background refresh (``CompetitorSyncService``) apply the same rule: record
``last_checked_at``, map ``PriceFetchError`` to a row status, otherwise store
the fetched price/currency/stock. Keeping it here avoids the two services
drifting apart.
"""

from datetime import datetime

from app.integrations.competitor_prices import PriceFetchError, fetch_competitor_price
from app.models.competitor import CompetitorListing


def apply_competitor_check(row: CompetitorListing, now: datetime) -> bool:
    """Refresh one row in place; True when the fetch succeeded."""
    row.last_checked_at = now
    try:
        result = fetch_competitor_price(row.store, row.url)
    except PriceFetchError as exc:
        row.status = exc.status
        row.last_error = str(exc)[:500]
        return False
    row.fetched_price = result.amount
    row.fetched_currency = result.currency
    row.fetched_in_stock = result.in_stock
    row.last_success_at = result.observed_at or now
    row.status = "success"
    row.last_error = None
    return True
