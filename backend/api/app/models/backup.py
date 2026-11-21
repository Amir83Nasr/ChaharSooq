"""Backup metadata and restore execution state — no archive bytes or credentials.

Archives are produced and consumed by the API worker (ADR 023); these tables
record what the owner sees and what the worker is allowed to do next.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import utcnow

BACKUP_QUEUED = "queued"
BACKUP_RUNNING = "running"
BACKUP_COMPLETED = "completed"
BACKUP_FAILED = "failed"
BACKUP_STATUSES = (BACKUP_QUEUED, BACKUP_RUNNING, BACKUP_COMPLETED, BACKUP_FAILED)

BACKUP_SCHEDULED = "scheduled"
BACKUP_OPERATOR = "operator"
BACKUP_UPLOADED = "uploaded"
BACKUP_PRE_RESTORE = "pre_restore"
BACKUP_KINDS = (BACKUP_SCHEDULED, BACKUP_OPERATOR, BACKUP_UPLOADED, BACKUP_PRE_RESTORE)

VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"
VERIFICATION_FAILED = "failed"
VERIFICATION_STATUSES = (VERIFICATION_PENDING, VERIFICATION_VERIFIED, VERIFICATION_FAILED)

DECRYPT_LIST = "decrypt_list"
DRILL_RESTORE = "drill_restore"
PG_RESTORE_LIST = "pg_restore_list"
VERIFICATION_METHODS = (DECRYPT_LIST, DRILL_RESTORE, PG_RESTORE_LIST)

RESTORE_QUEUED = "queued"
RESTORE_RUNNING = "running"
RESTORE_COMPLETED = "completed"
RESTORE_FAILED = "failed"
RESTORE_STATUSES = (RESTORE_QUEUED, RESTORE_RUNNING, RESTORE_COMPLETED, RESTORE_FAILED)


class BackupRecord(Base):
    """One logical pg_dump archive, verified and retained by the API worker."""

    __tablename__ = "backup_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_backup_records_status",
        ),
        CheckConstraint(
            "verification IN ('pending', 'verified', 'failed')",
            name="ck_backup_records_verification",
        ),
        CheckConstraint(
            "restore_status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_backup_records_restore_status",
        ),
        Index("ix_backup_records_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=BACKUP_RUNNING, server_default=BACKUP_RUNNING
    )
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=BACKUP_SCHEDULED, server_default=BACKUP_SCHEDULED
    )
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=VERIFICATION_PENDING,
        server_default=VERIFICATION_PENDING,
    )
    verification_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Archive basename only: never a filesystem path, secret, or credential.
    storage_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when the archive file was removed after retention; metadata stays so
    # the owner can still see that the version existed.
    pruned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Stable machine code, never raw stderr from pg_dump or the encryptor.
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Restore state lives on the archive itself (ADR 026); no request table.
    restore_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    restore_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    restore_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    restore_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BackupState(Base):
    """Single-row worker lease so only one dump/restore runs at a time.

    An expired lease is reclaimable, so a crashed API worker cannot block
    backups forever. Migration 0021 inserts the singleton row.
    """

    __tablename__ = "backup_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
