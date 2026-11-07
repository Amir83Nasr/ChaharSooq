"""Pydantic boundary schemas — machine-readable in/out only."""

from app.schemas.auth import LoginIn, LoginOut, MeOut
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    InventorySummaryOut,
    ProductIn,
    ProductOut,
    ProductPage,
    ProductPriceBoundsUpdate,
    SyncRunOut,
    SyncStatusOut,
)
from app.schemas.common import ErrorBody, ErrorEnvelope
from app.schemas.dashboard import (
    CatalogBrandOut,
    CatalogSectionOut,
    CompetitorGapOut,
    DashboardGroupOut,
    DashboardOverviewOut,
    DashboardSummaryOut,
)
from app.schemas.settings import SettingsOut, SettingsUpdateIn
from app.schemas.suggested_price import SuggestedPriceFormulaIn, SuggestedPriceFormulaOut

__all__ = [
    "CatalogBrandOut",
    "CatalogSectionOut",
    "CategoryIn",
    "CategoryOut",
    "CompetitorGapOut",
    "DashboardGroupOut",
    "DashboardOverviewOut",
    "DashboardSummaryOut",
    "ErrorBody",
    "ErrorEnvelope",
    "InventorySummaryOut",
    "LoginIn",
    "LoginOut",
    "MeOut",
    "ProductIn",
    "ProductOut",
    "ProductPage",
    "ProductPriceBoundsUpdate",
    "SettingsOut",
    "SettingsUpdateIn",
    "SuggestedPriceFormulaIn",
    "SuggestedPriceFormulaOut",
    "SyncRunOut",
    "SyncStatusOut",
]
