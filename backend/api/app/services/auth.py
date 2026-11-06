"""Auth service — login/logout/session lookup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, new_session_token, verify_password
from app.models import Admin, AdminSession
from app.repositories import AdminRepository, AdminSessionRepository
from app.schemas import LoginIn

LOGIN_ERROR = "نام کاربری یا گذرواژه نادرست است"


class AuthService:
    def __init__(self, session: Session) -> None:
        self._admins = AdminRepository(session)
        self._sessions = AdminSessionRepository(session)

    def login(self, payload: LoginIn) -> str | None:
        admin = self._admins.get_by_username(payload.username)
        if admin is None or not verify_password(admin.password_hash, payload.password):
            return None
        now = datetime.now(UTC)
        self._sessions.delete_expired(now)
        # Session rotation: a fresh login invalidates older sessions so a
        # leaked cookie stops working as soon as the admin logs in again.
        self._sessions.delete_for_admin(admin.id)
        token = new_session_token()
        ttl = timedelta(hours=get_settings().session_ttl_hours)
        self._sessions.add(
            AdminSession(
                admin_id=admin.id,
                token_hash=hash_token(token),
                expires_at=now + ttl,
            )
        )
        return token

    def logout(self, token: str) -> None:
        self._sessions.delete_by_token_hash(hash_token(token))

    def current_admin(self, token: str | None) -> Admin | None:
        if not token:
            return None
        session = self._sessions.get_by_token_hash(hash_token(token))
        expires_at = session.expires_at if session else None
        if session is None or expires_at is None:
            return None
        aware_expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if aware_expiry <= datetime.now(UTC):
            return None
        return self._admins.get(session.admin_id)
