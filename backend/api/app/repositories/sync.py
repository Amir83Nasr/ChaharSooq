"""Sync-state repository — single-row lock + attempt/success bookkeeping."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.models import ParsinaSyncState
from app.models.parsina import SYNC_STATE_ID

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult


class SyncStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_state(self) -> ParsinaSyncState:
        state = self._session.get(ParsinaSyncState, SYNC_STATE_ID)
        if state is None:
            state = ParsinaSyncState(id=SYNC_STATE_ID)
            self._session.add(state)
            self._session.flush()
        return state

    def try_acquire(self, *, now: datetime, lock_seconds: int) -> bool:
        """Atomic compare-and-swap: only one row/worker wins the lock.

        Those reads only happen when another transaction holds the lock row —
        the conditional UPDATE itself blocks until its value is known.
        """
        self.ensure_state()
        self._session.commit()
        result = self._session.execute(
            update(ParsinaSyncState)
            .where(
                ParsinaSyncState.id == SYNC_STATE_ID,
                or_(
                    ParsinaSyncState.lock_until.is_(None),
                    ParsinaSyncState.lock_until < now,
                ),
            )
            .values(lock_until=now + timedelta(seconds=lock_seconds), running_since=now)
            # Keep the in-session row fresh: callers read status right after.
            .execution_options(synchronize_session="fetch")
        )
        self._session.commit()
        # Postgres reports rowcount; SQLite can return -1 when unknown.
        rowcount = cast("CursorResult[Any]", result).rowcount
        if rowcount >= 0:
            return rowcount == 1
        state = self._session.get(ParsinaSyncState, SYNC_STATE_ID)
        return state is not None and state.running_since == now

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
        processed: int,
        created: int,
        updated: int,
        deactivated: int,
        skipped: int,
    ) -> None:
        state = self.ensure_state()
        state.last_attempt_at = attempted_at
        state.last_success_at = attempted_at
        state.last_error = None
        state.last_processed = processed
        state.last_created = created
        state.last_updated = updated
        state.last_deactivated = deactivated
        state.last_skipped = skipped
        self._session.commit()

    def record_failure(self, *, attempted_at: datetime, error: str) -> None:
        state = self.ensure_state()
        state.last_attempt_at = attempted_at
        state.last_error = error[:500]
        self._session.commit()

    def get(self) -> ParsinaSyncState:
        return self.ensure_state()
