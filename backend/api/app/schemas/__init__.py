"""Pydantic boundary schemas — machine-readable in/out only."""

from app.schemas.auth import LoginIn, LoginOut, MeOut
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    InventorySummaryOut,
    ProductIn,
    ProductOut,
    ProductPage,
    SyncRunOut,
    SyncStatusOut,
)
from app.schemas.common import ErrorBody, ErrorEnvelope
from app.schemas.dashboard import (
    AttentionItemOut,
    AttentionOut,
    CompetitorGapOut,
    DashboardGroupOut,
    DashboardOverviewOut,
)
from app.schemas.settings import SettingsOut, SettingsUpdateIn
from app.schemas.suggested_price import SuggestedPriceFormulaIn, SuggestedPriceFormulaOut

__all__ = [
    "AttentionItemOut",
    "AttentionOut",
    "CategoryIn",
    "CategoryOut",
    "CompetitorGapOut",
    "DashboardGroupOut",
    "DashboardOverviewOut",
    "ErrorBody",
    "ErrorEnvelope",
    "InventorySummaryOut",
    "LoginIn",
    "LoginOut",
    "MeOut",
    "ProductIn",
    "ProductOut",
    "ProductPage",
    "SettingsOut",
    "SettingsUpdateIn",
    "SuggestedPriceFormulaIn",
    "SuggestedPriceFormulaOut",
    "SyncRunOut",
    "SyncStatusOut",
]
