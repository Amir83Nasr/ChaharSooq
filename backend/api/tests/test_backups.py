"""Owner backups: settings, upload/download, queue, worker execution, restore.

The PostgreSQL client binaries are replaced by ``FakePgTools`` so the tests
never need a real server or a ``psql`` install. The archive directory comes
from the per-test ``BACKUP_DIR`` set by the ``client`` fixture.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.backup_storage import ensure_backup_dir
from app.core.database import get_engine
from app.integrations.pg_tools import PgToolError, PgTools
from app.models import BackupRecord
from app.models.backup import (
    BACKUP_COMPLETED,
    BACKUP_FAILED,
    BACKUP_OPERATOR,
    BACKUP_PRE_RESTORE,
    BACKUP_QUEUED,
    BACKUP_RUNNING,
    BACKUP_SCHEDULED,
    PG_RESTORE_LIST,
    RESTORE_COMPLETED,
    RESTORE_FAILED,
    RESTORE_QUEUED,
    RESTORE_RUNNING,
)
from app.models.base import utcnow
from app.repositories import BackupRepository
from app.services import BackupService
from app.services.backup_worker import BackupWorker
from app.services.settings import SettingsService
from tests.helpers import login, login_owner

SETTINGS_URL = "/api/v1/settings/backup"
BACKUPS_URL = "/api/v1/backups"


def _restore_url(backup_id: int) -> str:
    return f"{BACKUPS_URL}/{backup_id}/restore"


ARCHIVE_BYTES = b"PGDMP\x01fake custom-format archive"
TOC = [
    "5; 0 0 TABLE DATA public categories charsooq",
    "6; 0 0 TABLE DATA public products charsooq",
    "7; 0 0 TABLE DATA public competitor_listings charsooq",
    "8; 0 0 TABLE DATA public settings charsooq",
]


class FakePgTools(PgTools):
    """Deterministic stand-in for pg_dump/pg_restore/psql."""

    def __init__(
        self,
        *,
        available: bool = True,
        fail_dump: bool = False,
        fail_script: bool = False,
    ) -> None:
        super().__init__(timeout_seconds=60)
        self._available = available
        self._fail_dump = fail_dump
        self._fail_script = fail_script
        self.dumps: list[tuple[str, set[str]]] = []
        self.scripts: list[bytes] = []
        self.data_requests: list[list[str]] = []

    def available(self) -> bool:
        return self._available

    def dump(
        self,
        database_url: str,
        target: Path,
        *,
        exclude_table_data: Sequence[str] = (),
    ) -> int:
        if self._fail_dump:
            raise PgToolError("dump_failed")
        self.dumps.append((database_url, set(exclude_table_data)))
        target.write_bytes(ARCHIVE_BYTES)
        os.chmod(target, 0o600)
        return target.stat().st_size

    def verify(self, archive: Path) -> list[str]:
        if not archive.is_file() or archive.read_bytes() != ARCHIVE_BYTES:
            raise PgToolError("archive_invalid")
        return list(TOC)

    def table_data_tables(self, toc: Sequence[str]) -> set[str]:
        return {line.split()[6] for line in toc if "TABLE DATA" in line}

    def append_table_data(self, archive: Path, tables: Sequence[str], sink: BinaryIO) -> None:
        self.data_requests.append(list(tables))
        for table in tables:
            sink.write(f"COPY public.{table} (id) FROM stdin;\n".encode())
            sink.write(b"\\.\n")

    def run_script(self, database_url: str, script: Path) -> None:
        self.scripts.append(script.read_bytes())
        if self._fail_script:
            raise PgToolError("restore_failed")


@pytest.fixture()
def tools(monkeypatch: pytest.MonkeyPatch) -> FakePgTools:
    fake = FakePgTools()
    monkeypatch.setattr("app.services.backups.PG_TOOLS", fake)
    monkeypatch.setattr("app.services.backup_worker.PG_TOOLS", fake)
    return fake


@pytest.fixture()
def archive_dir() -> Path:
    return ensure_backup_dir()


def _verified_record(
    *,
    directory: Path,
    verified: bool = True,
    storage_ref: str = "charsooq-scheduled-20260101T000000Z-1.dump",
    with_file: bool = True,
) -> int:
    """Create a finished archive record through the host-side service helpers."""
    if with_file:
        (directory / storage_ref).write_bytes(ARCHIVE_BYTES)
    with Session(get_engine()) as session:
        service = BackupService(session, tools=FakePgTools(), directory=directory)
        record = service.create_record(
            kind=BACKUP_SCHEDULED, status=BACKUP_QUEUED, storage_ref=storage_ref
        )
        service.finish_record(
            record.id, size_bytes=len(ARCHIVE_BYTES), sha256="a" * 64, source_revision=None
        )
        if verified:
            service.mark_verified(record.id)
        return record.id


def test_backup_settings_are_owner_only(client: TestClient, tools: FakePgTools) -> None:
    assert client.get(SETTINGS_URL).status_code == 401
    login(client)
    for response in (
        client.get(SETTINGS_URL),
        client.put(SETTINGS_URL, json={"enabled": True}),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"

    login_owner(client)
    response = client.get(SETTINGS_URL)
    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "interval_minutes": 720,
        "retention_days": 30,
        "verification_method": PG_RESTORE_LIST,
        "tools_available": True,
        "storage_ready": True,
    }
    # General settings stay readable by every role and leak no backup keys.
    general = client.get("/api/v1/settings").json()
    assert "backup_enabled" not in general
    assert "backup_interval_minutes" not in general


def test_backup_settings_report_unavailable_tools(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.backups.PG_TOOLS", FakePgTools(available=False))
    login_owner(client)
    body = client.get(SETTINGS_URL).json()
    assert body["tools_available"] is False
    assert body["storage_ready"] is True


def test_owner_updates_backup_settings_with_validated_interval(
    client: TestClient, tools: FakePgTools
) -> None:
    login_owner(client)
    response = client.put(SETTINGS_URL, json={"enabled": False, "interval_minutes": 120})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["interval_minutes"] == 120
    assert client.get(SETTINGS_URL).json()["interval_minutes"] == 120

    for minutes in (59, 10081):
        invalid = client.put(SETTINGS_URL, json={"interval_minutes": minutes})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"


def test_owner_queues_a_manual_backup(client: TestClient, tools: FakePgTools) -> None:
    login_owner(client)
    response = client.post(BACKUPS_URL)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == BACKUP_QUEUED
    assert body["kind"] == BACKUP_OPERATOR
    assert body["downloadable"] is False

    duplicate = client.post(BACKUPS_URL)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"

    login(client)
    assert client.post(BACKUPS_URL).status_code == 403


def test_manual_backup_refuses_when_tools_are_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.backups.PG_TOOLS", FakePgTools(available=False))
    login_owner(client)
    response = client.post(BACKUPS_URL)
    assert response.status_code == 409
    assert "PostgreSQL" in response.json()["error"]["message"]


def test_upload_stores_and_verifies_an_archive(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    login_owner(client)
    response = client.post(
        "/api/v1/backups/upload",
        files={"file": ("snapshot.dump", ARCHIVE_BYTES, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "uploaded"
    assert body["status"] == BACKUP_COMPLETED
    assert body["verification"] == "verified"
    assert body["verification_method"] == PG_RESTORE_LIST
    assert body["size_bytes"] == len(ARCHIVE_BYTES)
    assert body["downloadable"] is True

    stored = sorted(archive_dir.glob("*.dump"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == ARCHIVE_BYTES
    assert (stored[0].stat().st_mode & 0o777) == 0o600


def test_upload_rejects_invalid_archives(client: TestClient, tools: FakePgTools) -> None:
    login_owner(client)
    response = client.post(
        "/api/v1/backups/upload",
        files={"file": ("bad.dump", b"not an archive", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_upload_rejects_archives_over_the_cap(
    client: TestClient, tools: FakePgTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TinySettings:
        backup_max_upload_bytes = 8

    monkeypatch.setattr("app.services.backups.get_settings", lambda: TinySettings())
    login_owner(client)
    response = client.post(
        "/api/v1/backups/upload",
        files={"file": ("big.dump", b"x" * 9, "application/octet-stream")},
    )
    assert response.status_code == 413


def test_download_is_owner_only_and_confined_to_storage(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    backup_id = _verified_record(directory=archive_dir)
    login_owner(client)

    response = client.get(f"{BACKUPS_URL}/{backup_id}/download")
    assert response.status_code == 200
    assert response.content == ARCHIVE_BYTES
    assert "attachment" in response.headers["content-disposition"]

    assert client.get(f"{BACKUPS_URL}/9999/download").status_code == 404

    login(client)
    assert client.get(f"{BACKUPS_URL}/{backup_id}/download").status_code == 403


def test_download_rejects_path_traversal(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    record_id = _verified_record(directory=archive_dir)
    with Session(get_engine()) as session:
        record = session.get(BackupRecord, record_id)
        assert record is not None
        record.storage_ref = "../secrets.dump"
        session.commit()

    login_owner(client)
    assert client.get(f"{BACKUPS_URL}/{record_id}/download").status_code == 404


def test_owner_deletes_an_archive_and_its_metadata(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    backup_id = _verified_record(directory=archive_dir)
    assert len(list(archive_dir.glob("*.dump"))) == 1
    login_owner(client)

    response = client.delete(f"{BACKUPS_URL}/{backup_id}")
    assert response.status_code == 204, response.text
    assert all(row["id"] != backup_id for row in client.get(BACKUPS_URL).json())
    assert list(archive_dir.glob("*.dump")) == []
    assert client.delete(f"{BACKUPS_URL}/{backup_id}").status_code == 404


def test_migration_releases_archives_pinned_by_legacy_restore_requests(
    client: TestClient,
    tools: FakePgTools,
    archive_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_id = _verified_record(directory=archive_dir)
    with Session(get_engine()) as session:
        session.execute(text("PRAGMA foreign_keys = ON"))
        session.execute(
            text(
                "CREATE TABLE backup_restore_requests ("
                "id INTEGER PRIMARY KEY, "
                "backup_record_id INTEGER NOT NULL REFERENCES backup_records(id) "
                "ON DELETE RESTRICT, "
                "status VARCHAR(16) NOT NULL)"
            )
        )
        session.execute(
            text(
                "INSERT INTO backup_restore_requests (id, backup_record_id, status) "
                "VALUES (1, :backup_id, 'failed')"
            ),
            {"backup_id": backup_id},
        )
        session.commit()

    # Before the migration the obsolete request pins the archive at the database.
    with pytest.raises(IntegrityError):
        with Session(get_engine()) as session:
            session.execute(text("PRAGMA foreign_keys = ON"))
            record = session.get(BackupRecord, backup_id)
            assert record is not None
            session.delete(record)
            session.commit()

    migration = importlib.import_module("migrations.versions.0022_remove_restore_requests")

    class _DropOp:
        @staticmethod
        def execute(statement: str) -> None:
            with get_engine().begin() as connection:
                connection.exec_driver_sql(statement)

    monkeypatch.setattr(migration, "op", _DropOp())
    migration.upgrade()

    assert not inspect(get_engine()).has_table("backup_restore_requests")
    login_owner(client)
    assert client.delete(f"{BACKUPS_URL}/{backup_id}").status_code == 204
    assert all(row["id"] != backup_id for row in client.get(BACKUPS_URL).json())


def test_delete_is_owner_only(client: TestClient, tools: FakePgTools, archive_dir: Path) -> None:
    backup_id = _verified_record(directory=archive_dir)
    assert client.delete(f"{BACKUPS_URL}/{backup_id}").status_code == 401

    login(client)
    assert client.delete(f"{BACKUPS_URL}/{backup_id}").status_code == 403
    assert list(archive_dir.glob("*.dump"))


def test_delete_refuses_an_archive_with_an_active_restore(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    backup_id = _verified_record(directory=archive_dir)
    login_owner(client)
    assert client.post(_restore_url(backup_id)).status_code == 202

    response = client.delete(f"{BACKUPS_URL}/{backup_id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert list(archive_dir.glob("*.dump"))
    assert any(row["id"] == backup_id for row in client.get(BACKUPS_URL).json())

    # A completed or failed restore is history, not a pin: deletion is allowed.
    with Session(get_engine()) as session:
        record = session.get(BackupRecord, backup_id)
        assert record is not None
        record.restore_status = RESTORE_FAILED
        session.commit()
    assert client.delete(f"{BACKUPS_URL}/{backup_id}").status_code == 204
    assert list(archive_dir.glob("*.dump")) == []


def test_delete_refuses_a_backup_still_running(client: TestClient, tools: FakePgTools) -> None:
    with Session(get_engine()) as session:
        record = BackupRepository(session).add(
            BackupRecord(kind=BACKUP_SCHEDULED, status=BACKUP_QUEUED)
        )
        record_id = record.id
        session.commit()

    login_owner(client)
    assert client.delete(f"{BACKUPS_URL}/{record_id}").status_code == 409


def test_restore_requires_a_verified_local_archive(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    verified_id = _verified_record(directory=archive_dir)
    unverified_id = _verified_record(
        directory=archive_dir,
        verified=False,
        storage_ref="charsooq-scheduled-20260101T000000Z-2.dump",
    )
    missing_id = _verified_record(
        directory=archive_dir,
        with_file=False,
        storage_ref="charsooq-scheduled-20260101T000000Z-3.dump",
    )
    login_owner(client)

    for backup_id, expected in (
        (9999, 404),
        (unverified_id, 409),
        (missing_id, 409),
    ):
        response = client.post(_restore_url(backup_id))
        assert response.status_code == expected, response.text

    created = client.post(_restore_url(verified_id))
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["id"] == verified_id
    assert body["restore_status"] == RESTORE_QUEUED
    assert body["restore_started_at"] is None
    assert body["restore_finished_at"] is None
    assert body["restore_error_code"] is None
    assert body["restored_at"] is None

    listed = next(row for row in client.get(BACKUPS_URL).json() if row["id"] == verified_id)
    assert listed["restore_status"] == RESTORE_QUEUED

    duplicate = client.post(_restore_url(verified_id))
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message"] == "بازیابی دیگری در حال اجرا است"


def test_restore_rejects_pruned_and_pending_archives(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    pruned_id = _verified_record(directory=archive_dir)
    with Session(get_engine()) as session:
        pruned = session.get(BackupRecord, pruned_id)
        assert pruned is not None
        pruned.pruned_at = utcnow()
        queued = BackupRepository(session).add(
            BackupRecord(kind=BACKUP_SCHEDULED, status=BACKUP_QUEUED)
        )
        queued_id = queued.id
        session.commit()

    login_owner(client)
    assert client.post(_restore_url(pruned_id)).status_code == 404
    assert client.post(_restore_url(queued_id)).status_code == 404


def test_restore_blocks_while_a_backup_is_pending(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    backup_id = _verified_record(directory=archive_dir)
    login_owner(client)
    assert client.post(BACKUPS_URL).status_code == 202
    response = client.post(_restore_url(backup_id))
    assert response.status_code == 409


def test_only_one_restore_can_be_queued_at_a_time(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    first_id = _verified_record(directory=archive_dir)
    second_id = _verified_record(
        directory=archive_dir, storage_ref="charsooq-scheduled-20260101T000000Z-2.dump"
    )
    login_owner(client)
    assert client.post(_restore_url(first_id)).status_code == 202
    assert client.post(_restore_url(second_id)).status_code == 409


def test_restore_is_owner_only(client: TestClient, tools: FakePgTools, archive_dir: Path) -> None:
    backup_id = _verified_record(directory=archive_dir)
    assert client.post(_restore_url(backup_id)).status_code == 401

    login(client)
    assert client.get(BACKUPS_URL).status_code == 403
    assert client.post(_restore_url(backup_id)).status_code == 403
    assert client.post(BACKUPS_URL).status_code == 403


def _worker(tools: FakePgTools, directory: Path) -> BackupWorker:
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return BackupWorker(factory, tools=tools, directory=directory)


def test_worker_completes_a_queued_manual_backup(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    login_owner(client)
    queued = client.post(BACKUPS_URL).json()
    assert _worker(tools, archive_dir).tick() is True

    rows = client.get(BACKUPS_URL).json()
    row = next(item for item in rows if item["id"] == queued["id"])
    assert row["status"] == BACKUP_COMPLETED
    assert row["verification"] == "verified"
    assert row["verification_method"] == PG_RESTORE_LIST
    assert row["size_bytes"] == len(ARCHIVE_BYTES)
    assert row["sha256"] is not None
    assert row["downloadable"] is True
    assert row["retention_expires_at"] is not None
    assert row["source_revision"] is None

    # Authentication, sessions, and backup metadata never leak into a shop dump.
    assert tools.dumps
    _, excluded = tools.dumps[0]
    assert {"admin_sessions", "backup_records", "backup_state", "alembic_version"} <= excluded
    assert "backup_restore_requests" not in excluded
    assert "admins" not in excluded
    assert inspect(get_engine()).has_table("backup_restore_requests") is False

    stored = list(archive_dir.glob("*.dump"))
    assert len(stored) == 1
    assert (stored[0].stat().st_mode & 0o777) == 0o600


def test_worker_marks_a_failed_dump(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, archive_dir: Path
) -> None:
    failing = FakePgTools(fail_dump=True)
    monkeypatch.setattr("app.services.backups.PG_TOOLS", failing)
    login_owner(client)
    queued = client.post(BACKUPS_URL).json()

    assert _worker(failing, archive_dir).tick() is True
    row = next(item for item in client.get(BACKUPS_URL).json() if item["id"] == queued["id"])
    assert row["status"] == BACKUP_FAILED
    assert row["error_code"] == "dump_failed"
    assert row["downloadable"] is False


def test_worker_creates_due_scheduled_backups(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    with Session(get_engine()) as session:
        SettingsService(session).update_backup_enabled(True)
        session.commit()

    assert _worker(tools, archive_dir).tick() is True
    login_owner(client)
    rows = client.get(BACKUPS_URL).json()
    assert rows
    assert rows[0]["kind"] == BACKUP_SCHEDULED
    assert rows[0]["status"] == BACKUP_COMPLETED

    # No new attempt before the interval elapses.
    assert _worker(tools, archive_dir).tick() is False
    assert len(client.get(BACKUPS_URL).json()) == 1


def test_worker_restores_data_with_a_pre_restore_archive(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    source_id = _verified_record(directory=archive_dir)
    login_owner(client)
    assert client.post(_restore_url(source_id)).status_code == 202

    worker = _worker(tools, archive_dir)
    assert worker.tick() is True

    done = next(row for row in client.get(BACKUPS_URL).json() if row["id"] == source_id)
    assert done["restore_status"] == RESTORE_COMPLETED
    assert done["restore_started_at"] is not None
    assert done["restore_finished_at"] is not None
    assert done["restored_at"] is not None
    assert done["restore_error_code"] is None

    archives = client.get(BACKUPS_URL).json()
    assert any(row["kind"] == BACKUP_PRE_RESTORE for row in archives)

    script = tools.scripts[-1].decode()
    assert "BEGIN;" in script and script.rstrip().endswith("COMMIT;")
    for table in ("products", "categories", "competitor_listings", "settings"):
        expected = f'DELETE FROM public."{table}";'  # noqa: S608
        assert expected in script
    # Logins and backup metadata are never deleted by a restore.
    assert '"admins"' not in script
    assert '"backup_records"' not in script
    # The owner's own backup policy survives the restore.
    assert "INSERT INTO public.settings (key, value)" in script
    assert "backup_interval_minutes" in script
    assert tools.data_requests[-1] == ["categories", "products", "competitor_listings", "settings"]


def test_worker_rolls_back_a_failed_restore(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, archive_dir: Path
) -> None:
    source_id = _verified_record(directory=archive_dir)
    failing = FakePgTools(fail_script=True)
    login_owner(client)
    assert client.post(_restore_url(source_id)).status_code == 202

    assert _worker(failing, archive_dir).tick() is True
    done = next(row for row in client.get(BACKUPS_URL).json() if row["id"] == source_id)
    assert done["restore_status"] == RESTORE_FAILED
    assert done["restore_error_code"] == "restore_failed"
    assert done["restore_finished_at"] is not None
    assert done["restored_at"] is None


def test_worker_fails_a_restore_whose_archive_disappeared(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    source_id = _verified_record(directory=archive_dir)
    login_owner(client)
    assert client.post(_restore_url(source_id)).status_code == 202
    for path in archive_dir.glob("*.dump"):
        path.unlink()

    assert _worker(tools, archive_dir).tick() is True
    done = next(row for row in client.get(BACKUPS_URL).json() if row["id"] == source_id)
    assert done["restore_status"] == RESTORE_FAILED
    assert done["restore_error_code"] == "archive_missing"


def test_prune_respects_retention_and_pending_restores(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    expired_id = _verified_record(
        directory=archive_dir, storage_ref="charsooq-scheduled-20260101T000000Z-4.dump"
    )
    kept_id = _verified_record(
        directory=archive_dir, storage_ref="charsooq-scheduled-20260101T000000Z-5.dump"
    )
    with Session(get_engine()) as session:
        expired = session.get(BackupRecord, expired_id)
        kept = session.get(BackupRecord, kept_id)
        assert expired is not None and kept is not None
        expired.retention_expires_at = utcnow() - timedelta(days=1)
        kept.retention_expires_at = utcnow() + timedelta(days=1)
        session.commit()

    login_owner(client)
    assert client.post(_restore_url(expired_id)).status_code == 202

    # An active restore pins its archive even after retention.
    assert _worker(tools, archive_dir).prune() == 0
    assert (archive_dir / "charsooq-scheduled-20260101T000000Z-4.dump").exists()

    with Session(get_engine()) as session:
        expired = session.get(BackupRecord, expired_id)
        assert expired is not None
        expired.restore_status = RESTORE_FAILED
        session.commit()
    assert _worker(tools, archive_dir).prune() == 1
    assert not (archive_dir / "charsooq-scheduled-20260101T000000Z-4.dump").exists()

    rows = {row["id"]: row for row in client.get(BACKUPS_URL).json()}
    assert rows[expired_id]["pruned_at"] is not None
    assert rows[expired_id]["downloadable"] is False
    assert rows[kept_id]["pruned_at"] is None
    assert rows[kept_id]["downloadable"] is True


def test_stale_running_work_is_marked_interrupted(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    with Session(get_engine()) as session:
        repo = BackupRepository(session)
        stale = repo.add(BackupRecord(kind=BACKUP_SCHEDULED, status=BACKUP_RUNNING))
        stale.created_at = utcnow() - timedelta(days=1)
        stale_id = stale.id
        stale_restore = repo.add(
            BackupRecord(
                kind=BACKUP_SCHEDULED,
                status=BACKUP_COMPLETED,
                restore_status=RESTORE_RUNNING,
                restore_started_at=utcnow() - timedelta(days=1),
            )
        )
        stale_restore_id = stale_restore.id
        session.commit()

    _worker(tools, archive_dir).tick()
    with Session(get_engine()) as session:
        row = session.get(BackupRecord, stale_id)
        assert row is not None
        assert row.status == BACKUP_FAILED
        assert row.error_code == "interrupted"
        restore = session.get(BackupRecord, stale_restore_id)
        assert restore is not None
        assert restore.restore_status == RESTORE_FAILED
        assert restore.restore_error_code == "interrupted"
        assert restore.restore_finished_at is not None


def test_cli_helpers_finish_a_host_driven_record(archive_dir: Path) -> None:
    with Session(get_engine()) as session:
        service = BackupService(session, tools=FakePgTools(), directory=archive_dir)
        record = service.create_record(
            kind=BACKUP_SCHEDULED, status=BACKUP_RUNNING, storage_ref="host.dump"
        )
        (archive_dir / "host.dump").write_bytes(ARCHIVE_BYTES)
        service.finish_record(
            record.id,
            size_bytes=len(ARCHIVE_BYTES),
            sha256=service.sha256(archive_dir / "host.dump"),
            source_revision="24a9f2d",
        )
        service.mark_verified(record.id)
        record = service.mark_verified(record.id)
        assert record.status == BACKUP_COMPLETED
        assert record.verification == "verified"
        assert service.last_completed() is not None
        assert service.download_path(record.id) == archive_dir / "host.dump"


def test_restore_can_be_retried_after_a_failure(
    client: TestClient, tools: FakePgTools, archive_dir: Path
) -> None:
    backup_id = _verified_record(directory=archive_dir)
    login_owner(client)
    assert client.post(_restore_url(backup_id)).status_code == 202
    assert _worker(FakePgTools(fail_script=True), archive_dir).tick() is True

    failed = next(row for row in client.get(BACKUPS_URL).json() if row["id"] == backup_id)
    assert failed["restore_status"] == RESTORE_FAILED

    retried = client.post(_restore_url(backup_id))
    assert retried.status_code == 202, retried.text
    body = retried.json()
    assert body["restore_status"] == RESTORE_QUEUED
    assert body["restore_error_code"] is None
    assert body["restore_finished_at"] is None
    assert body["restored_at"] is None


def test_unavailable_storage_is_reported(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.backups.storage_ready", lambda: False)
    login_owner(client)
    assert client.get(SETTINGS_URL).json()["storage_ready"] is False
    assert client.post(BACKUPS_URL).status_code == 409


def test_archive_names_are_stable_and_safe() -> None:
    stamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    from app.core.backup_storage import new_archive_name

    assert new_archive_name("operator", 7, now=stamp) == "charsooq-operator-20260102T030405Z-7.dump"
    assert new_archive_name("pre_restore", 9, now=stamp) == (
        "charsooq-pre_restore-20260102T030405Z-9.dump"
    )
    with Session(get_engine()) as session:
        service = BackupService(session, tools=FakePgTools())
        assert service.name_for("operator", 7).startswith("charsooq-operator-")
        assert service.name_for("operator", 7).endswith("-7.dump")
