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

from app.models.competitor import CompetitorSyncState
from app.repositories.competitor import CompetitorRepository
from app.repositories.competitor_sync import CompetitorSyncStateRepository
from app.services.competitor_check import apply_competitor_check as _apply_check

log = logging.getLogger("charsooq.competitors")

LOCK_SECONDS = 30 * 60
# Bounded concurrency: enough to overlap independent stores without flooding
# sockets or tripping a store's rate limit (spacing itself is per store).
MAX_WORKERS = 4


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
        """Check every link. Caller already holds the lock."""
        now = datetime.now(UTC)
        try:
            rows = self._listings.list_all()
            active = [row for row in rows if row.is_active]
            skipped = len(rows) - len(active)
            active_ids = [row.id for row in active]
            results = self._check_many(active_ids)
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

    def _check_many(self, listing_ids: list[int]) -> dict[int, bool]:
        """Refresh links concurrently, each in its own transaction.

        When a session factory is available (production), every worker owns a
        separate Session — SQLAlchemy Sessions are not thread-safe. Without a
        factory (tests and callers that pass an in-memory Session) the check
        runs sequentially on the caller's Session so behavior stays identical.
        The store-level slot in ``fetch_competitor_price`` is process-global
        and thread-safe, so concurrent workers still respect politeness.
        """
        if not listing_ids:
            return {}
        if self._session_factory is None:
            return {
                listing_id: self._check_one(self._session, listing_id) for listing_id in listing_ids
            }
        outcomes: dict[int, bool] = {}
        workers = min(MAX_WORKERS, len(listing_ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._check_in_session, listing_id): listing_id
                for listing_id in listing_ids
            }
            for future in as_completed(futures):
                listing_id = futures[future]
                outcomes[listing_id] = future.result()
        return outcomes

    def _check_in_session(self, listing_id: int) -> bool:
        factory = self._session_factory
        if factory is None:  # pragma: no cover — guarded by _check_many
            raise RuntimeError("session factory is required for concurrent checks")
        with factory() as session:
            ok = self._check_one(session, listing_id)
            session.commit()
            return ok

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
