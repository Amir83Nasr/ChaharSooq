"""Competitor price management request and response types."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CompetitorStore = Literal["digikala", "technolife", "sofa", "digifresh", "other"]
CompetitorStatus = Literal[
    "pending", "success", "not_found", "unavailable", "blocked", "failed", "manual"
]
Currency = Literal["IRR", "IRT"]


class CompetitorListingCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "store": "digikala",
                    "url": "https://www.digikala.com/product/dkp-123456/",
                }
            ]
        }
    )

    store: CompetitorStore = Field(
        description="`digikala` and `technolife` are fetched automatically; `other` is manual-only."
    )
    url: str = Field(min_length=12, max_length=2048, description="Public product page URL.")


class CompetitorListingUpdate(BaseModel):
    store: CompetitorStore | None = None
    url: str | None = Field(default=None, min_length=12, max_length=2048)
    is_active: bool | None = Field(default=None, description="Pause auto-checks without deleting.")
    manual_price: float | None = Field(
        default=None, ge=0, le=10**15, description="Manual override in `manual_currency`."
    )
    manual_currency: Currency | None = Field(
        default=None, description="`IRT` = Toman, `IRR` = Rial. Defaults to the store's currency."
    )
    manual_in_stock: bool | None = Field(default=None, description="Manual stock override.")


class CompetitorListingOut(BaseModel):
    id: int
    product_id: int
    store: CompetitorStore
    url: str
    is_active: bool = Field(description="Inactive links are skipped by checks and bulk refresh.")
    status: CompetitorStatus = Field(
        description=(
            "Last fetch result: `success`, `not_found`, `unavailable`, `blocked`, "
            "`failed`, `pending`, or `manual`."
        )
    )
    fetched_price: float | None = Field(default=None, description="Last automatic price.")
    fetched_currency: Currency | None = None
    fetched_in_stock: bool | None = None
    manual_price: float | None = Field(default=None, description="Admin override, if set.")
    manual_currency: Currency | None = None
    manual_in_stock: bool | None = None
    effective_price: float | None = Field(
        default=None,
        description=(
            "Fresh manual override, otherwise a fresh fetched price; null for "
            "inactive links or stale data."
        ),
    )
    effective_currency: Currency | None = None
    effective_in_stock: bool | None = None
    price_is_fresh: bool = Field(description="The effective price is fresh and the link is active.")
    last_checked_at: datetime | None = Field(default=None, description="Last fetch attempt (UTC).")
    last_success_at: datetime | None = Field(
        default=None, description="Last successful fetch (UTC)."
    )
    manual_updated_at: datetime | None = Field(
        default=None, description="Last override update (UTC)."
    )
    last_error: str | None = Field(
        default=None, description="Persian error from the last failed fetch."
    )
    price_change_percent: float | None = Field(
        default=None,
        description=(
            "Change between the latest observation and the last one at least "
            "24 hours older, in percent. Null until two daily observations exist."
        ),
    )
    previous_price: float | None = Field(
        default=None, description="Price from the previous daily observation."
    )
    previous_currency: Currency | None = None
    previous_observed_at: datetime | None = Field(
        default=None, description="UTC timestamp of the previous daily observation."
    )
    created_at: datetime
    updated_at: datetime


class CompetitorCheckOut(BaseModel):
    listing: CompetitorListingOut


class CompetitorPriceOut(BaseModel):
    id: int
    store: CompetitorStore
    url: str
    status: CompetitorStatus
    price: float | None = Field(default=None, description="Effective price (manual wins).")
    currency: Currency | None = None
    in_stock: bool | None = None
    is_fresh: bool = Field(description="Price is within the configured TTL.")
    is_manual: bool = Field(description="The effective price comes from a manual override.")
    last_checked_at: datetime | None = None
    price_change_percent: float | None = Field(
        default=None,
        description="Daily price change of the linked product, in percent.",
    )
    previous_price: float | None = None
    previous_currency: Currency | None = None
    previous_observed_at: datetime | None = None


class CompetitorSyncRunOut(BaseModel):
    """Accepted trigger only — counters arrive via the status endpoint."""

    status: Literal["running"] = Field(description="The job was accepted and is running.")
    message: str | None = Field(default=None, description="Persian status message.")


class CompetitorSyncStatusOut(BaseModel):
    running: bool = Field(description="A bulk refresh currently holds the lock.")
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
    last_checked: int = Field(default=0, description="Links checked in the last run.")
    last_updated: int = Field(default=0, description="Listings updated in the last run.")
    last_failed: int = Field(default=0, description="Links that failed in the last run.")
    last_skipped: int = Field(default=0, description="Inactive links skipped in the last run.")
