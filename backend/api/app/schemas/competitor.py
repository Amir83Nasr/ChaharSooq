"""Competitor price management request and response types."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CompetitorStore = Literal["digikala", "technolife", "other"]
CompetitorStatus = Literal[
    "pending", "success", "not_found", "unavailable", "blocked", "failed", "manual"
]
Currency = Literal["IRR", "IRT"]


class CompetitorListingCreate(BaseModel):
    store: CompetitorStore
    url: str = Field(min_length=12, max_length=2048)


class CompetitorListingUpdate(BaseModel):
    store: CompetitorStore | None = None
    url: str | None = Field(default=None, min_length=12, max_length=2048)
    is_active: bool | None = None
    manual_price: float | None = Field(default=None, ge=0, le=10**15)
    manual_currency: Currency | None = None
    manual_in_stock: bool | None = None


class CompetitorListingOut(BaseModel):
    id: int
    product_id: int
    store: CompetitorStore
    url: str
    is_active: bool
    status: CompetitorStatus
    fetched_price: float | None
    fetched_currency: Currency | None
    fetched_in_stock: bool | None
    manual_price: float | None
    manual_currency: Currency | None
    manual_in_stock: bool | None
    effective_price: float | None
    effective_currency: Currency | None
    effective_in_stock: bool | None
    price_is_fresh: bool
    last_checked_at: datetime | None
    last_success_at: datetime | None
    manual_updated_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class CompetitorCheckOut(BaseModel):
    listing: CompetitorListingOut


class CompetitorPriceOut(BaseModel):
    id: int
    store: CompetitorStore
    url: str
    status: CompetitorStatus
    price: float | None
    currency: Currency | None
    in_stock: bool | None
    is_fresh: bool
    is_manual: bool
    last_checked_at: datetime | None


class CompetitorSyncRunOut(BaseModel):
    """Accepted trigger only — counters arrive via the status endpoint."""

    status: Literal["running"]
    message: str | None = None


class CompetitorSyncStatusOut(BaseModel):
    running: bool
    running_since: datetime | None = None
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_checked: int = 0
    last_updated: int = 0
    last_failed: int = 0
    last_skipped: int = 0
