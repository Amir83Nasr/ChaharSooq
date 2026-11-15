"""Suggested price boundary schemas.

Appliances and digital goods blend the Parsina base with a competitor price.
Furniture/carpet have no direct competitor price; the same weight scales the
linked product's daily price change instead.
"""

from pydantic import BaseModel, Field

from app.core.top_groups import TopGroup

__all__ = ["SuggestedPriceFormulaIn", "SuggestedPriceFormulaOut", "TopGroup"]


class SuggestedPriceFormulaIn(BaseModel):
    top_group: TopGroup = Field(description="Catalog section the weight applies to.")
    weight: float = Field(
        ge=0,
        le=1,
        description=(
            "Source share (0–1): competitor price for لوازم خانگی/کالای دیجیتال, "
            "daily price change for مبلمان/فرش."
        ),
    )


class SuggestedPriceFormulaOut(SuggestedPriceFormulaIn):
    pass
