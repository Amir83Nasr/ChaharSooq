"""Suggested price boundary schemas.

The suggested price is a weighted blend of the Parsina base price and a
competitor price; only the competitor weight is configurable per top group.
"""

from typing import Literal

from pydantic import BaseModel, Field

TopGroup = Literal["فرش", "مبلمان", "لوازم خانگی"]


class SuggestedPriceFormulaIn(BaseModel):
    top_group: TopGroup
    weight: float = Field(ge=0, le=1)


class SuggestedPriceFormulaOut(SuggestedPriceFormulaIn):
    pass
