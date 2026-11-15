"""Auth handlers — login/logout/me + session cookie."""

from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin, get_db
from app.api.openapi import RATE_LIMITED, UNAUTHORIZED, VALIDATION_ERROR
from app.core.config import get_settings
from app.models import Admin
from app.schemas import LoginIn, LoginOut, MeOut, UserRole
from app.services import LOGIN_ERROR, AuthService

router = APIRouter(tags=["Auth"])


def _session_cookie_policy() -> tuple[str, bool, Literal["lax", "none"]]:
    """Return (cookie name, secure, samesite) for login and logout.

    SESSION_COOKIE_SECURE controls the Secure attribute for same-site cookies.
    SameSite=None requires Secure, so the attribute is forced on even when the
    operator explicitly disables SESSION_COOKIE_SECURE.
    """
    settings = get_settings()
    # ponytail: cross-domain prod (Vercel + API host جدا) به SESSION_SAMESITE=none نیاز دارد.
    samesite: Literal["lax", "none"] = "none" if settings.session_samesite == "none" else "lax"
    secure = True if samesite == "none" else bool(settings.session_cookie_secure)
    return settings.session_cookie_name, secure, samesite


def _session_cookie(token: str | None, *, max_age: int | None) -> dict[str, object]:
    key, secure, samesite = _session_cookie_policy()
    return {
        "key": key,
        "value": token or "",
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "path": "/",
        **({"max_age": max_age} if max_age else {"expires": 0}),
    }


@router.post(
    "/auth/login",
    response_model=LoginOut,
    status_code=status.HTTP_200_OK,
    summary="Log in",
    description=(
        "Validates the admin credentials and rotates the server-side session, "
        "returning an HttpOnly cookie. Rate-limited to 10 attempts per minute "
        "per IP and username."
    ),
    responses={401: UNAUTHORIZED, 422: VALIDATION_ERROR, 429: RATE_LIMITED},
)
def login(payload: LoginIn, response: Response, session: Session = Depends(get_db)) -> LoginOut:  # noqa: B008
    token = AuthService(session).login(payload)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_ERROR)
    ttl = get_settings().session_ttl_hours * 3600
    response.set_cookie(**_session_cookie(token, max_age=ttl))  # type: ignore[arg-type]
    return LoginOut(ok=True)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description="Deletes the server-side session and clears the session cookie.",
    responses={204: {"description": "Session cookie cleared."}},
)
def logout(request: Request, response: Response, session: Session = Depends(get_db)) -> None:  # noqa: B008
    key, secure, samesite = _session_cookie_policy()
    token = request.cookies.get(key)
    if token:
        AuthService(session).logout(token)
    response.delete_cookie(key=key, path="/", secure=secure, samesite=samesite)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get(
    "/auth/me",
    response_model=MeOut,
    summary="Current account",
    description="Returns the id, username, and role behind the current session cookie.",
    responses={401: UNAUTHORIZED},
)
def me(admin: Admin | None = Depends(get_current_admin)) -> MeOut:  # noqa: B008
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_ERROR)
    return MeOut(id=admin.id, username=admin.username, role=cast(UserRole, admin.role))
