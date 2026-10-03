"""Thin route handlers — validation + status codes only, logic in services."""

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.dependencies import get_current_admin, get_db, require_admin
from app.models import Admin
from app.schemas import LoginIn, LoginOut, MeOut, ProductIn, ProductOut, ProductPage
from app.services import LOGIN_ERROR, AuthService, ProductService

router = APIRouter()


def _session_cookie(token: str | None, *, max_age: int | None) -> dict[str, object]:
    settings = get_settings()
    return {
        "key": settings.session_cookie_name,
        "value": token or "",
        "httponly": True,
        "secure": settings.is_production,
        "samesite": "lax",
        "path": "/",
        **({"max_age": max_age} if max_age else {"expires": 0}),
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/login", response_model=LoginOut, status_code=status.HTTP_200_OK)
def login(payload: LoginIn, response: Response, session: Session = Depends(get_db)) -> LoginOut:  # noqa: B008
    token = AuthService(session).login(payload)
    if token is None:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return LoginOut(ok=False)
    ttl = get_settings().session_ttl_hours * 3600
    response.set_cookie(**_session_cookie(token, max_age=ttl))  # type: ignore[arg-type]
    return LoginOut(ok=True)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: Session = Depends(get_db)) -> None:  # noqa: B008
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        AuthService(session).logout(token)
    response.delete_cookie(key=get_settings().session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/auth/me", response_model=MeOut)
def me(admin: Admin | None = Depends(get_current_admin)) -> MeOut:  # noqa: B008
    if admin is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_ERROR)
    return MeOut(username=admin.username)


@router.get("/products", response_model=ProductPage)
def list_products(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> ProductPage:
    items, total = ProductService(session).list(query=q, page=page, page_size=page_size)
    return ProductPage(
        items=[ProductOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductIn,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> ProductOut:
    return ProductOut.model_validate(ProductService(session).create(payload))
