"""Pydantic boundary schemas — machine-readable in/out only."""

from datetime import datetime

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, list[str]] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    ok: bool = True


class MeOut(BaseModel):
    username: str


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


class SettingsOut(BaseModel):
    low_stock_threshold: int


class SettingsUpdateIn(BaseModel):
    low_stock_threshold: int = Field(ge=0, le=1_000_000)
