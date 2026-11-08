"""Env-managed owner account — bootstrapped on every API start.

The owner is the highest-privilege account and is never created from the
panel. `OWNER_USERNAME` / `OWNER_PASSWORD` are the source of truth: the
account is created when missing, re-hashed when the password changes, and
kept as the only `owner` row. Secrets are never logged.
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.security import hash_password, verify_password
from app.models import Admin
from app.models.auth import ROLE_ADMIN, ROLE_OWNER
from app.repositories import AdminRepository, AdminSessionRepository

log = logging.getLogger("charsooq.owner")

_BOOTSTRAP_ATTEMPTS = 3


class OwnerBootstrapService:
    def __init__(self, session: Session) -> None:
        self._admins = AdminRepository(session)
        self._sessions = AdminSessionRepository(session)

    def apply(self, username: str, password: str) -> None:
        """Create/update the env owner and demote any other owner rows."""
        username = username.strip()
        owner = self._admins.get_by_username(username)
        if owner is None:
            # Flush inside the caller's transaction so the unique username
            # index is the final guard against two replicas racing on boot.
            owner = self._admins.add(
                Admin(
                    username=username,
                    password_hash=hash_password(password),
                    role=ROLE_OWNER,
                )
            )
        else:
            owner.role = ROLE_OWNER
            if not verify_password(owner.password_hash, password):
                owner.password_hash = hash_password(password)
                # A changed env password invalidates existing sessions.
                self._sessions.delete_for_admin(owner.id)

        # Single-owner invariant: the env account is the only `owner` row.
        for other in self._admins.list_by_roles((ROLE_OWNER,)):
            if other.id != owner.id:
                other.role = ROLE_ADMIN


def bootstrap_owner() -> None:
    """Ensure the env owner exists. No-op in tests or without a password."""
    settings = get_settings()
    if settings.app_env == "test":
        return
    if not settings.owner_password:
        log.info("OWNER_PASSWORD is not set; skipping env-managed owner bootstrap")
        return

    for attempt in range(1, _BOOTSTRAP_ATTEMPTS + 1):
        with Session(get_engine()) as session:
            try:
                OwnerBootstrapService(session).apply(
                    settings.owner_username, settings.owner_password
                )
                session.commit()
            except IntegrityError:
                # Another replica created the same username first; retry now
                # that the row exists (the next pass takes the update branch).
                session.rollback()
                if attempt == _BOOTSTRAP_ATTEMPTS:
                    raise
                continue
        log.info("env owner account %r ensured", settings.owner_username)
        return
