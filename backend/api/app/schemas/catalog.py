"""Catalog boundary schemas — machine-readable in/out only."""

from datetime import datetime

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
    id: int
    name: str
    sku: str
    price: int
    stock: int
    category: CategoryOut | None = None
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
