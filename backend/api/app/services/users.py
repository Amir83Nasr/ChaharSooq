"""User management — create/list/delete login accounts (admin-only routes)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Admin
from app.models.auth import ROLE_ADMIN
from app.repositories import AdminRepository, AdminSessionRepository
from app.schemas import UserCreateIn


class UsernameTakenError(Exception):
    """Another account already uses this username."""


class UserNotFoundError(Exception):
    """No account exists for the requested id."""


class CannotDeleteSelfError(Exception):
    """An admin cannot delete the account they are signed in with."""


class LastAdminError(Exception):
    """The last remaining admin account cannot be deleted."""


class UserService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._admins = AdminRepository(session)
        self._sessions = AdminSessionRepository(session)

    def list(self) -> list[Admin]:
        return self._admins.list_all()

    def create(self, payload: UserCreateIn) -> Admin:
        if self._admins.get_by_username(payload.username) is not None:
            raise UsernameTakenError
        admin = Admin(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
        )
        try:
            return self._admins.add(admin)
        except IntegrityError:
            # The unique index is the final guard for the check-then-insert race.
            self._session.rollback()
            raise UsernameTakenError from None

    def delete(self, user_id: int, *, actor_id: int) -> None:
        target = self._admins.get(user_id)
        if target is None:
            raise UserNotFoundError
        if target.id == actor_id:
            raise CannotDeleteSelfError
        if target.role == ROLE_ADMIN and self._admins.count_admins() <= 1:
            raise LastAdminError
        # Sessions must go first: the FK has no cascade and an orphaned
        # session would keep a deleted account usable until expiry.
        self._sessions.delete_for_admin(target.id)
        self._admins.delete(target)
