"""Settings boundary schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.suggested_price import SuggestedPriceFormulaIn, SuggestedPriceFormulaOut


class SettingsOut(BaseModel):
    low_stock_threshold: int
    default_page_size: int
    sync_interval_minutes: int
    default_competitor_store: Literal["digikala", "technolife"]
    suggested_price_formulas: list[SuggestedPriceFormulaOut]


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    low_stock_threshold: int | None = Field(default=None, ge=0, le=1_000_000)
    default_page_size: Literal[0, 10, 20, 50, 100, 500] | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    default_competitor_store: Literal["digikala", "technolife"] | None = None
    suggested_price_formulas: list[SuggestedPriceFormulaIn] | None = None

    @field_validator("suggested_price_formulas")
    @classmethod
    def validate_unique_formula_top_groups(
        cls, formulas: list[SuggestedPriceFormulaIn] | None
    ) -> list[SuggestedPriceFormulaIn] | None:
        if formulas is None:
            return None
        top_groups = [formula.top_group for formula in formulas]
        if len(top_groups) != len(set(top_groups)):
            raise ValueError("برای هر دسته‌بندی فقط یک فرمول می‌توان ثبت کرد")
        return formulas
