"""FastAPI dependencies — DB session + admin auth guard."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_readonly_session as _get_readonly_session
from app.core.database import get_session as _get_session
from app.core.errors import FORBIDDEN, LOGIN_REQUIRED
from app.models import Admin
from app.models.auth import ROLE_ADMIN, ROLE_OWNER
from app.services import AuthService


def get_db() -> Iterator[Session]:
    yield from _get_session()


def get_db_readonly() -> Iterator[Session]:
    """Read-only session for GET handlers — never commits."""
    yield from _get_readonly_session()


# Documents the session cookie in OpenAPI (Swagger's Authorize dialog).
# `auto_error=False` keeps missing sessions on the shared error envelope
# instead of FastAPI's default 403.
_SESSION_COOKIE = APIKeyCookie(
    name=get_settings().session_cookie_name,
    auto_error=False,
    scheme_name="SessionCookie",
    description=(
        "HttpOnly cookie set by `POST /api/v1/auth/login`. Browsers send it "
        "automatically; other clients must forward it as a `Cookie` header."
    ),
)

SessionToken = Annotated[str | None, Security(_SESSION_COOKIE)]


def get_current_admin(
    token: SessionToken,
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> Admin | None:
    return AuthService(session).current_admin(token)


def require_user(
    token: SessionToken,
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> Admin:
    """Any signed-in account, regardless of role (read endpoints)."""
    admin = AuthService(session).current_admin(token)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_REQUIRED)
    return admin


def require_admin(
    admin: Annotated[Admin, Depends(require_user)],
) -> Admin:
    """Signed-in management account (`owner` or `admin`) — write endpoints.

    Owner-only operations are decided in the service layer from the actor's
    role, because `/users` is shared by both management roles.
    """
    if admin.role not in (ROLE_OWNER, ROLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN)
    return admin


def require_owner(
    admin: Annotated[Admin, Depends(require_user)],
) -> Admin:
    """Signed-in top-level owner account — sensitive configuration."""
    if admin.role != ROLE_OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN)
    return admin
