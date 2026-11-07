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
    "suggested_price_change",
    "stock",
]


class SettingsOut(BaseModel):
    low_stock_threshold: int = Field(description="Stock at or below this value counts as low.")
    default_page_size: int = Field(description="Products per page; 0 means show all.")
    sync_interval_minutes: int = Field(description="Product sync interval.")
    competitor_sync_interval_minutes: int = Field(description="Bulk competitor refresh interval.")
    default_competitor_store: Literal["digikala", "technolife"] = Field(
        description="Store pre-selected when adding a competitor link."
    )
    suggested_price_formulas: list[SuggestedPriceFormulaOut] = Field(
        description="Per-group competitor weight for the suggested price."
    )
    product_table_columns: list[ProductTableColumn] = Field(
        description="Visible product-table columns, in canonical order."
    )


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "low_stock_threshold": 10,
                    "default_page_size": 20,
                    "sync_interval_minutes": 720,
                    "competitor_sync_interval_minutes": 1440,
                    "default_competitor_store": "digikala",
                    "suggested_price_formulas": [{"top_group": "فرش", "weight": 0.4}],
                    "product_table_columns": ["name", "price", "stock"],
                }
            ]
        },
    )

    low_stock_threshold: int | None = Field(
        default=None, ge=0, le=1_000_000, description="Stock at or below this value is low."
    )
    default_page_size: Literal[0, 10, 20, 50, 100, 500] | None = Field(
        default=None, description="0 means show all products."
    )
    sync_interval_minutes: int | None = Field(
        default=None, ge=1, le=10080, description="Product sync interval, in minutes."
    )
    competitor_sync_interval_minutes: int | None = Field(
        default=None, ge=15, le=10080, description="Bulk competitor refresh interval, in minutes."
    )
    default_competitor_store: Literal["digikala", "technolife"] | None = Field(
        default=None, description="Store pre-selected when adding a competitor link."
    )
    suggested_price_formulas: list[SuggestedPriceFormulaIn] | None = Field(
        default=None, description="Replaces the saved list; omit to keep the current weights."
    )
    product_table_columns: list[ProductTableColumn] | None = Field(
        default=None,
        description="Replaces the visible list (at least one column, no duplicates).",
    )

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
