"""Suggested price boundary schemas.

Weights stay per catalog section: one weight per top group, shared by both
formulas. The per-product `pricing_mode` selects which formula consumes it —
`exact_competitor` blends the Parsina base with a direct competitor price,
while `similar_product` scales the linked product's daily price change.
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
            "Source share (0–1): used as the competitor share in the weighted "
            "blend for `exact_competitor` products, and as the daily-change "
            "scale for `similar_product` products."
        ),
    )


class SuggestedPriceFormulaOut(SuggestedPriceFormulaIn):
    pass
