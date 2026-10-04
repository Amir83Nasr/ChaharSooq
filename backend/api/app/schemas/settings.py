"""Settings boundary schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SettingsOut(BaseModel):
    low_stock_threshold: int
    default_page_size: int


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    low_stock_threshold: int | None = Field(default=None, ge=0, le=1_000_000)
    default_page_size: Literal[10, 20, 50] | None = None
