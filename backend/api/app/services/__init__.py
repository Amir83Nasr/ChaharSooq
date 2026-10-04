"""Business logic lives here — never in route handlers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models import Admin, AdminSession, Category, Product, Setting
from app.repositories import CategoryRepository, ProductRepository, ProductSort
from app.schemas import CategoryIn, LoginIn, ProductIn

LOGIN_ERROR = "نام کاربری یا گذرواژه نادرست است"
INVALID_CATEGORY_ERROR = "دسته‌بندی نامعتبر است"

LOW_STOCK_THRESHOLD_KEY = "low_stock_threshold"
DEFAULT_LOW_STOCK_THRESHOLD = 10


class InvalidCategoryError(ValueError):
    pass


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def login(self, payload: LoginIn) -> str | None:
        admin = self._session.execute(
            select(Admin).where(Admin.username == payload.username)
        ).scalar_one_or_none()
        if admin is None or not verify_password(admin.password_hash, payload.password):
            return None
        now = datetime.now(UTC)
        self._session.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
        token = new_session_token()
        ttl = timedelta(hours=get_settings().session_ttl_hours)
        self._session.add(
            AdminSession(
                token_hash=hash_token(token),
                expires_at=now + ttl,
            )
        )
        return token

    def logout(self, token: str) -> None:
        self._session.execute(
            delete(AdminSession).where(AdminSession.token_hash == hash_token(token))
        )

    def current_admin(self, token: str | None) -> Admin | None:
        if not token:
            return None
        session = self._session.execute(
            select(AdminSession).where(AdminSession.token_hash == hash_token(token))
        ).scalar_one_or_none()
        expires_at = session.expires_at if session else None
        if session is None or expires_at is None:
            return None
        aware_expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if aware_expiry <= datetime.now(UTC):
            return None
        return self._session.execute(select(Admin).limit(1)).scalar_one_or_none()

    def seed(self, username: str, password_hash: str) -> None:
        exists = self._session.execute(select(Admin.id).limit(1)).scalar_one_or_none()
        if exists is None:
            self._session.add(Admin(username=username, password_hash=hash_password(password_hash)))


class CategoryService:
    def __init__(self, session: Session) -> None:
        self._repos = CategoryRepository(session)

    def list(self) -> list[Category]:
        return self._repos.list()

    def create(self, payload: CategoryIn) -> Category:
        return self._repos.add(Category(name=payload.name.strip()))

    def delete(self, category_id: int) -> Category | None | str:
        """Return None when missing, "in_use" when products reference it."""
        category = self._repos.get(category_id)
        if category is None:
            return None
        if self._repos.product_count(category_id) > 0:
            return "in_use"
        self._repos.delete(category)
        return category


class ProductService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repos = ProductRepository(session)

    def list(
        self,
        *,
        query: str,
        category_id: int | None,
        min_price: int | None,
        max_price: int | None,
        min_stock: int | None,
        max_stock: int | None,
        in_stock: bool | None,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        if min_price is not None and max_price is not None and min_price > max_price:
            min_price, max_price = max_price, min_price
        return self._repos.list(
            query=query.strip(),
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            min_stock=min_stock,
            max_stock=max_stock,
            in_stock=in_stock,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def create(self, payload: ProductIn) -> Product:
        if payload.category_id is None:
            return self._repos.add(Product(**payload.model_dump()))
        if self._session.get(Category, payload.category_id) is None:
            raise InvalidCategoryError
        return self._repos.add(Product(**payload.model_dump()))


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_threshold(self) -> int:
        row = self._session.get(Setting, LOW_STOCK_THRESHOLD_KEY)
        if row is None:
            return DEFAULT_LOW_STOCK_THRESHOLD
        try:
            value = int(row.value)
        except ValueError:
            return DEFAULT_LOW_STOCK_THRESHOLD
        return max(value, 0)

    def update_threshold(self, threshold: int) -> int:
        row = self._session.get(Setting, LOW_STOCK_THRESHOLD_KEY)
        if row is None:
            row = Setting(key=LOW_STOCK_THRESHOLD_KEY, value=str(threshold))
            self._session.add(row)
        else:
            row.value = str(threshold)
        self._session.flush()
        return threshold
