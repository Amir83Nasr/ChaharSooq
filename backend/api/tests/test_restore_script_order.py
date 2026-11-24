"""Restore script ordering: buffered DELETEs must reach disk before pg_restore."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from app.services.backup_worker import BackupWorker

TOC = [
    "1; 0 0 TABLE DATA public products owner",
    "2; 0 0 TABLE DATA public settings owner",
]


class FdWriterTools:
    """Writes COPY blocks to the raw fd, like `pg_restore --file=-` does."""

    def verify(self, archive: Path) -> list[str]:
        return list(TOC)

    def table_data_tables(self, toc: Sequence[str]) -> set[str]:
        return {line.split()[6] for line in toc}

    def append_table_data(self, archive: Path, tables: Sequence[str], sink: BinaryIO) -> None:
        # Bypass Python's buffer: this is what a subprocess writing to the
        # same file descriptor does in production.
        fd = sink.fileno()
        for table in tables:
            os.write(fd, f"COPY public.{table} (id) FROM stdin;\n\\.\n".encode())

    def run_script(self, database_url: str, script: Path) -> None:
        pass


def test_deletes_are_written_before_copy_blocks(tmp_path: Path) -> None:
    worker = BackupWorker.__new__(BackupWorker)
    worker._tools = FdWriterTools()  # type: ignore[assignment]
    worker._capture_backup_settings = lambda: {}  # type: ignore[method-assign]
    worker._sequence_statements = lambda tables: []  # type: ignore[method-assign]

    script = tmp_path / "restore.sql"
    script.parent.mkdir(parents=True, exist_ok=True)
    worker._build_restore_script(tmp_path / "archive.dump", script)

    content = script.read_bytes().decode()
    first_copy = content.find("COPY public.")
    assert first_copy > 0
    for table in ("products", "settings"):
        delete = f'DELETE FROM public."{table}";'  # noqa: S608
        assert 0 < content.find(delete) < first_copy, content
