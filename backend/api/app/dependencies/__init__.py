"""FastAPI dependencies — DB session + admin auth guard."""

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_session as _get_session
from app.models import Admin
from app.services import AuthService


def get_db() -> Iterator[Session]:
    yield from _get_session()


def _token_from_request(request: Request) -> str | None:
    from app.core.config import get_settings

    return request.cookies.get(get_settings().session_cookie_name)


def get_current_admin(
    request: Request,
    session: Session = Depends(get_db),  # noqa: B008
) -> Admin | None:
    return AuthService(session).current_admin(_token_from_request(request))


def require_admin(
    request: Request,
    session: Session = Depends(get_db),  # noqa: B008
) -> Admin:
    admin = AuthService(session).current_admin(_token_from_request(request))
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="نیاز به ورود است")
    return admin
