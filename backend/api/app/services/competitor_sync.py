"""Bulk competitor-price refresh — one background run over every active link.

Per-listing politeness throttling is bypassed (the user asked for a bulk
refresh); the store-level slot in ``fetch_competitor_price`` still spaces
external requests. Links from different stores are checked concurrently so
one slow store does not serialize the whole run, but each fetch still waits
for its store's slot under ``competitor_prices._lock``. Per-item failures are
recorded on the row and counted, never aborting the run — only an unexpected
crash marks the run as failed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.competitor import CompetitorListing, CompetitorSyncState
from app.repositories.competitor import CompetitorRepository
from app.repositories.competitor_sync import CompetitorSyncStateRepository
from app.services.competitor_check import apply_competitor_check as _apply_check

log = logging.getLogger("charsooq.competitors")

LOCK_SECONDS = 30 * 60
# One worker per store group; the store set is small and fixed by the catalog
# sections (digikala, technolife, sofa, digifresh, torob). Spacing inside a
# store still comes from its own politeness slot, so overlapping stores is safe.
MAX_WORKERS = 5


class CompetitorSyncBusyError(Exception):
    """Another bulk refresh holds the lock."""


@dataclass(frozen=True)
class CompetitorSyncResult:
    checked: int
    updated: int
    failed: int
    skipped: int


class CompetitorSyncService:
    def __init__(
        self,
        session: Session,
        *,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._session = session
        self._session_factory = session_factory
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
        """Check every stale link. Caller already holds the lock.

        Links with a fresh successful price are skipped rather than fetched
        again: a bulk refresh repeated sooner than the configured price TTL
        would otherwise re-spend one politeness slot per link for no new data.
        This is the dominant cost as the link count grows.
        """
        now = datetime.now(UTC)
        try:
            rows = self._listings.list_all()
            ttl = timedelta(hours=get_settings().competitor_price_ttl_hours)
            active: list[CompetitorListing] = []
            skipped = 0
            for row in rows:
                if not row.is_active:
                    skipped += 1
                    continue
                last_success = row.last_success_at
                if last_success is not None:
                    if last_success.tzinfo is None:
                        last_success = last_success.replace(tzinfo=UTC)
                    if now - last_success < ttl:
                        skipped += 1
                        continue
                active.append(row)
            results = self._check_many(active)
        except Exception as exc:  # noqa: BLE001 — record, then let the caller classify
            self._fail(now, exc)
            raise
        result = CompetitorSyncResult(
            checked=len(active),
            updated=sum(1 for ok in results.values() if ok),
            failed=sum(1 for ok in results.values() if not ok),
            skipped=skipped,
        )
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

    def _check_many(self, rows: list[CompetitorListing]) -> dict[int, bool]:
        """Refresh links with one worker per store.

        Every store owns its worker and processes its links sequentially, so
        all stores run in parallel while the per-store politeness slot in
        ``fetch_competitor_price`` still spaces requests within a store. A
        slow or rate-limited store can never hold back a different store,
        which is the dominant cost as the number of links grows.

        With no session factory (tests and direct callers) the check stays
        sequential on the caller's Session. With a factory, each group owns a
        separate Session — SQLAlchemy Sessions are not thread-safe.
        """
        if not rows:
            return {}
        if self._session_factory is None:
            return {row.id: self._check_one(self._session, row.id) for row in rows}

        by_store: dict[str, list[int]] = {}
        for row in rows:
            by_store.setdefault(row.store, []).append(row.id)
        outcomes: dict[int, bool] = {}
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(by_store))) as pool:
            futures = {
                pool.submit(self._check_store, listing_ids): store
                for store, listing_ids in by_store.items()
            }
            for future in as_completed(futures):
                outcomes.update(future.result())
        return outcomes

    def _check_store(self, listing_ids: list[int]) -> dict[int, bool]:
        factory = self._session_factory
        if factory is None:  # pragma: no cover — guarded by _check_many
            raise RuntimeError("session factory is required for concurrent checks")
        results: dict[int, bool] = {}
        # One Session per store group: sequential use inside a single thread,
        # isolated from every other store's transaction.
        with factory() as session:
            for listing_id in listing_ids:
                results[listing_id] = self._check_one(session, listing_id)
                session.commit()
        return results

    @staticmethod
    def _check_one(session: Session, listing_id: int) -> bool:
        repo = CompetitorRepository(session)
        row = repo.get(listing_id)
        if row is None or not row.is_active:
            return False
        ok = _apply_check(row, datetime.now(UTC))
        repo.flush()
        return ok

    def state(self) -> CompetitorSyncState:
        return self._state.get()

    def _fail(self, now: datetime, exc: Exception) -> None:
        self._session.rollback()
        message = f"خطای به‌روزرسانی قیمت رقبا: {exc}"
        self._state.record_failure(attempted_at=now, error=message)
        self._state.release(success=False, error=message)
        log.warning("competitor bulk refresh failed: %s", message)


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
            return CompetitorSyncService(session, session_factory=session_factory).run()
        except CompetitorSyncBusyError:
            return None


__all__ = [
    "LOCK_SECONDS",
    "MAX_WORKERS",
    "CompetitorSyncBusyError",
    "CompetitorSyncResult",
    "CompetitorSyncService",
    "run_scheduled_competitor_sync",
]
