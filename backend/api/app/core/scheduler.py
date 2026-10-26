"""Background scheduler — periodic Parsina sync, independent of any browser.

Runs in a daemon thread inside the API process. Multi-worker/multi-instance
safety comes from the DB lock in ProductSyncService, not from this loop.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_parsina_settings
from app.core.database import get_engine
from app.services.sync import run_scheduled_sync

log = logging.getLogger("charsooq.scheduler")

# How often the loop checks "is a sync due?" — the real interval is the env
# setting; ticking faster keeps that interval honest without more DB writes.
TICK_SECONDS = 30


class SyncScheduler:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        settings = get_parsina_settings()
        if not settings.is_configured or not settings.parsina_sync_enabled:
            log.info("scheduler off: parsina not configured")
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="parsina-sync", daemon=True)
        self._thread.start()
        log.info("scheduler on: every %d min", settings.parsina_sync_interval_minutes)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        interval = get_parsina_settings().parsina_sync_interval_minutes
        while not self._stop.is_set():
            try:
                run_scheduled_sync(session_factory=self._session_factory, interval_minutes=interval)
            except Exception:  # noqa: BLE001 — a bad tick must not kill the loop
                log.exception("scheduled parsina sync crashed")
            self._stop.wait(TICK_SECONDS)


def build_scheduler() -> SyncScheduler:
    """Tests never start it; only the running app's lifespan does."""
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return SyncScheduler(factory)
