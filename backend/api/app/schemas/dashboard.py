"""Dashboard boundary schemas — machine-readable in/out only."""

from pydantic import BaseModel, Field


class DashboardGroupOut(BaseModel):
    name: str
    count: int = Field(ge=0)
    stock_value: int = Field(ge=0)


class DashboardOverviewOut(BaseModel):
    total: int = Field(ge=0)
    in_stock: int = Field(ge=0)
    low: int = Field(ge=0)
    out: int = Field(ge=0)
    stock_value: int = Field(ge=0)
    competitor_coverage: int = Field(ge=0)
    appliance_total: int = Field(ge=0)
    groups: list[DashboardGroupOut] = Field(default_factory=list)


class CompetitorGapOut(BaseModel):
    product_id: int
    name: str
    our_price: int = Field(ge=0)
    competitor_price: int = Field(ge=0)
    competitor_store: str
    diff_percent: float


class DashboardSummaryOut(BaseModel):
    """Single-call dashboard payload — overview + gaps + catalog breakdown.

    Replaces three sequential client fetches with one round-trip; the
    individual endpoints stay for backwards compatibility.
    """

    overview: DashboardOverviewOut
    gaps: list[CompetitorGapOut] = Field(default_factory=list)
    catalog: list["CatalogSectionOut"] = Field(default_factory=list)


class CatalogBrandOut(BaseModel):
    """One raw Parsina group inside a section — `group_name` is the full
    `main_group_name`, `brand` is the display remainder after the section
    prefix (same rule as the products table)."""

    group_name: str
    brand: str
    count: int = Field(ge=0)
    stock_value: int = Field(ge=0)


class CatalogSectionOut(BaseModel):
    """Per-section (بخش) aggregate — فرش / مبلمان / لوازم خانگی / سایر."""

    top_group: str
    items: int = Field(ge=0)
    group_count: int = Field(ge=0)
    brand_count: int = Field(ge=0)
    stock_value: int = Field(ge=0)
    brands: list[CatalogBrandOut] = Field(default_factory=list)
