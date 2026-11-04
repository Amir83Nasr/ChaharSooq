"""Bulk-refresh state repository — single-row lock + run bookkeeping.

Mirrors the Parsina sync-state compare-and-swap so only one bulk competitor
refresh (manual button) can hold the lock at a time.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.models.competitor import COMPETITOR_SYNC_STATE_ID, CompetitorSyncState

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult


def _acquired_by_us(state: CompetitorSyncState | None, now: datetime) -> bool:
    if state is None or state.running_since is None:
        return False
    acquired_at = state.running_since
    if acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=UTC)
    return acquired_at == now


class CompetitorSyncStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_state(self) -> CompetitorSyncState:
        state = self._session.get(CompetitorSyncState, COMPETITOR_SYNC_STATE_ID)
        if state is None:
            state = CompetitorSyncState(id=COMPETITOR_SYNC_STATE_ID)
            self._session.add(state)
            self._session.flush()
        return state

    def try_acquire(self, *, now: datetime, lock_seconds: int) -> bool:
        """Atomic compare-and-swap: only one bulk run wins the lock."""
        self.ensure_state()
        self._session.commit()
        result = self._session.execute(
            update(CompetitorSyncState)
            .where(
                CompetitorSyncState.id == COMPETITOR_SYNC_STATE_ID,
                or_(
                    CompetitorSyncState.lock_until.is_(None),
                    CompetitorSyncState.lock_until < now,
                ),
            )
            .values(lock_until=now + timedelta(seconds=lock_seconds), running_since=now)
            .execution_options(synchronize_session="fetch")
        )
        self._session.commit()
        rowcount = cast("CursorResult[Any]", result).rowcount
        if rowcount >= 0:
            return rowcount == 1
        state = self._session.get(CompetitorSyncState, COMPETITOR_SYNC_STATE_ID)
        return _acquired_by_us(state, now)

    def release(self, *, success: bool, error: str | None = None) -> None:
        state = self.ensure_state()
        state.lock_until = None
        state.running_since = None
        if not success:
            state.last_error = (error or "خطای نامشخص")[:500]
        self._session.commit()

    def record_result(
        self,
        *,
        attempted_at: datetime,
        checked: int,
        updated: int,
        failed: int,
        skipped: int,
    ) -> None:
        state = self.ensure_state()
        state.last_attempt_at = attempted_at
        state.last_success_at = attempted_at
        state.last_error = None
        state.last_checked = checked
        state.last_updated = updated
        state.last_failed = failed
        state.last_skipped = skipped
        self._session.commit()

    def record_failure(self, *, attempted_at: datetime, error: str) -> None:
        state = self.ensure_state()
        state.last_attempt_at = attempted_at
        state.last_error = error[:500]
        self._session.commit()

    def get(self) -> CompetitorSyncState:
        return self.ensure_state()
