"""Auth service — login/logout/session lookup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, new_session_token, verify_password
from app.models import Admin, AdminSession
from app.schemas import LoginIn

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
                admin_id=admin.id,
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
        return self._session.get(Admin, session.admin_id)
