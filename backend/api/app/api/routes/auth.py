"""Auth handlers — login/logout/me + session cookie."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.config import get_settings
from app.models import Admin
from app.schemas import ErrorEnvelope, LoginIn, LoginOut, MeOut
from app.services import LOGIN_ERROR, AuthService

router = APIRouter()


def _session_cookie(token: str | None, *, max_age: int | None) -> dict[str, object]:
    settings = get_settings()
    # ponytail: cross-domain prod (Vercel + API host جدا) به SESSION_SAMESITE=none نیاز دارد.
    samesite: str = "none" if settings.session_samesite == "none" else "lax"
    secure = True if samesite == "none" else settings.is_production
    return {
        "key": settings.session_cookie_name,
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
    responses={401: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope}},
)
def login(payload: LoginIn, response: Response, session: Session = Depends(get_db)) -> LoginOut:  # noqa: B008
    token = AuthService(session).login(payload)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_ERROR)
    ttl = get_settings().session_ttl_hours * 3600
    response.set_cookie(**_session_cookie(token, max_age=ttl))  # type: ignore[arg-type]
    return LoginOut(ok=True)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: Session = Depends(get_db)) -> None:  # noqa: B008
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        AuthService(session).logout(token)
    settings = get_settings()
    samesite: str = "none" if settings.session_samesite == "none" else "lax"
    secure = True if samesite == "none" else settings.is_production
    response.delete_cookie(
        key=settings.session_cookie_name, path="/", secure=secure, samesite=samesite
    )
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/auth/me", response_model=MeOut)
def me(admin: Admin | None = Depends(get_current_admin)) -> MeOut:  # noqa: B008
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_ERROR)
    return MeOut(username=admin.username)
