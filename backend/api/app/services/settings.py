"""Settings service — admin display preferences get/update."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_parsina_settings
from app.models import Setting

LOW_STOCK_THRESHOLD_KEY = "low_stock_threshold"
DEFAULT_LOW_STOCK_THRESHOLD = 5

DEFAULT_PAGE_SIZE_KEY = "default_page_size"
DEFAULT_PAGE_SIZE = 0
ALLOWED_PAGE_SIZES = (0, 10, 20, 50, 100, 500)

SYNC_INTERVAL_KEY = "sync_interval_minutes"
DEFAULT_SYNC_INTERVAL_MINUTES = get_parsina_settings().parsina_sync_interval_minutes
MIN_SYNC_INTERVAL_MINUTES = 1
MAX_SYNC_INTERVAL_MINUTES = 10080


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> dict[str, int]:
        return {
            "low_stock_threshold": self.get_threshold(),
            "default_page_size": self.get_page_size(),
            "sync_interval_minutes": self.get_sync_interval(),
        }

    def get_threshold(self) -> int:
        row = self._session.get(Setting, LOW_STOCK_THRESHOLD_KEY)
        if row is None:
            return DEFAULT_LOW_STOCK_THRESHOLD
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_LOW_STOCK_THRESHOLD
        return max(value, 0)

    def update_threshold(self, threshold: int) -> int:
        row = self._session.get(Setting, LOW_STOCK_THRESHOLD_KEY)
        if row is None:
            row = Setting(key=LOW_STOCK_THRESHOLD_KEY, value=str(threshold))
            self._session.add(row)
        else:
            row.value = str(threshold)
        self._session.flush()
        return threshold

    def get_page_size(self) -> int:
        row = self._session.get(Setting, DEFAULT_PAGE_SIZE_KEY)
        if row is None:
            return DEFAULT_PAGE_SIZE
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_PAGE_SIZE
        return value if value in ALLOWED_PAGE_SIZES else DEFAULT_PAGE_SIZE

    def update_page_size(self, page_size: int) -> int:
        row = self._session.get(Setting, DEFAULT_PAGE_SIZE_KEY)
        if row is None:
            row = Setting(key=DEFAULT_PAGE_SIZE_KEY, value=str(page_size))
            self._session.add(row)
        else:
            row.value = str(page_size)
        self._session.flush()
        return page_size

    def get_sync_interval(self) -> int:
        row = self._session.get(Setting, SYNC_INTERVAL_KEY)
        if row is None:
            return DEFAULT_SYNC_INTERVAL_MINUTES
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_SYNC_INTERVAL_MINUTES
        return min(max(value, MIN_SYNC_INTERVAL_MINUTES), MAX_SYNC_INTERVAL_MINUTES)

    def update_sync_interval(self, minutes: int) -> int:
        row = self._session.get(Setting, SYNC_INTERVAL_KEY)
        if row is None:
            row = Setting(key=SYNC_INTERVAL_KEY, value=str(minutes))
            self._session.add(row)
        else:
            row.value = str(minutes)
        self._session.flush()
        return minutes
