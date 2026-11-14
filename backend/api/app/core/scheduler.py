"""Background scheduler — periodic product sync, independent of any browser.

Runs in a daemon thread inside the API process. Multi-worker/multi-instance
safety comes from the DB lock in ProductSyncService, not from this loop.
Development ticks on the same interval from the CSV fixture so dev mirrors
the production timing; only tests never start it.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_parsina_settings, get_settings
from app.core.database import get_engine
from app.integrations.parsina_csv import CsvCommoditySource
from app.services.competitor_sync import run_scheduled_competitor_sync
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
        app_settings = get_settings()
        mode = app_settings.source_mode
        if mode == "off":
            log.info("scheduler off: sync loop runs only in development and production")
            return
        if mode == "csv":
            # Dev mirrors prod timing from the CSV fixture (same interval,
            # same lock, same status reporting) — no Parsina credentials needed.
            if not CsvCommoditySource(Path(app_settings.products_csv_path)).is_configured:
                log.info("scheduler off: product CSV fixture not configured")
                return
        # In "parsina" mode the connection can be configured later in settings, so
        # the loop always starts and each tick checks effective DB/env config.
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="parsina-sync", daemon=True)
        self._thread.start()
        if mode == "csv":
            log.info(
                "scheduler on (development CSV): every %d min",
                get_parsina_settings().parsina_sync_interval_minutes,
            )
        elif mode == "dev":
            log.info(
                "scheduler on (dev-db simulation): every %d min",
                get_parsina_settings().parsina_sync_interval_minutes,
            )
        else:
            log.info(
                "scheduler on (parsina): every %d min",
                get_parsina_settings().parsina_sync_interval_minutes,
            )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                # Re-read the intervals each tick so admin changes in Settings
                # take effect without a process restart. One session covers
                # both reads so a tick costs a single checkout.
                from app.services import SettingsService

                with self._session_factory() as _s:
                    interval = SettingsService(_s).get_sync_interval()
                    competitor_interval = SettingsService(_s).get_competitor_sync_interval()
                run_scheduled_sync(session_factory=self._session_factory, interval_minutes=interval)
                run_scheduled_competitor_sync(
                    session_factory=self._session_factory,
                    interval_minutes=competitor_interval,
                )
            except Exception:  # noqa: BLE001 — a bad tick must not kill the loop
                log.exception("scheduled sync tick crashed")
            self._stop.wait(TICK_SECONDS)


def build_scheduler() -> SyncScheduler:
    """Tests never start it; only the running app's lifespan does."""
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return SyncScheduler(factory)
