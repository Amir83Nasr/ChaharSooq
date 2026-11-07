"""Catalog boundary schemas — machine-readable in/out only."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.competitor import CompetitorPriceOut


class CategoryIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "فرش"}]})

    name: str = Field(min_length=1, max_length=120, description="Unique category name.")


class CategoryOut(BaseModel):
    id: int
    name: str
    created_at: datetime = Field(description="UTC creation timestamp.")

    model_config = {"from_attributes": True}


class ProductIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "فرش دستباف ۱۲ متری",
                    "sku": "FR-1200",
                    "price": 18_500_000,
                    "stock": 4,
                    "category_id": 1,
                }
            ]
        }
    )

    name: str = Field(min_length=1, max_length=200, description="Display name.")
    sku: str = Field(min_length=1, max_length=64, description="Internal SKU (unique per row).")
    price: int = Field(ge=0, description="Unit price in Toman.")
    stock: int = Field(ge=0, default=0, description="Available quantity.")
    category_id: int | None = Field(default=None, description="Existing category id, if any.")


class ProductOut(BaseModel):
    """Mirror row — numbers stay machine-readable; UI formats them."""

    id: int
    external_id: int | None = Field(
        default=None, description="Parsina `goodId`; null for manual rows."
    )
    name: str
    sku: str
    price: float = Field(description="Unit price in Toman.")
    stock: float = Field(description="Available quantity.")
    main_group_name: str | None = Field(default=None, description="Raw Parsina group name.")
    sub_group_name: str | None = None
    unit_name: str | None = None
    is_active: bool = Field(default=True, description="False once the source drops the row.")
    category: CategoryOut | None = None
    synced_at: datetime | None = Field(
        default=None, description="Last successful source sync (UTC)."
    )
    competitor_prices: list[CompetitorPriceOut] = Field(default_factory=list)
    allowed_decrease_percent: float | None = Field(
        default=None,
        description=(
            "Maximum allowed decrease below the base price (m in the floor "
            "formula); null leaves the suggested price unclamped on this side."
        ),
    )
    allowed_increase_percent: float | None = Field(
        default=None,
        description=(
            "Maximum allowed increase above the base price (n in the ceiling "
            "formula); null leaves the suggested price unclamped on this side."
        ),
    )
    created_at: datetime = Field(description="UTC creation timestamp.")

    model_config = {"from_attributes": True}


class ProductPriceBoundsUpdate(BaseModel):
    """Per-product suggested-price clamp: m% below and n% above the base."""

    allowed_decrease_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum allowed decrease below the base price, in percent.",
    )
    allowed_increase_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum allowed increase above the base price, in percent.",
    )


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int = Field(description="Total matches across all pages.")
    page: int = Field(description="1-based page number; always 1 for a show-all request.")
    page_size: int = Field(
        description="Items per page; equals the item count for a show-all request."
    )


class InventorySummaryOut(BaseModel):
    total: int = Field(description="All catalog rows.")
    in_stock: int = Field(description="Rows with stock above the low-stock threshold.")
    low: int = Field(description="Rows in stock but at or below the threshold.")
    out: int = Field(description="Rows with zero stock.")
    stock_value: int = Field(description="Sum of price × stock, in Toman.")


class SyncRunOut(BaseModel):
    """Accepted trigger only — counters arrive via the status endpoint."""

    status: Literal["running"] = Field(description="The job was accepted and is running.")
    message: str | None = Field(default=None, description="Persian status message.")


class SyncStatusOut(BaseModel):
    configured: bool = Field(description="Whether the active source has credentials/data.")
    source: Literal["parsina", "csv", "dev"] = Field(
        default="parsina", description="Active product source."
    )
    running: bool = Field(description="A manual or scheduled run currently holds the lock.")
    running_since: datetime | None = Field(
        default=None, description="UTC start of the current run."
    )
    last_attempt_at: datetime | None = Field(default=None, description="UTC start of the last run.")
    last_success_at: datetime | None = Field(
        default=None, description="UTC end of the last fully applied run."
    )
    last_error: str | None = Field(
        default=None, description="Persian error from the last failed run."
    )
    last_processed: int = Field(default=0, description="Rows read in the last run.")
    last_created: int = Field(default=0, description="Rows created in the last run.")
    last_updated: int = Field(default=0, description="Rows updated in the last run.")
    last_deactivated: int = Field(default=0, description="Rows soft-deleted in the last run.")
    last_skipped: int = Field(
        default=0, description="Rows skipped by the importer in the last run."
    )
    interval_minutes: int = Field(description="Scheduled interval in minutes.")
