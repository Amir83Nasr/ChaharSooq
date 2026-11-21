"""Backup metadata, queue, and worker-lease queries — no business rules here."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BackupRecord, BackupState
from app.models.backup import (
    BACKUP_QUEUED,
    BACKUP_RUNNING,
    RESTORE_QUEUED,
    RESTORE_RUNNING,
)
from app.models.base import utcnow

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

STATE_ID = 1


def _claimed(result: object) -> bool:
    """True when a conditional UPDATE changed exactly one row.

    Postgres reports `rowcount`; drivers that return -1 are treated as "not
    claimed", which is the safe answer for a lease or a status transition.
    """
    rowcount = cast("CursorResult[Any]", result).rowcount
    return rowcount == 1


def aware(value: datetime | None) -> datetime | None:
    """Normalize SQLite's naive datetimes for comparisons."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class BackupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── archives ─────────────────────────────────────────────

    def add(self, record: BackupRecord) -> BackupRecord:
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, record_id: int) -> BackupRecord | None:
        return self._session.get(BackupRecord, record_id)

    def list_recent(self, limit: int) -> list[BackupRecord]:
        return list(
            self._session.scalars(
                select(BackupRecord)
                .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
                .limit(limit)
            ).all()
        )

    def last_completed(self) -> BackupRecord | None:
        return self._session.scalars(
            select(BackupRecord)
            .where(BackupRecord.status == "completed")
            .where(BackupRecord.pruned_at.is_(None))
            .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
            .limit(1)
        ).first()

    def last_attempt(self, kinds: Sequence[str]) -> BackupRecord | None:
        """Most recent record of the given kinds, whatever its outcome."""
        return self._session.scalars(
            select(BackupRecord)
            .where(BackupRecord.kind.in_(kinds))
            .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
            .limit(1)
        ).first()

    def pending(self) -> BackupRecord | None:
        """A queued or running archive blocks another manual/scheduled run."""
        return self._session.scalars(
            select(BackupRecord)
            .where(BackupRecord.status.in_((BACKUP_QUEUED, BACKUP_RUNNING)))
            .order_by(BackupRecord.id.asc())
            .limit(1)
        ).first()

    def next_queued(self) -> BackupRecord | None:
        return self._session.scalars(
            select(BackupRecord)
            .where(BackupRecord.status == BACKUP_QUEUED)
            .order_by(BackupRecord.id.asc())
            .limit(1)
        ).first()

    def claim(self, record_id: int, *, from_status: str, to_status: str) -> bool:
        """Conditional status transition; one worker wins a queued row."""
        result = self._session.execute(
            update(BackupRecord)
            .where(BackupRecord.id == record_id, BackupRecord.status == from_status)
            .values(status=to_status)
        )
        return _claimed(result)

    def stale(self, *, before: datetime, status: str) -> list[BackupRecord]:
        return list(
            self._session.scalars(
                select(BackupRecord)
                .where(BackupRecord.status == status)
                .where(BackupRecord.created_at < before)
            ).all()
        )

    def expired(self, *, now: datetime, limit: int = 100) -> list[BackupRecord]:
        return list(
            self._session.scalars(
                select(BackupRecord)
                .where(BackupRecord.status == "completed")
                .where(BackupRecord.pruned_at.is_(None))
                .where(BackupRecord.retention_expires_at.is_not(None))
                .where(BackupRecord.retention_expires_at < now)
                .order_by(BackupRecord.id.asc())
                .limit(limit)
            ).all()
        )

    # ── restore execution ────────────────────────────────────

    def pending_restore(self) -> BackupRecord | None:
        """A queued or running restore blocks another restore or dump run."""
        return self._session.scalars(
            select(BackupRecord)
            .where(BackupRecord.restore_status.in_((RESTORE_QUEUED, RESTORE_RUNNING)))
            .order_by(BackupRecord.id.asc())
            .limit(1)
        ).first()

    def next_queued_restore(self) -> BackupRecord | None:
        return self._session.scalars(
            select(BackupRecord)
            .where(BackupRecord.restore_status == RESTORE_QUEUED)
            .order_by(BackupRecord.id.asc())
            .limit(1)
        ).first()

    def claim_restore(self, record_id: int) -> bool:
        """Conditional status transition; one worker wins a queued restore."""
        result = self._session.execute(
            update(BackupRecord)
            .where(BackupRecord.id == record_id, BackupRecord.restore_status == RESTORE_QUEUED)
            .values(restore_status=RESTORE_RUNNING, restore_started_at=utcnow())
        )
        return _claimed(result)

    def stale_restores(self, *, before: datetime) -> list[BackupRecord]:
        return list(
            self._session.scalars(
                select(BackupRecord)
                .where(BackupRecord.restore_status == RESTORE_RUNNING)
                .where(BackupRecord.restore_started_at < before)
            ).all()
        )

    def restore_blocks_pruning(self, record_id: int) -> bool:
        """An active restore pins the archive until it finishes or fails."""
        return (
            self._session.scalars(
                select(BackupRecord.id)
                .where(BackupRecord.id == record_id)
                .where(BackupRecord.restore_status.in_((RESTORE_QUEUED, RESTORE_RUNNING)))
                .limit(1)
            ).first()
            is not None
        )

    # ── worker lease ─────────────────────────────────────────

    def try_acquire_lease(self, *, now: datetime, seconds: int) -> bool:
        until = now + timedelta(seconds=seconds)
        state = self._session.get(BackupState, STATE_ID)
        if state is None:
            self._session.add(BackupState(id=STATE_ID, lease_until=until))
            try:
                self._session.flush()
            except IntegrityError:
                self._session.rollback()
                return self._acquire_existing(now=now, until=until)
            return True
        return self._acquire_existing(now=now, until=until)

    def _acquire_existing(self, *, now: datetime, until: datetime) -> bool:
        result = self._session.execute(
            update(BackupState)
            .where(BackupState.id == STATE_ID)
            .where(or_(BackupState.lease_until.is_(None), BackupState.lease_until < now))
            .values(lease_until=until)
        )
        return _claimed(result)

    def release_lease(self) -> None:
        state = self._session.get(BackupState, STATE_ID)
        if state is not None:
            state.lease_until = None
            self._session.flush()


__all__ = ["BackupRepository", "aware"]
