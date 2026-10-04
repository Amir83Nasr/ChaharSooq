"""Pydantic boundary schemas — machine-readable in/out only."""

from app.schemas.auth import LoginIn, LoginOut, MeOut
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    InventorySummaryOut,
    ProductIn,
    ProductOut,
    ProductPage,
)
from app.schemas.common import ErrorBody, ErrorEnvelope
from app.schemas.settings import SettingsOut, SettingsUpdateIn

__all__ = [
    "CategoryIn",
    "CategoryOut",
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
]
