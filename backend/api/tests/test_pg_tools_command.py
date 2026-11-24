"""The pg_dump command must not read tables the application role cannot see."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.integrations.pg_tools import PgTools


def test_excluded_tables_are_not_even_locked(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """``--exclude-table-data`` alone still takes ACCESS SHARE and fails on a
    table revoked from the application role (alembic_version); the whole table
    must be excluded from the dump instead."""
    captured: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured.extend(command)
        file_arg = next(arg for arg in command if arg.startswith("--file="))
        target = Path(file_arg.split("=", 1)[1])
        target.write_bytes(b"archive")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr("app.integrations.pg_tools.subprocess.run", fake_run)
    monkeypatch.setattr(PgTools, "binary", lambda self, name: f"/usr/bin/{name}")

    tools = PgTools()
    archive = tmp_path / "backup.dump"
    size = tools.dump(
        "postgresql://app:pw@localhost/db",
        archive,
        exclude_table_data=("alembic_version",),
    )

    command = captured
    assert size == archive.stat().st_size
    assert "--exclude-table=public.alembic_version" in command
    assert "--exclude-table-data=public.alembic_version" not in command
