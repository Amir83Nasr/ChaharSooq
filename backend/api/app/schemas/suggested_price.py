"""Suggested price boundary schemas.

One weight per pricing mode: `exact_competitor` blends the Parsina base with a
direct competitor price; `similar_product` scales the linked product's daily
price change. The mode is stored per product, not per catalog section.
"""

from pydantic import BaseModel, Field

from app.schemas.catalog import PricingMode

__all__ = ["SuggestedPriceFormulaIn", "SuggestedPriceFormulaOut"]


class SuggestedPriceFormulaIn(BaseModel):
    mode: PricingMode = Field(
        description=(
            "Pricing mode the weight applies to: `exact_competitor` (weighted "
            "blend with a direct competitor price) or `similar_product` "
            "(base adjusted by the linked product's daily price change)."
        )
    )
    weight: float = Field(
        ge=0,
        le=1,
        description=(
            "Source share (0–1): competitor price for `exact_competitor`, "
            "daily price change for `similar_product`."
        ),
    )


class SuggestedPriceFormulaOut(SuggestedPriceFormulaIn):
    pass
