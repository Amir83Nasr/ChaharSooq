"""Catalog boundary schemas — machine-readable in/out only."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class CategoryOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=64)
    price: int = Field(ge=0)  # toman, integer
    stock: int = Field(ge=0, default=0)
    category_id: int | None = Field(default=None)


class ProductOut(BaseModel):
    """Mirror row — numbers stay machine-readable; UI formats them."""

    id: int
    external_id: int | None = None
    name: str
    sku: str
    price: float
    stock: float
    main_group_name: str | None = None
    sub_group_name: str | None = None
    unit_name: str | None = None
    is_active: bool = True
    category: CategoryOut | None = None
    synced_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


class InventorySummaryOut(BaseModel):
    total: int
    in_stock: int
    low: int
    out: int
    stock_value: int


class SyncRunOut(BaseModel):
    """Accepted trigger only — counters arrive via the status endpoint."""

    status: Literal["running"]
    message: str | None = None


class SyncStatusOut(BaseModel):
    configured: bool
    source: Literal["parsina", "csv"] = "parsina"
    running: bool
    running_since: datetime | None = None
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_processed: int = 0
    last_created: int = 0
    last_updated: int = 0
    last_deactivated: int = 0
    last_skipped: int = 0
    interval_minutes: int
