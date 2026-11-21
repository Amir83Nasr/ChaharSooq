"""Owner-facing backup settings, archive operations, and direct restore.

The owner queues work here; ``app.services.backup_worker`` executes it. Nothing
in this module writes data outside the archive directory, and no method can
delete or restore production data without a validated archive. Explicit archive
deletion only removes a stored copy and its metadata, never shop data.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO, Literal

from sqlalchemy.orm import Session

from app.core.backup_storage import (
    archive_path,
    backup_dir,
    ensure_backup_dir,
    existing_archive,
    new_archive_name,
    remove_quietly,
    sha256_file,
    storage_ready,
    upload_archive_name,
)
from app.core.config import get_settings
from app.integrations.pg_tools import PG_TOOLS, PgToolError, PgTools
from app.models import BackupRecord
from app.models.backup import (
    BACKUP_COMPLETED,
    BACKUP_OPERATOR,
    BACKUP_QUEUED,
    BACKUP_RUNNING,
    BACKUP_UPLOADED,
    PG_RESTORE_LIST,
    RESTORE_QUEUED,
    VERIFICATION_PENDING,
    VERIFICATION_VERIFIED,
)
from app.models.base import utcnow
from app.repositories import BackupRepository
from app.services.settings import SettingsService

RETENTION_DAYS = 30
BACKUP_LIST_LIMIT = 50
UPLOAD_CHUNK_BYTES = 1024 * 1024

RequestRejection = Literal[
    "not_found",
    "not_verified",
    "pending_exists",
    "file_missing",
    "backup_pending",
    "backup_running",
    "restore_running",
]
UnavailableReason = Literal["tools_unavailable", "storage_unavailable"]


class BackupRequestError(Exception):
    """The requested backup action is not allowed in the current state."""

    def __init__(self, reason: RequestRejection) -> None:
        self.reason = reason
        super().__init__(reason)


class BackupUnavailableError(Exception):
    """The host cannot produce or store an archive right now."""

    def __init__(self, reason: UnavailableReason) -> None:
        self.reason = reason
        super().__init__(reason)


class InvalidArchiveError(Exception):
    """An uploaded file is not a usable pg_dump custom archive."""

    def __init__(self, code: str = "archive_invalid") -> None:
        self.code = code
        super().__init__(code)


class UploadTooLargeError(Exception):
    """The uploaded archive exceeds the configured cap."""


class BackupService:
    def __init__(
        self,
        session: Session,
        *,
        tools: PgTools | None = None,
        directory: Path | None = None,
    ) -> None:
        self._session = session
        self._settings = SettingsService(session)
        self._backups = BackupRepository(session)
        self._tools = tools if tools is not None else PG_TOOLS
        self._directory = directory
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)

    # ── owner settings ───────────────────────────────────────

    def settings_view(self) -> dict[str, object]:
        return {
            "enabled": self._settings.get_backup_enabled(),
            "interval_minutes": self._settings.get_backup_interval_minutes(),
            "retention_days": RETENTION_DAYS,
            "verification_method": PG_RESTORE_LIST,
            "tools_available": self._tools.available(),
            "storage_ready": self._storage_ready(),
        }

    def update_settings(
        self, *, enabled: bool | None, interval_minutes: int | None
    ) -> dict[str, object]:
        if enabled is not None:
            self._settings.update_backup_enabled(enabled)
        if interval_minutes is not None:
            self._settings.update_backup_interval_minutes(interval_minutes)
        self._session.commit()
        return self.settings_view()

    def _storage_ready(self) -> bool:
        if self._directory is None:
            return storage_ready()
        return os.access(self._directory, os.W_OK | os.X_OK)

    # ── archives ─────────────────────────────────────────────

    def list_backups(self) -> list[dict[str, object]]:
        return [self.backup_view(row) for row in self._backups.list_recent(BACKUP_LIST_LIMIT)]

    def last_completed(self) -> BackupRecord | None:
        return self._backups.last_completed()

    @staticmethod
    def backup_view(record: BackupRecord) -> dict[str, object]:
        return {
            "id": record.id,
            "created_at": record.created_at,
            "finished_at": record.finished_at,
            "status": record.status,
            "kind": record.kind,
            "size_bytes": record.size_bytes,
            "sha256": record.sha256,
            "verification": record.verification,
            "verification_method": record.verification_method,
            "source_revision": record.source_revision,
            "storage_ref": record.storage_ref,
            "retention_expires_at": record.retention_expires_at,
            "pruned_at": record.pruned_at,
            "error_code": record.error_code,
            "restore_status": record.restore_status,
            "restore_started_at": record.restore_started_at,
            "restore_finished_at": record.restore_finished_at,
            "restore_error_code": record.restore_error_code,
            "restored_at": record.restored_at,
            "downloadable": (
                record.pruned_at is None
                and record.status == BACKUP_COMPLETED
                and existing_archive(record.storage_ref) is not None
            ),
        }

    def queue_manual(self) -> BackupRecord:
        """Queue an owner-triggered dump; the worker runs it within seconds."""
        if self._backups.pending_restore() is not None:
            raise BackupRequestError("pending_exists")
        if self._backups.pending() is not None:
            raise BackupRequestError("pending_exists")
        self._ensure_available()
        record = self._backups.add(BackupRecord(kind=BACKUP_OPERATOR, status=BACKUP_QUEUED))
        self._session.commit()
        return record

    def _ensure_available(self) -> None:
        if not self._tools.available():
            raise BackupUnavailableError("tools_unavailable")
        if not self._storage_ready():
            raise BackupUnavailableError("storage_unavailable")

    # ── upload ───────────────────────────────────────────────

    def save_upload(self, stream: BinaryIO) -> BackupRecord:
        """Stream one archive into storage, verify its TOC, then record it."""
        self._ensure_available()
        settings = get_settings()
        directory = ensure_backup_dir() if self._directory is None else self._directory
        partial = directory / f".upload-{uuid.uuid4().hex}.part"
        digest = hashlib.sha256()
        size = 0
        final_path: Path | None = None
        try:
            with partial.open("wb") as handle:
                os.chmod(partial, 0o600)
                while True:
                    chunk = stream.read(UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > settings.backup_max_upload_bytes:
                        raise UploadTooLargeError
                    digest.update(chunk)
                    handle.write(chunk)
            if size == 0:
                raise InvalidArchiveError("archive_empty")

            try:
                self._tools.verify(partial)
            except PgToolError as error:
                raise InvalidArchiveError(error.code) from None

            final_path = directory / upload_archive_name()
            os.chmod(partial, 0o600)
            os.replace(partial, final_path)
            now = utcnow()
            record = self._backups.add(
                BackupRecord(
                    kind=BACKUP_UPLOADED,
                    status=BACKUP_COMPLETED,
                    size_bytes=size,
                    sha256=digest.hexdigest(),
                    verification=VERIFICATION_VERIFIED,
                    verification_method=PG_RESTORE_LIST,
                    storage_ref=final_path.name,
                    finished_at=now,
                    retention_expires_at=now + timedelta(days=RETENTION_DAYS),
                )
            )
            self._session.commit()
            return record
        except Exception:
            remove_quietly(partial)
            remove_quietly(final_path)
            raise

    def download_path(self, record_id: int) -> Path | None:
        record = self._backups.get(record_id)
        if record is None or record.status != BACKUP_COMPLETED or record.pruned_at is not None:
            return None
        return existing_archive(record.storage_ref)

    def archive_name(self, record_id: int) -> str | None:
        record = self._backups.get(record_id)
        if record is None or record.pruned_at is not None:
            return None
        path = archive_path(record.storage_ref)
        return path.name if path is not None else None

    def delete_backup(self, record_id: int) -> None:
        """Permanently remove one archive and its metadata, never shop data."""
        record = self._backups.get(record_id)
        if record is None:
            raise BackupRequestError("not_found")
        if record.status in (BACKUP_QUEUED, BACKUP_RUNNING):
            raise BackupRequestError("backup_running")
        if self._backups.restore_blocks_pruning(record_id):
            raise BackupRequestError("restore_running")
        path = existing_archive(record.storage_ref, directory=self._directory)
        self._session.delete(record)
        self._session.commit()
        remove_quietly(path)

    # ── direct restore ───────────────────────────────────────

    def start_restore(self, backup_id: int) -> BackupRecord:
        """Queue a transactional data restore from one verified local archive."""
        record = self._backups.get(backup_id)
        if record is None or record.status != BACKUP_COMPLETED or record.pruned_at is not None:
            raise BackupRequestError("not_found")
        if record.verification != VERIFICATION_VERIFIED:
            raise BackupRequestError("not_verified")
        if existing_archive(record.storage_ref) is None:
            raise BackupRequestError("file_missing")
        if self._backups.pending_restore() is not None:
            raise BackupRequestError("restore_running")
        if self._backups.pending() is not None:
            raise BackupRequestError("backup_pending")
        record.restore_status = RESTORE_QUEUED
        record.restore_started_at = None
        record.restore_finished_at = None
        record.restore_error_code = None
        record.restored_at = None
        self._session.commit()
        return record

    # ── host CLI helpers ─────────────────────────────────────

    def create_record(self, *, kind: str, status: str, storage_ref: str | None) -> BackupRecord:
        """Create an archive row for a host-driven dump (CLI/pre-restore)."""
        record = self._backups.add(BackupRecord(kind=kind, status=status, storage_ref=storage_ref))
        self._session.commit()
        return record

    def finish_record(
        self, record_id: int, *, size_bytes: int, sha256: str, source_revision: str | None
    ) -> BackupRecord:
        record = self._backups.get(record_id)
        if record is None:
            raise BackupRequestError("not_found")
        record.status = BACKUP_COMPLETED
        record.size_bytes = size_bytes
        record.sha256 = sha256
        record.source_revision = source_revision
        record.finished_at = utcnow()
        record.retention_expires_at = utcnow() + timedelta(days=RETENTION_DAYS)
        self._session.commit()
        return record

    def mark_verified(self, record_id: int, method: str = PG_RESTORE_LIST) -> BackupRecord:
        record = self._backups.get(record_id)
        if record is None or record.status != BACKUP_COMPLETED:
            raise BackupRequestError("not_found")
        record.verification = VERIFICATION_VERIFIED
        record.verification_method = method
        self._session.commit()
        return record

    def fail_record(self, record_id: int, error_code: str) -> BackupRecord:
        record = self._backups.get(record_id)
        if record is None:
            raise BackupRequestError("not_found")
        record.status = "failed"
        record.error_code = error_code[:64]
        record.finished_at = utcnow()
        self._session.commit()
        return record

    @staticmethod
    def sha256(path: Path) -> str:
        return sha256_file(path)

    @staticmethod
    def name_for(kind: str, record_id: int) -> str:
        return new_archive_name(kind, record_id)

    @staticmethod
    def archive_directory() -> Path:
        return backup_dir()


# Re-exported for the routes' success/failure mapping and for tests.
__all__ = [
    "BACKUP_LIST_LIMIT",
    "BackupRequestError",
    "BackupService",
    "BackupUnavailableError",
    "InvalidArchiveError",
    "RETENTION_DAYS",
    "UploadTooLargeError",
    "VERIFICATION_PENDING",
    "PG_RESTORE_LIST",
]
