"""Dashboard boundary schemas — machine-readable in/out only."""

from pydantic import BaseModel, Field


class DashboardGroupOut(BaseModel):
    name: str = Field(description="Raw Parsina `main_group_name`.")
    count: int = Field(ge=0, description="Product count in the group.")
    stock_value: int = Field(ge=0, description="Sum of price × stock, in Toman.")


class DashboardOverviewOut(BaseModel):
    total: int = Field(ge=0, description="All active catalog rows.")
    in_stock: int = Field(ge=0, description="Rows above the low-stock threshold.")
    low: int = Field(ge=0, description="Rows in stock but at or below the threshold.")
    out: int = Field(ge=0, description="Rows with zero stock.")
    stock_value: int = Field(ge=0, description="Sum of price × stock, in Toman.")
    competitor_coverage: int = Field(
        ge=0, description="Active products with at least one fresh competitor price."
    )
    appliance_total: int = Field(
        ge=0, description="Active non-فرش/مبلمان products (the coverage denominator)."
    )
    groups: list[DashboardGroupOut] = Field(
        default_factory=list, description="Top groups by stock value."
    )


class CompetitorGapOut(BaseModel):
    product_id: int
    name: str
    our_price: int = Field(ge=0, description="Our unit price in Toman.")
    competitor_price: int = Field(ge=0, description="Cheapest fresh competitor price in Toman.")
    competitor_store: str
    diff_percent: float = Field(
        description="(our_price − competitor_price) / competitor_price × 100, one decimal."
    )


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
    stock_value: int = Field(ge=0, description="Sum of price × stock, in Toman.")


class CatalogSectionOut(BaseModel):
    """Per-section (بخش) aggregate — فرش / مبلمان / لوازم خانگی / سایر."""

    top_group: str = Field(description="Section name.")
    items: int = Field(ge=0, description="Active products in the section.")
    group_count: int = Field(ge=0, description="Raw groups in the section.")
    brand_count: int = Field(ge=0, description="Distinct display brands in the section.")
    stock_value: int = Field(ge=0, description="Sum of price × stock, in Toman.")
    brands: list[CatalogBrandOut] = Field(default_factory=list)
