"""Product handlers — paginated list + create + inventory summary."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models import Admin
from app.schemas import (
    InventorySummaryOut,
    ProductIn,
    ProductOut,
    ProductPage,
)
from app.services import (
    INVALID_CATEGORY_ERROR,
    InvalidCategoryError,
    ProductService,
)

router = APIRouter()


@router.get("/products", response_model=ProductPage)
def list_products(
    q: str = Query(default=""),
    category_id: int | None = Query(default=None, ge=1),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    min_stock: int | None = Query(default=None, ge=0),
    max_stock: int | None = Query(default=None, ge=0),
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
        min_stock=min_stock,
        max_stock=max_stock,
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


@router.get("/products/summary", response_model=InventorySummaryOut)
def products_summary(
    threshold: int = Query(default=10, ge=0),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> InventorySummaryOut:
    summary = ProductService(session).summary(low_stock_threshold=threshold)
    return InventorySummaryOut(**summary)
