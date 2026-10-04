"""Business logic lives here — never in route handlers."""

from app.services.auth import LOGIN_ERROR, AuthService
from app.services.catalog import CategoryService
from app.services.products import (
    INVALID_CATEGORY_ERROR,
    InvalidCategoryError,
    ProductService,
)
from app.services.settings import (
    ALLOWED_PAGE_SIZES,
    DEFAULT_LOW_STOCK_THRESHOLD,
    DEFAULT_PAGE_SIZE,
    DEFAULT_PAGE_SIZE_KEY,
    LOW_STOCK_THRESHOLD_KEY,
    SettingsService,
)

__all__ = [
    "LOGIN_ERROR",
    "INVALID_CATEGORY_ERROR",
    "LOW_STOCK_THRESHOLD_KEY",
    "DEFAULT_LOW_STOCK_THRESHOLD",
    "ALLOWED_PAGE_SIZES",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_PAGE_SIZE_KEY",
    "AuthService",
    "CategoryService",
    "InvalidCategoryError",
    "ProductService",
    "SettingsService",
]
