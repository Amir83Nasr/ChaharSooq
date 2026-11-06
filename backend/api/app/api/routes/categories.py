"""Category handlers — list/create/delete with in-use guard."""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_db_readonly, require_admin
from app.models import Admin
from app.schemas import CategoryIn, CategoryOut
from app.services import CategoryService

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    response: Response,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[CategoryOut]:
    rows = [CategoryOut.model_validate(c) for c in CategoryService(session).list()]
    etag = hashlib.sha256("|".join(f"{c.id}:{c.name}" for c in rows).encode()).hexdigest()[:32]
    response.headers["Cache-Control"] = "private, max-age=60"
    response.headers["ETag"] = f'"{etag}"'
    return rows


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
