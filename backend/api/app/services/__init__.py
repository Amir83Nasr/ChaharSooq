"""Business logic lives here — never in route handlers."""

from app.services.auth import LOGIN_ERROR, AuthService
from app.services.catalog import CategoryService
from app.services.dashboard import DashboardService
from app.services.exports import (
    EXPORT_TOO_LARGE_MESSAGE,
    ExportService,
    ExportTooLargeError,
)
from app.services.products import (
    INVALID_CATEGORY_ERROR,
    InvalidCategoryError,
    ProductNotFoundError,
    ProductService,
)
from app.services.settings import (
    ALLOWED_COMPETITOR_STORES,
    ALLOWED_PAGE_SIZES,
    COMPETITOR_SYNC_INTERVAL_KEY,
    DEFAULT_COMPETITOR_STORE,
    DEFAULT_COMPETITOR_STORE_KEY,
    DEFAULT_COMPETITOR_SYNC_INTERVAL_MINUTES,
    DEFAULT_LOW_STOCK_THRESHOLD,
    DEFAULT_PAGE_SIZE,
    DEFAULT_PAGE_SIZE_KEY,
    LOW_STOCK_THRESHOLD_KEY,
    SYNC_INTERVAL_KEY,
    SettingsService,
)
from app.services.users import (
    CannotDeleteOwnerError,
    CannotDeleteSelfError,
    ForbiddenRoleError,
    LastAdminError,
    UsernameTakenError,
    UserNotFoundError,
    UserService,
)

__all__ = [
    "LOGIN_ERROR",
    "INVALID_CATEGORY_ERROR",
    "LOW_STOCK_THRESHOLD_KEY",
    "DEFAULT_LOW_STOCK_THRESHOLD",
    "ALLOWED_PAGE_SIZES",
    "ALLOWED_COMPETITOR_STORES",
    "DEFAULT_COMPETITOR_STORE",
    "DEFAULT_COMPETITOR_STORE_KEY",
    "COMPETITOR_SYNC_INTERVAL_KEY",
    "DEFAULT_COMPETITOR_SYNC_INTERVAL_MINUTES",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_PAGE_SIZE_KEY",
    "AuthService",
    "CannotDeleteOwnerError",
    "CannotDeleteSelfError",
    "CategoryService",
    "DashboardService",
    "EXPORT_TOO_LARGE_MESSAGE",
    "ExportService",
    "ExportTooLargeError",
    "ForbiddenRoleError",
    "InvalidCategoryError",
    "LastAdminError",
    "ProductService",
    "ProductNotFoundError",
    "SettingsService",
    "SYNC_INTERVAL_KEY",
    "UsernameTakenError",
    "UserNotFoundError",
    "UserService",
]
