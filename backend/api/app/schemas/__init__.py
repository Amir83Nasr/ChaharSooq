"""Pydantic boundary schemas — machine-readable in/out only."""

from app.schemas.auth import LoginIn, LoginOut, MeOut
from app.schemas.backup import (
    BackupOut,
    BackupSettingsOut,
    BackupSettingsUpdateIn,
)
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    InventorySummaryOut,
    ProductCompetitorFlagUpdate,
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
from app.schemas.parsina import ParsinaConnectionIn, ParsinaConnectionOut
from app.schemas.settings import SettingsOut, SettingsUpdateIn
from app.schemas.suggested_price import SuggestedPriceFormulaIn, SuggestedPriceFormulaOut
from app.schemas.users import AssignableRole, UserCreateIn, UserOut, UserRole

__all__ = [
    "AssignableRole",
    "BackupOut",
    "BackupSettingsOut",
    "BackupSettingsUpdateIn",
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
    "ParsinaConnectionIn",
    "ParsinaConnectionOut",
    "ProductCompetitorFlagUpdate",
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
    "UserCreateIn",
    "UserOut",
    "UserRole",
]
