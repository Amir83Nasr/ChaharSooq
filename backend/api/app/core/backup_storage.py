"""Local archive storage for logical backups.

Archives live in one directory (a named Docker volume in Production) with
owner-only permissions. Only a validated basename is ever stored in the
database, so a compromised metadata row cannot point outside the directory.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings

_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,180}")


def backup_dir() -> Path:
    return get_settings().resolved_backup_dir


def ensure_backup_dir() -> Path:
    """Create the archive directory with owner-only permissions."""
    directory = backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:  # pragma: no cover — a mounted volume may already be correct
        pass
    return directory


def storage_ready() -> bool:
    try:
        directory = ensure_backup_dir()
        return os.access(directory, os.W_OK | os.X_OK)
    except OSError:
        return False


def archive_path(storage_ref: str | None, *, directory: Path | None = None) -> Path | None:
    """Resolve a stored basename under the archive directory, or ``None``."""
    if not storage_ref or not _SAFE_NAME.fullmatch(storage_ref):
        return None
    base = (directory if directory is not None else backup_dir()).resolve()
    candidate = (base / storage_ref).resolve()
    if candidate.parent != base:
        return None
    return candidate


def existing_archive(storage_ref: str | None, *, directory: Path | None = None) -> Path | None:
    path = archive_path(storage_ref, directory=directory)
    if path is None or not path.is_file():
        return None
    return path


def new_archive_name(kind: str, record_id: int, *, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"charsooq-{kind}-{stamp}-{record_id}.dump"


def upload_archive_name(*, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"charsooq-uploaded-{stamp}-{os.urandom(4).hex()}.dump"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remove_quietly(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
