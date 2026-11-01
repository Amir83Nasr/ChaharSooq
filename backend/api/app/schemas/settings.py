"""Settings boundary schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.suggested_price import SuggestedPriceFormulaIn, SuggestedPriceFormulaOut


class SettingsOut(BaseModel):
    low_stock_threshold: int
    default_page_size: int
    sync_interval_minutes: int
    suggested_price_formulas: list[SuggestedPriceFormulaOut]


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    low_stock_threshold: int | None = Field(default=None, ge=0, le=1_000_000)
    default_page_size: Literal[0, 10, 20, 50, 100, 500] | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    suggested_price_formulas: list[SuggestedPriceFormulaIn] | None = None

    @field_validator("suggested_price_formulas")
    @classmethod
    def validate_unique_formula_categories(
        cls, formulas: list[SuggestedPriceFormulaIn] | None
    ) -> list[SuggestedPriceFormulaIn] | None:
        if formulas is None:
            return None
        category_ids = [formula.category_id for formula in formulas]
        if len(category_ids) != len(set(category_ids)):
            raise ValueError("برای هر دسته‌بندی فقط یک فرمول می‌توان ثبت کرد")
        return formulas
