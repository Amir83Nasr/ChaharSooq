"""Settings service — admin display preferences get/update."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.models import SuggestedPriceFormula
from app.repositories import SettingsRepository, SuggestedPriceFormulaRepository
from app.schemas import SuggestedPriceFormulaIn
from app.schemas.settings import ProductTableColumn

LOW_STOCK_THRESHOLD_KEY = "low_stock_threshold"
DEFAULT_LOW_STOCK_THRESHOLD = 5

DEFAULT_PAGE_SIZE_KEY = "default_page_size"
DEFAULT_PAGE_SIZE = 0
ALLOWED_PAGE_SIZES = (0, 10, 20, 50, 100, 500)

SYNC_INTERVAL_KEY = "sync_interval_minutes"
DEFAULT_SYNC_INTERVAL_MINUTES = 1440
MIN_SYNC_INTERVAL_MINUTES = 1
MAX_SYNC_INTERVAL_MINUTES = 10080

COMPETITOR_SYNC_INTERVAL_KEY = "competitor_sync_interval_minutes"
DEFAULT_COMPETITOR_SYNC_INTERVAL_MINUTES = 1440
MIN_COMPETITOR_SYNC_INTERVAL_MINUTES = 15
MAX_COMPETITOR_SYNC_INTERVAL_MINUTES = 10080

DEFAULT_COMPETITOR_STORE_KEY = "default_competitor_store"
DEFAULT_COMPETITOR_STORE: Literal["digikala", "technolife"] = "digikala"
ALLOWED_COMPETITOR_STORES: tuple[Literal["digikala", "technolife"], ...] = (
    "digikala",
    "technolife",
)

PRODUCT_TABLE_COLUMNS_KEY = "product_table_columns"
# Canonical table order; also the default when nothing is stored yet.
PRODUCT_TABLE_COLUMNS: tuple[ProductTableColumn, ...] = (
    "row",
    "name",
    "sku",
    "category",
    "brand",
    "unit",
    "price",
    "competitor_price",
    "price_diff",
    "suggested_price",
    "stock",
)
DEFAULT_PRODUCT_TABLE_COLUMNS: tuple[ProductTableColumn, ...] = PRODUCT_TABLE_COLUMNS


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._settings = SettingsRepository(session)
        self._formulas = SuggestedPriceFormulaRepository(session)

    def get_all(self) -> dict[str, object]:
        return {
            "low_stock_threshold": self.get_threshold(),
            "default_page_size": self.get_page_size(),
            "sync_interval_minutes": self.get_sync_interval(),
            "competitor_sync_interval_minutes": self.get_competitor_sync_interval(),
            "default_competitor_store": self.get_competitor_store(),
            "suggested_price_formulas": self.get_suggested_price_formulas(),
            "product_table_columns": self.get_product_table_columns(),
        }

    def get_suggested_price_formulas(self) -> list[dict[str, object]]:
        rows = self._formulas.list_ordered()
        return [{"top_group": row.top_group, "weight": float(row.weight)} for row in rows]

    def update_suggested_price_formulas(
        self, formulas: list[SuggestedPriceFormulaIn]
    ) -> list[dict[str, object]]:
        existing = self._formulas.get_map()
        submitted = {item.top_group: item.weight for item in formulas}
        for top_group, row in existing.items():
            if top_group not in submitted:
                self._formulas.delete(row)
        for top_group, weight in submitted.items():
            row = existing.get(top_group)
            decimal_weight = Decimal(str(weight))
            if row is None:
                new_row = SuggestedPriceFormula(top_group=top_group, weight=decimal_weight)
                self._formulas.add(new_row)
            else:
                self._formulas.update_weight(row, decimal_weight)
        return self.get_suggested_price_formulas()

    def get_threshold(self) -> int:
        row = self._settings.get(LOW_STOCK_THRESHOLD_KEY)
        if row is None:
            return DEFAULT_LOW_STOCK_THRESHOLD
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_LOW_STOCK_THRESHOLD
        return max(value, 0)

    def update_threshold(self, threshold: int) -> int:
        self._settings.upsert(LOW_STOCK_THRESHOLD_KEY, str(threshold))
        return threshold

    def get_page_size(self) -> int:
        row = self._settings.get(DEFAULT_PAGE_SIZE_KEY)
        if row is None:
            return DEFAULT_PAGE_SIZE
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_PAGE_SIZE
        return value if value in ALLOWED_PAGE_SIZES else DEFAULT_PAGE_SIZE

    def update_page_size(self, page_size: int) -> int:
        self._settings.upsert(DEFAULT_PAGE_SIZE_KEY, str(page_size))
        return page_size

    def get_sync_interval(self) -> int:
        row = self._settings.get(SYNC_INTERVAL_KEY)
        if row is None:
            return DEFAULT_SYNC_INTERVAL_MINUTES
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_SYNC_INTERVAL_MINUTES
        return min(max(value, MIN_SYNC_INTERVAL_MINUTES), MAX_SYNC_INTERVAL_MINUTES)

    def update_sync_interval(self, minutes: int) -> int:
        self._settings.upsert(SYNC_INTERVAL_KEY, str(minutes))
        return minutes

    def get_competitor_sync_interval(self) -> int:
        row = self._settings.get(COMPETITOR_SYNC_INTERVAL_KEY)
        if row is None:
            return DEFAULT_COMPETITOR_SYNC_INTERVAL_MINUTES
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_COMPETITOR_SYNC_INTERVAL_MINUTES
        return min(
            max(value, MIN_COMPETITOR_SYNC_INTERVAL_MINUTES),
            MAX_COMPETITOR_SYNC_INTERVAL_MINUTES,
        )

    def update_competitor_sync_interval(self, minutes: int) -> int:
        self._settings.upsert(COMPETITOR_SYNC_INTERVAL_KEY, str(minutes))
        return minutes

    def get_competitor_store(self) -> Literal["digikala", "technolife"]:
        row = self._settings.get(DEFAULT_COMPETITOR_STORE_KEY)
        if row is None:
            return DEFAULT_COMPETITOR_STORE
        value = row.value.strip()
        if value == "technolife":
            return "technolife"
        return "digikala"

    def update_competitor_store(
        self, store: Literal["digikala", "technolife"]
    ) -> Literal["digikala", "technolife"]:
        self._settings.upsert(DEFAULT_COMPETITOR_STORE_KEY, store)
        return store

    def get_product_table_columns(self) -> list[ProductTableColumn]:
        row = self._settings.get(PRODUCT_TABLE_COLUMNS_KEY)
        if row is None:
            return list(DEFAULT_PRODUCT_TABLE_COLUMNS)
        stored = {part.strip() for part in row.value.split(",") if part.strip()}
        visible: list[ProductTableColumn] = [
            column for column in PRODUCT_TABLE_COLUMNS if column in stored
        ]
        # An empty or fully unknown value would hide the whole table.
        if not visible:
            return list(DEFAULT_PRODUCT_TABLE_COLUMNS)
        return visible

    def update_product_table_columns(
        self, columns: list[ProductTableColumn]
    ) -> list[ProductTableColumn]:
        requested = set(columns)
        visible: list[ProductTableColumn] = [
            column for column in PRODUCT_TABLE_COLUMNS if column in requested
        ]
        if not visible:
            visible = list(DEFAULT_PRODUCT_TABLE_COLUMNS)
        self._settings.upsert(PRODUCT_TABLE_COLUMNS_KEY, ",".join(visible))
        return visible
