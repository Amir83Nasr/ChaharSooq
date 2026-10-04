"""Business logic lives here — never in route handlers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models import Admin, AdminSession, Product
from app.repositories import ProductRepository
from app.schemas import LoginIn, ProductIn

LOGIN_ERROR = "نام کاربری یا گذرواژه نادرست است"


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


class ProductService:
    def __init__(self, session: Session) -> None:
        self._repos = ProductRepository(session)

    def list(self, *, query: str, page: int, page_size: int) -> tuple[list[Product], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        return self._repos.list(query=query.strip(), page=page, page_size=page_size)

    def create(self, payload: ProductIn) -> Product:
        return self._repos.add(Product(**payload.model_dump()))
