"""Settings service — admin display preferences get/update."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_parsina_settings
from app.models import Setting, SuggestedPriceFormula

LOW_STOCK_THRESHOLD_KEY = "low_stock_threshold"
DEFAULT_LOW_STOCK_THRESHOLD = 5

DEFAULT_PAGE_SIZE_KEY = "default_page_size"
DEFAULT_PAGE_SIZE = 0
ALLOWED_PAGE_SIZES = (0, 10, 20, 50, 100, 500)

SYNC_INTERVAL_KEY = "sync_interval_minutes"
DEFAULT_SYNC_INTERVAL_MINUTES = get_parsina_settings().parsina_sync_interval_minutes
MIN_SYNC_INTERVAL_MINUTES = 1
MAX_SYNC_INTERVAL_MINUTES = 10080

DEFAULT_COMPETITOR_STORE_KEY = "default_competitor_store"
DEFAULT_COMPETITOR_STORE: Literal["digikala", "technolife"] = "digikala"
ALLOWED_COMPETITOR_STORES: tuple[Literal["digikala", "technolife"], ...] = (
    "digikala",
    "technolife",
)


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> dict[str, object]:
        return {
            "low_stock_threshold": self.get_threshold(),
            "default_page_size": self.get_page_size(),
            "sync_interval_minutes": self.get_sync_interval(),
            "default_competitor_store": self.get_competitor_store(),
            "suggested_price_formulas": self.get_suggested_price_formulas(),
        }

    def get_suggested_price_formulas(self) -> list[dict[str, str]]:
        rows = self._session.scalars(
            select(SuggestedPriceFormula).order_by(SuggestedPriceFormula.top_group)
        )
        return [{"top_group": row.top_group, "expression": row.expression} for row in rows]

    def update_suggested_price_formulas(
        self, formulas: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        existing = {
            row.top_group: row for row in self._session.scalars(select(SuggestedPriceFormula)).all()
        }
        submitted = {str(item["top_group"]): str(item["expression"]) for item in formulas}
        for top_group, row in existing.items():
            if top_group not in submitted:
                self._session.delete(row)
        for top_group, expression in submitted.items():
            row = existing.get(top_group)
            if row is None:
                self._session.add(SuggestedPriceFormula(top_group=top_group, expression=expression))
            else:
                row.expression = expression
        self._session.flush()
        return self.get_suggested_price_formulas()

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

    def get_competitor_store(self) -> Literal["digikala", "technolife"]:
        row = self._session.get(Setting, DEFAULT_COMPETITOR_STORE_KEY)
        if row is None:
            return DEFAULT_COMPETITOR_STORE
        value = row.value.strip()
        if value == "technolife":
            return "technolife"
        return "digikala"

    def update_competitor_store(
        self, store: Literal["digikala", "technolife"]
    ) -> Literal["digikala", "technolife"]:
        row = self._session.get(Setting, DEFAULT_COMPETITOR_STORE_KEY)
        if row is None:
            row = Setting(key=DEFAULT_COMPETITOR_STORE_KEY, value=store)
            self._session.add(row)
        else:
            row.value = store
        self._session.flush()
        return store
