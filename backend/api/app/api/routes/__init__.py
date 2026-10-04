"""Thin route handlers — validation + status codes only, logic in services."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.dependencies import get_current_admin, get_db, require_admin
from app.models import Admin
from app.schemas import (
    CategoryIn,
    CategoryOut,
    ErrorEnvelope,
    LoginIn,
    LoginOut,
    MeOut,
    ProductIn,
    ProductOut,
    ProductPage,
)
from app.services import (
    INVALID_CATEGORY_ERROR,
    LOGIN_ERROR,
    AuthService,
    CategoryService,
    InvalidCategoryError,
    ProductService,
)

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
    category_id: int | None = Query(default=None, ge=1),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    in_stock: bool | None = Query(default=None),
    sort: Literal["newest", "cheapest", "most_expensive"] = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> ProductPage:
    items, total = ProductService(session).list(
        query=q,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort=sort,
        page=page,
        page_size=page_size,
    )
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
    try:
        product = ProductService(session).create(payload)
    except InvalidCategoryError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=INVALID_CATEGORY_ERROR,
        ) from None
    return ProductOut.model_validate(product)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in CategoryService(session).list()]


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryIn,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> CategoryOut:
    try:
        category = CategoryService(session).create(payload)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این دسته‌بندی قبلاً ثبت شده است",
        ) from None
    return CategoryOut.model_validate(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> Response:
    result = CategoryService(session).delete(category_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="یافت نشد")
    if result == "in_use":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "category_in_use",
                    "message": "این دسته دارای محصول است و حذف نمی‌شود",
                }
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
