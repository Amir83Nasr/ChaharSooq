"""Pydantic boundary schemas — machine-readable in/out only."""

from app.schemas.ai import AISettingsIn, AISettingsOut, AITestIn, AITestOut
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
    PricingMode,
    ProductIn,
    ProductOut,
    ProductPage,
    ProductPinUpdate,
    ProductPriceBoundsUpdate,
    ProductPricingModeUpdate,
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
from app.schemas.parsina import (
    CardexEntryOut,
    CardexPeriod,
    CardexSummaryOut,
    ParsinaConnectionIn,
    ParsinaConnectionOut,
    ProductCardexOut,
)
from app.schemas.settings import SettingsOut, SettingsUpdateIn
from app.schemas.suggested_price import SuggestedPriceFormulaIn, SuggestedPriceFormulaOut
from app.schemas.users import AssignableRole, UserCreateIn, UserOut, UserRole

__all__ = [
    "AISettingsIn",
    "AISettingsOut",
    "AITestIn",
    "AITestOut",
    "AssignableRole",
    "BackupOut",
    "CardexEntryOut",
    "CardexPeriod",
    "CardexSummaryOut",
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
    "ProductCardexOut",
    "ProductIn",
    "ProductOut",
    "ProductPage",
    "ProductPinUpdate",
    "ProductPricingModeUpdate",
    "ProductPriceBoundsUpdate",
    "PricingMode",
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
