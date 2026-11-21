"""PostgreSQL client tools — the only place that spawns pg_dump/pg_restore/psql.

The API keeps its application-role credential in the environment, never on a
command line. ``pg_dump`` needs no superuser for a logical archive, and a
data-only restore runs with the same least-privilege role. The migration and
administrative credentials are never read here.

Failures surface as stable machine codes (``PgToolError.code``); raw stderr is
never stored in the database and never rendered to the browser.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.engine import URL, make_url

log = logging.getLogger("charsooq.backup")

PG_TOOLS_UNAVAILABLE = "pg_tools_unavailable"
DUMP_FAILED = "dump_failed"
DUMP_TIMEOUT = "dump_timeout"
ARCHIVE_INVALID = "archive_invalid"
RESTORE_FAILED = "restore_failed"
RESTORE_TIMEOUT = "restore_timeout"

#: ``pg_restore --list`` prints one TOC line per object; a TABLE DATA entry is
#: what makes an archive useful for this application's restore path.
_TABLE_DATA_MARKER = "TABLE DATA"


class PgToolError(RuntimeError):
    """A client tool failed; ``code`` is safe to persist and show in the UI."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _connection_env(database_url: str) -> dict[str, str]:
    """libpq environment derived from the application URL (no password in argv)."""
    try:
        parsed: URL = make_url(database_url)
    except Exception:  # noqa: BLE001 — a malformed URL is a configuration error
        raise PgToolError(DUMP_FAILED) from None
    if not parsed.database or not parsed.username:
        raise PgToolError(DUMP_FAILED)

    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env["PGHOST"] = parsed.host or "localhost"
    env["PGPORT"] = str(parsed.port or 5432)
    env["PGUSER"] = parsed.username
    env["PGDATABASE"] = parsed.database
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    sslmode = parsed.query.get("sslmode")
    if isinstance(sslmode, str) and sslmode:
        env["PGSSLMODE"] = sslmode
    return env


def _truncated_stderr(stderr: bytes | None) -> str:
    """A short diagnostic for logs; never includes the connection URL."""
    if not stderr:
        return ""
    text = stderr.decode(errors="replace").strip().replace("\n", " ")
    return text[-300:]


class PgTools:
    """Thin, testable wrapper around the PostgreSQL client binaries."""

    def __init__(self, *, timeout_seconds: int = 3600) -> None:
        self._timeout = timeout_seconds

    # ── availability ─────────────────────────────────────────

    def binary(self, name: str) -> str | None:
        return shutil.which(name)

    def available(self) -> bool:
        return all(self.binary(name) for name in ("pg_dump", "pg_restore", "psql"))

    def _require(self, name: str) -> str:
        path = self.binary(name)
        if path is None:
            raise PgToolError(PG_TOOLS_UNAVAILABLE)
        return path

    # ── dump ─────────────────────────────────────────────────

    def dump(
        self,
        database_url: str,
        target: Path,
        *,
        exclude_table_data: Sequence[str] = (),
    ) -> int:
        """Write a custom-format archive atomically; return its size in bytes."""
        pg_dump = self._require("pg_dump")
        partial = target.with_name(f"{target.name}.partial")
        partial.unlink(missing_ok=True)
        command = [
            pg_dump,
            "--format=custom",
            "--compress=6",
            "--no-owner",
            "--no-privileges",
            f"--file={partial}",
        ]
        command.extend(f"--exclude-table-data=public.{table}" for table in exclude_table_data)

        try:
            result = subprocess.run(
                command,
                env=_connection_env(database_url),
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            partial.unlink(missing_ok=True)
            raise PgToolError(DUMP_TIMEOUT) from None
        if result.returncode != 0 or not partial.exists() or partial.stat().st_size == 0:
            partial.unlink(missing_ok=True)
            log.warning("pg_dump failed: %s", _truncated_stderr(result.stderr))
            raise PgToolError(DUMP_FAILED)

        os.chmod(partial, 0o600)
        partial.replace(target)
        return target.stat().st_size

    # ── verify ───────────────────────────────────────────────

    def verify(self, archive: Path) -> list[str]:
        """Return the archive TOC; raise ``archive_invalid`` when unusable."""
        pg_restore = self._require("pg_restore")
        try:
            result = subprocess.run(
                [pg_restore, "--list", str(archive)],
                capture_output=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise PgToolError(ARCHIVE_INVALID) from None
        if result.returncode != 0:
            log.warning("pg_restore --list failed: %s", _truncated_stderr(result.stderr))
            raise PgToolError(ARCHIVE_INVALID)
        lines = result.stdout.decode(errors="replace").splitlines()
        if not any(_TABLE_DATA_MARKER in line for line in lines):
            raise PgToolError(ARCHIVE_INVALID)
        return lines

    def table_data_tables(self, toc: Sequence[str]) -> set[str]:
        """Table names with a ``TABLE DATA`` entry in a ``pg_restore --list`` TOC."""
        tables: set[str] = set()
        for line in toc:
            if _TABLE_DATA_MARKER not in line:
                continue
            # Format: "<dumpId>; <oid> <oid> TABLE DATA public <name> <owner>"
            parts = line.split()
            if len(parts) >= 7 and parts[3] == "TABLE" and parts[4] == "DATA":
                tables.add(parts[6])
        return tables

    # ── restore ──────────────────────────────────────────────

    def append_table_data(
        self,
        archive: Path,
        tables: Sequence[str],
        sink: BinaryIO,
    ) -> None:
        """Append SQL data blocks (COPY ... FROM stdin) for the given tables."""
        pg_restore = self._require("pg_restore")
        for table in tables:
            try:
                result = subprocess.run(
                    [
                        pg_restore,
                        "--data-only",
                        "--no-owner",
                        "--no-privileges",
                        f"--table={table}",
                        "--file=-",
                        str(archive),
                    ],
                    stdout=sink,
                    stderr=subprocess.PIPE,
                    timeout=self._timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise PgToolError(RESTORE_TIMEOUT) from None
            if result.returncode != 0:
                log.warning("pg_restore data failed: %s", _truncated_stderr(result.stderr))
                raise PgToolError(RESTORE_FAILED)

    def run_script(self, database_url: str, script: Path) -> None:
        """Apply one SQL script with ON_ERROR_STOP inside its own transaction."""
        psql = self._require("psql")
        try:
            result = subprocess.run(
                [
                    psql,
                    "--no-psqlrc",
                    "--quiet",
                    "--set=ON_ERROR_STOP=1",
                    f"--file={script}",
                ],
                env=_connection_env(database_url),
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise PgToolError(RESTORE_TIMEOUT) from None
        if result.returncode != 0:
            log.warning("restore script failed: %s", _truncated_stderr(result.stderr))
            raise PgToolError(RESTORE_FAILED)


#: Shared default used by the API worker; tests inject a fake instance.
PG_TOOLS = PgTools()
