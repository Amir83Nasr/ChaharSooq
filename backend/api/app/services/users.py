"""User management — create/list/delete login accounts (owner/admin routes)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Admin
from app.models.auth import ROLE_ADMIN, ROLE_OWNER, ROLE_VIEWER
from app.repositories import AdminRepository, AdminSessionRepository
from app.schemas import UserCreateIn


class UsernameTakenError(Exception):
    """Another account already uses this username."""


class UserNotFoundError(Exception):
    """No account exists for the requested id."""


class CannotDeleteSelfError(Exception):
    """A management account cannot delete the account it is signed in with."""


class CannotDeleteOwnerError(Exception):
    """The env-managed owner cannot be deleted from the panel."""


class LastAdminError(Exception):
    """The last remaining admin account cannot be deleted."""


class ForbiddenRoleError(Exception):
    """An admin tried to create another admin; only the owner may."""


class UserService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._admins = AdminRepository(session)
        self._sessions = AdminSessionRepository(session)

    def list(self, *, actor: Admin) -> list[Admin]:
        """Owner sees every account; an admin sees only viewers."""
        if actor.role == ROLE_OWNER:
            return self._admins.list_all()
        return self._admins.list_by_roles((ROLE_VIEWER,))

    def create(self, payload: UserCreateIn, *, actor: Admin) -> Admin:
        if payload.role == ROLE_ADMIN and actor.role != ROLE_OWNER:
            raise ForbiddenRoleError
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

    def delete(self, user_id: int, *, actor: Admin) -> None:
        target = self._admins.get(user_id)
        if target is None:
            raise UserNotFoundError
        if target.id == actor.id:
            raise CannotDeleteSelfError
        # An admin may only see/manage viewers; anything higher is reported as
        # missing so admin usernames never leak through the endpoint.
        if actor.role != ROLE_OWNER and target.role != ROLE_VIEWER:
            raise UserNotFoundError
        if target.role == ROLE_OWNER:
            raise CannotDeleteOwnerError
        if target.role == ROLE_ADMIN and self._admins.count_admins() <= 1:
            raise LastAdminError
        # Sessions must go first: the FK has no cascade and an orphaned
        # session would keep a deleted account usable until expiry.
        self._sessions.delete_for_admin(target.id)
        self._admins.delete(target)
