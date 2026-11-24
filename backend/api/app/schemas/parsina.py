"""Parsina integration connection and product cardex schemas."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import PricingMode


class ParsinaConnectionOut(BaseModel):
    """Current Parsina connection as visible to the super admin.

    The password is never returned; `password_set` indicates whether one is
    stored (in the database or provided via env/secrets).
    """

    base_url: str = Field(default="", description="Parsina API base URL.")
    username: str = Field(default="", description="Parsina username.")
    org_id: int | None = Field(default=None, description="Organization id (org).")
    fiscal_year: int | None = Field(default=None, description="Fiscal year.")
    password_set: bool = Field(default=False, description="True when a password is configured.")
    configured: bool = Field(
        default=False, description="True when the effective connection is usable."
    )
    source: str = Field(
        default="none",
        description="Where the effective config comes from: db, env, or none.",
    )


class ParsinaConnectionIn(BaseModel):
    """Update Parsina connection fields. Omitted fields keep their current value."""

    model_config = ConfigDict(extra="ignore")

    base_url: str | None = Field(default=None, max_length=512)
    username: str | None = Field(default=None, max_length=255)
    # Empty string or null keeps the existing stored password.
    password: str | None = Field(default=None, max_length=512)
    org_id: int | None = Field(default=None, ge=1)
    fiscal_year: int | None = Field(default=None, ge=1, le=9999)


class CardexPeriod(BaseModel):
    """One of the four selectable cardex windows."""

    key: str = Field(description="Stable key: today, 3_days, 7_days, or 30_days.")
    label: str = Field(description="Persian label shown in the period selector.")
    from_date: date = Field(description="Inclusive ISO start date (UTC machine value).")
    to_date: date = Field(description="Inclusive ISO end date (UTC machine value).")


class CardexEntryOut(BaseModel):
    """A single purchase or sale line for the selected product."""

    kind: str = Field(description="`sale` or `purchase`.")
    invoice_id: int = Field(description="Parsina invoice id.")
    invoice_number: int | None = Field(default=None, description="Parsina invoice number.")
    invoice_date: date | None = Field(default=None, description="Invoice date, ISO.")
    counterparty: str | None = Field(default=None, description="Buyer or seller name.")
    quantity: float = Field(default=0, description="Total quantity in the invoice line.")
    net_price: int = Field(default=0, description="Net line amount in toman (integer).")
    is_cancelled: bool = Field(default=False, description="Parsina IsCancel flag.")
    is_confirmed: bool = Field(default=False, description="Parsina isConfirm flag.")
    is_checkedout: bool = Field(default=False, description="Parsina IsCheckedout flag.")


class CardexSummaryOut(BaseModel):
    """Aggregate purchase/sale figures for the selected window."""

    purchase_quantity: float = Field(default=0, description="Purchased quantity in the window.")
    purchase_amount: int = Field(default=0, description="Purchase amount in toman (integer).")
    sale_quantity: float = Field(default=0, description="Sold quantity in the window.")
    sale_amount: int = Field(default=0, description="Sale amount in toman (integer).")


class ProductCardexOut(BaseModel):
    """Sales/purchase history recorded in Parsina for one product."""

    product_id: int = Field(description="Charsooq product id.")
    sku: str = Field(description="Product SKU / Parsina good code.")
    period: str = Field(description="Selected period key.")
    periods: list[CardexPeriod] = Field(
        default_factory=list, description="The four available windows."
    )
    summary: CardexSummaryOut = Field(default_factory=CardexSummaryOut)
    entries: list[CardexEntryOut] = Field(default_factory=list)
    configured: bool = Field(default=False, description="Parsina connection is configured.")
    pricing_mode: PricingMode | None = Field(
        default=None, description="Current pricing mode of the product."
    )
