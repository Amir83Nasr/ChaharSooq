"""Settings boundary schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.suggested_price import SuggestedPriceFormulaIn, SuggestedPriceFormulaOut

# Stable ids for the product table columns the admin can show or hide.
type ProductTableColumn = Literal[
    "row",
    "name",
    "sku",
    "category",
    "brand",
    "unit",
    "price",
    "competitor_price",
    "price_diff",
    "suggested_price",
    "stock",
]


class SettingsOut(BaseModel):
    low_stock_threshold: int
    default_page_size: int
    sync_interval_minutes: int
    competitor_sync_interval_minutes: int
    default_competitor_store: Literal["digikala", "technolife"]
    suggested_price_formulas: list[SuggestedPriceFormulaOut]
    product_table_columns: list[ProductTableColumn]


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    low_stock_threshold: int | None = Field(default=None, ge=0, le=1_000_000)
    default_page_size: Literal[0, 10, 20, 50, 100, 500] | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    competitor_sync_interval_minutes: int | None = Field(default=None, ge=15, le=10080)
    default_competitor_store: Literal["digikala", "technolife"] | None = None
    suggested_price_formulas: list[SuggestedPriceFormulaIn] | None = None
    product_table_columns: list[ProductTableColumn] | None = None

    @field_validator("product_table_columns")
    @classmethod
    def validate_product_table_columns(
        cls, columns: list[ProductTableColumn] | None
    ) -> list[ProductTableColumn] | None:
        if columns is None:
            return None
        if not columns:
            raise ValueError("حداقل یک ستون باید نمایش داده شود")
        if len(columns) != len(set(columns)):
            raise ValueError("ستون تکراری مجاز نیست")
        return columns

    @field_validator("suggested_price_formulas")
    @classmethod
    def validate_unique_formula_top_groups(
        cls, formulas: list[SuggestedPriceFormulaIn] | None
    ) -> list[SuggestedPriceFormulaIn] | None:
        if formulas is None:
            return None
        top_groups = [formula.top_group for formula in formulas]
        if len(top_groups) != len(set(top_groups)):
            raise ValueError("برای هر دسته‌بندی فقط یک وزن می‌توان ثبت کرد")
        return formulas
