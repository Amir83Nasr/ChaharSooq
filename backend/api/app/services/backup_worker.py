"""Backup/restore execution — one DB-leased worker, manual and scheduled.

A dump uses the application role and the pinned PostgreSQL client tools; a
restore is *data-only* into the existing schema, in one transaction:

1. a pre-restore archive is written and verified,
2. business tables are emptied in dependency order,
3. matching table data is loaded from the chosen archive,
4. sequences are advanced and the owner's backup settings are preserved,
5. the whole script commits atomically (``ON_ERROR_STOP`` + one transaction).

A failure rolls the data back, so the running shop is never left half-restored.
Authentication tables and backup metadata are deliberately excluded: logins and
the backup history belong to the environment, not to a shop-data snapshot.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.backup_storage import (
    archive_path,
    ensure_backup_dir,
    existing_archive,
    new_archive_name,
    remove_quietly,
    sha256_file,
)
from app.core.config import get_database_settings, get_settings
from app.core.database import get_engine
from app.integrations.pg_tools import PG_TOOLS, PgToolError, PgTools
from app.models import BackupRecord
from app.models.backup import (
    BACKUP_COMPLETED,
    BACKUP_FAILED,
    BACKUP_KINDS,
    BACKUP_PRE_RESTORE,
    BACKUP_QUEUED,
    BACKUP_RUNNING,
    BACKUP_SCHEDULED,
    PG_RESTORE_LIST,
    RESTORE_COMPLETED,
    RESTORE_FAILED,
    VERIFICATION_VERIFIED,
)
from app.models.base import utcnow
from app.repositories import BackupRepository
from app.repositories.backups import aware
from app.services.backups import RETENTION_DAYS
from app.services.settings import SettingsService

log = logging.getLogger("charsooq.backup")

#: Shop data restored from an archive. Auth, sessions, backup metadata, and
#: Alembic bookkeeping stay untouched.
RESTORE_LOAD_ORDER: tuple[str, ...] = (
    "categories",
    "products",
    "competitor_listings",
    "competitor_price_observations",
    "competitor_sync_state",
    "parsina_sync_state",
    "suggested_price_formulas",
    "settings",
    "ai_config",
)
#: Children before parents; independent tables last.
RESTORE_DELETE_ORDER: tuple[str, ...] = (
    "competitor_price_observations",
    "competitor_listings",
    "products",
    "categories",
    "suggested_price_formulas",
    "parsina_sync_state",
    "competitor_sync_state",
    "settings",
    "ai_config",
)
#: Never self-reference: backup metadata and live sessions are environment state.
#: ``alembic_version`` is excluded because the application role deliberately has
#: no grant on it (provisioning revokes it), so dumping its rows would fail.
DUMP_EXCLUDED_TABLE_DATA: tuple[str, ...] = (
    "backup_records",
    "backup_state",
    "admin_sessions",
    "alembic_version",
)
STALE_GRACE_SECONDS = 600
TICK_SECONDS = 5

#: Reasons shown to the owner as stable codes; the UI maps them to Persian.
RESTORE_PRE_BACKUP_FAILED = "pre_restore_failed"
RESTORE_ARCHIVE_MISSING = "archive_missing"
RESTORE_INTERRUPTED = "interrupted"
BACKUP_INTERRUPTED = "interrupted"


class BackupWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        tools: PgTools | None = None,
        directory: Path | None = None,
        engine: Engine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._tools = tools if tools is not None else PG_TOOLS
        self._directory = directory
        self._engine = engine
        self._timeout = get_settings().backup_timeout_seconds
        # A restore can run a pre-restore dump and then the restore script, so
        # the lease covers both bounded steps before another worker may take over.
        self._lease_seconds = 2 * self._timeout + STALE_GRACE_SECONDS

    # ── public entry points ──────────────────────────────────

    def tick(self) -> bool:
        """Run at most one pending restore or backup; return whether work ran."""
        now = utcnow()
        if not self._acquire_lease(now):
            return False
        try:
            self._cleanup_stale(now)
            self._enqueue_due(now)
            restore_id = self._claim_restore()
            if restore_id is not None:
                self._execute_restore(restore_id)
                return True
            record_id = self._claim_backup()
            if record_id is not None:
                self._execute_backup(record_id)
                return True
            self._prune(now)
            return False
        finally:
            self._release_lease()

    def prune(self) -> int:
        """Delete expired archive files; return how many files were pruned."""
        with self._session_factory() as session:
            repo = BackupRepository(session)
            count = self._prune_with(repo, utcnow())
            session.commit()
            return count

    # ── lease / queue ────────────────────────────────────────

    def _acquire_lease(self, now: datetime) -> bool:
        with self._session_factory() as session:
            try:
                acquired = BackupRepository(session).try_acquire_lease(
                    now=now, seconds=self._lease_seconds
                )
                session.commit()
                return acquired
            except SQLAlchemyError:
                session.rollback()
                log.exception("backup lease acquisition failed")
                return False

    def _release_lease(self) -> None:
        with self._session_factory() as session:
            try:
                BackupRepository(session).release_lease()
                session.commit()
            except SQLAlchemyError:  # pragma: no cover — lease expires anyway
                session.rollback()

    def _enqueue_due(self, now: datetime) -> None:
        with self._session_factory() as session:
            repo = BackupRepository(session)
            service = SettingsService(session)
            if not service.get_backup_enabled():
                return
            if not self._tools.available() or not self._directory_writable():
                # Nothing to gain from queuing a run that must fail: Staging has
                # no client tools, and a broken volume is reported in settings.
                return
            if repo.pending() is not None or repo.pending_restore() is not None:
                return
            # Any archive produced since the last check satisfies the schedule:
            # a manual dump, an upload, or the safety dump written before a
            # restore all reset the interval. Counting only scheduled attempts
            # queues a second, automatic archive right after every owner action.
            last = repo.last_attempt(BACKUP_KINDS)
            if last is not None:
                created = aware(last.created_at)
                if created is not None and now < created + timedelta(
                    minutes=service.get_backup_interval_minutes()
                ):
                    return
            repo.add(BackupRecord(kind=BACKUP_SCHEDULED, status=BACKUP_QUEUED))
            session.commit()

    def _claim_backup(self) -> int | None:
        with self._session_factory() as session:
            repo = BackupRepository(session)
            record = repo.next_queued()
            if record is None:
                return None
            if not repo.claim(record.id, from_status=BACKUP_QUEUED, to_status=BACKUP_RUNNING):
                return None
            record.storage_ref = new_archive_name(record.kind, record.id)
            record.source_revision = self._current_revision()
            session.commit()
            return record.id

    def _claim_restore(self) -> int | None:
        with self._session_factory() as session:
            repo = BackupRepository(session)
            record = repo.next_queued_restore()
            if record is None:
                return None
            if not repo.claim_restore(record.id):
                return None
            session.commit()
            return record.id

    # ── backup ───────────────────────────────────────────────

    def _execute_backup(self, record_id: int) -> None:
        self._run_dump(record_id)
        self.prune()

    def _run_dump(self, record_id: int) -> bool:
        with self._session_factory() as session:
            record = BackupRepository(session).get(record_id)
            if record is None or not record.storage_ref:
                return False
            kind = record.kind
            storage_ref = record.storage_ref
        self._archive_directory()
        target = archive_path(storage_ref, directory=self._directory)
        if target is None:
            # The stored basename is not safe; never build a path from it.
            self._mark_backup_failed(record_id, "storage_unavailable")
            return False
        try:
            size = self._tools.dump(
                get_database_settings().database_url,
                target,
                exclude_table_data=DUMP_EXCLUDED_TABLE_DATA,
            )
            self._tools.verify(target)
            os.chmod(target, 0o600)
        except PgToolError as error:
            remove_quietly(target)
            self._mark_backup_failed(record_id, error.code)
            return False
        except Exception:  # noqa: BLE001 — a crash must fail the record, not the worker
            remove_quietly(target)
            log.exception("backup dump crashed id=%s", record_id)
            self._mark_backup_failed(record_id, "dump_failed")
            return False

        with self._session_factory() as session:
            record = BackupRepository(session).get(record_id)
            if record is None:
                return False
            now = utcnow()
            record.status = BACKUP_COMPLETED
            record.size_bytes = size
            record.sha256 = sha256_file(target)
            record.verification = VERIFICATION_VERIFIED
            record.verification_method = PG_RESTORE_LIST
            record.finished_at = now
            record.retention_expires_at = now + timedelta(days=RETENTION_DAYS)
            record.error_code = None
            session.commit()
        log.info("backup completed id=%s kind=%s size=%s", record_id, kind, size)
        return True

    def _mark_backup_failed(self, record_id: int, code: str) -> None:
        with self._session_factory() as session:
            record = BackupRepository(session).get(record_id)
            if record is None:
                return
            record.status = BACKUP_FAILED
            record.error_code = code[:64]
            record.finished_at = utcnow()
            session.commit()
        log.warning("backup failed id=%s code=%s", record_id, code)

    # ── restore ──────────────────────────────────────────────

    def _execute_restore(self, backup_id: int) -> None:
        storage_ref: str | None
        pruned_at: datetime | None
        with self._session_factory() as session:
            record = BackupRepository(session).get(backup_id)
            storage_ref = record.storage_ref if record is not None else None
            pruned_at = record.pruned_at if record is not None else None

        if storage_ref is None or pruned_at is not None:
            self._fail_restore(backup_id, RESTORE_ARCHIVE_MISSING)
            return
        archive = existing_archive(storage_ref, directory=self._directory)
        if archive is None:
            self._fail_restore(backup_id, RESTORE_ARCHIVE_MISSING)
            return

        pre_id = self._create_running_backup(BACKUP_PRE_RESTORE)
        if pre_id is None or not self._run_dump(pre_id):
            self._fail_restore(backup_id, RESTORE_PRE_BACKUP_FAILED)
            return

        script = self._archive_directory() / f".restore-{backup_id}-{uuid.uuid4().hex}.sql"
        try:
            self._build_restore_script(archive, script)
            self._tools.run_script(get_database_settings().database_url, script)
        except PgToolError as error:
            self._fail_restore(backup_id, error.code)
            return
        except Exception:  # noqa: BLE001 — the transaction rolled back; report it
            log.exception("restore crashed backup=%s", backup_id)
            self._fail_restore(backup_id, "restore_failed")
            return
        finally:
            remove_quietly(script)

        with self._session_factory() as session:
            record = BackupRepository(session).get(backup_id)
            if record is not None:
                now = utcnow()
                record.restore_status = RESTORE_COMPLETED
                record.restore_finished_at = now
                record.restored_at = now
                record.restore_error_code = None
                session.commit()
        log.info("restore completed backup=%s", backup_id)

    def _create_running_backup(self, kind: str) -> int | None:
        with self._session_factory() as session:
            repo = BackupRepository(session)
            record = repo.add(
                BackupRecord(
                    kind=kind,
                    status=BACKUP_RUNNING,
                    source_revision=self._current_revision(),
                )
            )
            record.storage_ref = new_archive_name(kind, record.id)
            session.commit()
            return record.id

    def _build_restore_script(self, archive: Path, script: Path) -> None:
        toc = self._tools.verify(archive)
        present = self._tools.table_data_tables(toc)
        if "products" not in present:
            raise PgToolError("archive_invalid")
        loadable = [table for table in RESTORE_LOAD_ORDER if table in present]
        settings = self._capture_backup_settings()

        os.chmod(script.parent, 0o700)
        # Binary mode: pg_restore writes raw COPY blocks into the same file.
        with script.open("wb") as handle:
            os.chmod(script, 0o600)
            handle.write(b"BEGIN;\n")
            handle.write(b"SET LOCAL statement_timeout = 0;\n")
            handle.write(b"SET LOCAL lock_timeout = '15s';\n")
            handle.write(b"SET LOCAL idle_in_transaction_session_timeout = 0;\n")
            for table in RESTORE_DELETE_ORDER:
                if table in present:
                    handle.write(f'DELETE FROM public."{table}";\n'.encode())
            # pg_restore writes straight to the same file descriptor via
            # `--file=-`. Flush our buffered DELETEs first, otherwise the COPY
            # blocks land on disk before them and every id collides with a
            # still-present row.
            handle.flush()
            self._tools.append_table_data(archive, loadable, handle)
            handle.flush()
            for statement in self._sequence_statements(loadable):
                handle.write(f"{statement}\n".encode())
            for key, value in settings.items():
                escaped = value.replace("'", "''")
                handle.write(
                    (
                        "INSERT INTO public.settings (key, value) "
                        f"VALUES ('{key}', '{escaped}') "
                        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;\n"
                    ).encode()
                )
            handle.write(b"COMMIT;\n")

    def _capture_backup_settings(self) -> dict[str, str]:
        with self._session_factory() as session:
            service = SettingsService(session)
            return {
                "backup_enabled": "true" if service.get_backup_enabled() else "false",
                "backup_interval_minutes": str(service.get_backup_interval_minutes()),
            }

    def _sequence_statements(self, tables: list[str]) -> list[str]:
        engine = self._engine or get_engine()
        if engine.dialect.name != "postgresql":
            return []
        query = text(
            """
            SELECT s.relname AS sequence_name, t.relname AS table_name, a.attname AS column_name
            FROM pg_class AS s
            JOIN pg_depend AS d
              ON d.objid = s.oid
             AND d.classid = 'pg_class'::regclass
             AND d.refclassid = 'pg_class'::regclass
             AND d.deptype IN ('a', 'i')
            JOIN pg_class AS t ON t.oid = d.refobjid
            JOIN pg_attribute AS a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
            JOIN pg_namespace AS n ON n.oid = s.relnamespace
            WHERE s.relkind = 'S' AND n.nspname = 'public'
            """
        )
        statements: list[str] = []
        with engine.connect() as connection:
            for sequence, table, column in connection.execute(query).all():
                if table not in tables:
                    continue
                sequence_name = f'public."{sequence}"'
                table_name = f'public."{table}"'
                column_name = f'"{column}"'
                statements.append(
                    "SELECT pg_catalog.setval("
                    f"'{sequence_name}', "
                    f"COALESCE((SELECT max({column_name}) FROM {table_name}), 0) + 1, false);"
                )
        return statements

    def _fail_restore(self, backup_id: int, code: str) -> None:
        with self._session_factory() as session:
            record = BackupRepository(session).get(backup_id)
            if record is None:
                return
            record.restore_status = RESTORE_FAILED
            record.restore_error_code = code[:64]
            record.restore_finished_at = utcnow()
            session.commit()
        log.warning("restore failed backup=%s code=%s", backup_id, code)

    # ── cleanup / retention ──────────────────────────────────

    def _cleanup_stale(self, now: datetime) -> None:
        threshold = now - timedelta(seconds=self._lease_seconds)
        with self._session_factory() as session:
            repo = BackupRepository(session)
            for record in repo.stale(before=threshold, status=BACKUP_RUNNING):
                record.status = BACKUP_FAILED
                record.error_code = BACKUP_INTERRUPTED
                record.finished_at = now
            for record in repo.stale_restores(before=threshold):
                record.restore_status = RESTORE_FAILED
                record.restore_error_code = RESTORE_INTERRUPTED
                record.restore_finished_at = now
            session.commit()
        self._remove_stale_partials(now)

    def _prune(self, now: datetime) -> int:
        with self._session_factory() as session:
            count = self._prune_with(BackupRepository(session), now)
            session.commit()
            return count

    def _prune_with(self, repo: BackupRepository, now: datetime) -> int:
        count = 0
        for record in repo.expired(now=now):
            if repo.restore_blocks_pruning(record.id):
                continue
            remove_quietly(existing_archive(record.storage_ref, directory=self._directory))
            record.pruned_at = now
            count += 1
        return count

    def _remove_stale_partials(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self._lease_seconds)
        directory = self._archive_directory()
        if not directory.is_dir():
            return
        for pattern in (".upload-*.part", ".restore-*.sql", "*.partial"):
            for path in directory.glob(pattern):
                try:
                    if datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff:
                        path.unlink(missing_ok=True)
                except OSError:  # pragma: no cover — racing cleanup is harmless
                    continue

    # ── helpers ──────────────────────────────────────────────

    def _current_revision(self) -> str | None:
        engine = self._engine or get_engine()
        try:
            with engine.connect() as connection:
                value = connection.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar()
            return str(value) if value else None
        except SQLAlchemyError:
            # The application role has no grant on alembic_version; that is fine.
            return None

    def _archive_directory(self) -> Path:
        if self._directory is not None:
            self._directory.mkdir(parents=True, exist_ok=True)
            return self._directory
        return ensure_backup_dir()

    def _directory_writable(self) -> bool:
        try:
            directory = self._archive_directory()
        except OSError:
            return False
        return os.access(directory, os.W_OK | os.X_OK)


def build_worker(session_factory: Callable[[], Session]) -> BackupWorker:
    return BackupWorker(session_factory)


__all__ = [
    "BackupWorker",
    "DUMP_EXCLUDED_TABLE_DATA",
    "RESTORE_DELETE_ORDER",
    "RESTORE_LOAD_ORDER",
    "TICK_SECONDS",
    "build_worker",
]
