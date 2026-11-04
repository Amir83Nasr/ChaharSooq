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
    groups: list[DashboardGroupOut] = Field(default_factory=list)


class AttentionItemOut(BaseModel):
    product_id: int
    name: str
    price: int = Field(ge=0)
    stock: float = Field(ge=0)


class AttentionOut(BaseModel):
    out: list[AttentionItemOut] = Field(default_factory=list)
    low: list[AttentionItemOut] = Field(default_factory=list)


class CompetitorGapOut(BaseModel):
    product_id: int
    name: str
    our_price: int = Field(ge=0)
    competitor_price: int = Field(ge=0)
    competitor_store: str
    diff_percent: float
