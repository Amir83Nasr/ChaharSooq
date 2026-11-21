"""Background backup/restore worker — one thread, DB-leased across API workers.

The thread only checks for work every few seconds; actual execution is guarded
by the ``backup_state`` lease, so two uvicorn workers never dump or restore at
the same time. Tests never start it.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import sessionmaker

from app.core.database import get_engine
from app.services.backup_worker import TICK_SECONDS, BackupWorker

log = logging.getLogger("charsooq.backup")


class BackupScheduler:
    def __init__(self, worker: BackupWorker) -> None:
        self._worker = worker
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="backup-worker", daemon=True)
        self._thread.start()
        log.info("backup worker started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._worker.tick()
            except Exception:  # noqa: BLE001 — a bad tick must not kill the worker
                log.exception("backup worker tick crashed")
            self._stop.wait(TICK_SECONDS)


def build_backup_scheduler() -> BackupScheduler:
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return BackupScheduler(BackupWorker(factory))
