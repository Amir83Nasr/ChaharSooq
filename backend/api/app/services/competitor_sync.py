"""Bulk competitor-price refresh — one background run over every active link.

Per-listing politeness throttling is bypassed (the user asked for a bulk
refresh); the store-level slot in ``fetch_competitor_price`` still spaces
external requests. Per-item failures are recorded on the row and counted,
never aborting the run — only an unexpected crash marks the run as failed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.integrations.competitor_prices import PriceFetchError, fetch_competitor_price
from app.models.competitor import CompetitorListing, CompetitorSyncState
from app.repositories.competitor import CompetitorRepository
from app.repositories.competitor_sync import CompetitorSyncStateRepository

log = logging.getLogger("charsooq.competitors")

LOCK_SECONDS = 30 * 60


class CompetitorSyncBusyError(Exception):
    """Another bulk refresh holds the lock."""


@dataclass(frozen=True)
class CompetitorSyncResult:
    checked: int
    updated: int
    failed: int
    skipped: int


class CompetitorSyncService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._listings = CompetitorRepository(session)
        self._state = CompetitorSyncStateRepository(session)

    def acquire(self) -> None:
        """Take the cross-worker lock; only one bulk run may hold it."""
        if not self._state.try_acquire(now=datetime.now(UTC), lock_seconds=LOCK_SECONDS):
            raise CompetitorSyncBusyError("به‌روزرسانی دیگری در حال اجراست")

    def run(self) -> CompetitorSyncResult:
        self.acquire()
        return self.run_acquired()

    def run_acquired(self) -> CompetitorSyncResult:
        """Check every link. Caller already holds the lock."""
        now = datetime.now(UTC)
        try:
            rows = self._listings.list_all()
            checked = updated = failed = skipped = 0
            for row in rows:
                if not row.is_active:
                    skipped += 1
                    continue
                checked += 1
                if _apply_check(row, datetime.now(UTC)):
                    updated += 1
                else:
                    failed += 1
                self._session.flush()
            result = CompetitorSyncResult(
                checked=checked, updated=updated, failed=failed, skipped=skipped
            )
        except Exception as exc:  # noqa: BLE001 — record, then let the caller classify
            self._fail(now, exc)
            raise
        self._state.record_result(
            attempted_at=now,
            checked=result.checked,
            updated=result.updated,
            failed=result.failed,
            skipped=result.skipped,
        )
        self._state.release(success=True)
        log.info(
            "competitor bulk refresh ok: checked=%d updated=%d failed=%d skipped=%d",
            result.checked,
            result.updated,
            result.failed,
            result.skipped,
        )
        return result

    def state(self) -> CompetitorSyncState:
        return self._state.get()

    def _fail(self, now: datetime, exc: Exception) -> None:
        self._session.rollback()
        message = f"خطای به‌روزرسانی قیمت رقبا: {exc}"
        self._state.record_failure(attempted_at=now, error=message)
        self._state.release(success=False, error=message)
        log.warning("competitor bulk refresh failed: %s", message)


def _apply_check(row: CompetitorListing, now: datetime) -> bool:
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


def _due(session: Session, *, interval_minutes: int) -> bool:
    """True unless a previous attempt ran more recently than the interval."""
    last_attempt = CompetitorSyncStateRepository(session).get().last_attempt_at
    if last_attempt is not None:
        if last_attempt.tzinfo is None:
            last_attempt = last_attempt.replace(tzinfo=UTC)
        if datetime.now(UTC) < last_attempt + timedelta(minutes=interval_minutes):
            return False
    return True


def run_scheduled_competitor_sync(
    *,
    session_factory: Callable[[], Session],
    interval_minutes: int,
) -> CompetitorSyncResult | None:
    """One scheduler tick: no-op unless the interval has elapsed.

    A tick that finds the lock held (e.g. a manual run in progress, or a
    previous tick still working through many links) simply skips.
    """
    with session_factory() as session:
        if not _due(session, interval_minutes=interval_minutes):
            return None
        try:
            return CompetitorSyncService(session).run()
        except CompetitorSyncBusyError:
            return None


__all__ = [
    "LOCK_SECONDS",
    "CompetitorSyncBusyError",
    "CompetitorSyncResult",
    "CompetitorSyncService",
    "run_scheduled_competitor_sync",
]
