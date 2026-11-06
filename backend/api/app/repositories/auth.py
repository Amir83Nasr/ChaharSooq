"""Auth repositories — direct Admin/AdminSession queries, no business rules."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Admin, AdminSession


class AdminRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, admin_id: int) -> Admin | None:
        return self._session.get(Admin, admin_id)

    def get_by_username(self, username: str) -> Admin | None:
        return (
            self._session.execute(select(Admin).where(Admin.username == username))
            .scalars()
            .one_or_none()
        )


class AdminSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: AdminSession) -> AdminSession:
        self._session.add(row)
        self._session.flush()
        return row

    def get_by_token_hash(self, token_hash: str) -> AdminSession | None:
        return (
            self._session.execute(select(AdminSession).where(AdminSession.token_hash == token_hash))
            .scalars()
            .one_or_none()
        )

    def delete_by_token_hash(self, token_hash: str) -> None:
        self._session.execute(delete(AdminSession).where(AdminSession.token_hash == token_hash))

    def delete_for_admin(self, admin_id: int) -> None:
        """Single-session enforcement — invalidate older logins on new login."""
        self._session.execute(delete(AdminSession).where(AdminSession.admin_id == admin_id))

    def delete_expired(self, now: datetime) -> None:
        self._session.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
