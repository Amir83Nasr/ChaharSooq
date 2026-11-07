"""Product handlers — paginated list + create + inventory summary."""

import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_db_readonly, require_admin
from app.api.openapi import NOT_FOUND, UNAUTHORIZED, VALIDATION_ERROR
from app.models import Admin
from app.schemas import (
    InventorySummaryOut,
    ProductIn,
    ProductOut,
    ProductPage,
    ProductPriceBoundsUpdate,
)
from app.services import (
    INVALID_CATEGORY_ERROR,
    InvalidCategoryError,
    ProductNotFoundError,
    ProductService,
)
from app.services.competitor import CompetitorService

router = APIRouter(tags=["Products"], responses={401: UNAUTHORIZED})


@router.get(
    "/products",
    response_model=ProductPage,
    summary="List products",
    description=(
        "Server-side search, filtering, sorting, and pagination over the local "
        "catalog mirror. `page_size=0` returns every match without an offset; "
        "an explicit size is capped at 500."
    ),
    responses={422: VALIDATION_ERROR},
)
def list_products(
    q: str = Query(default="", description="Case-insensitive match on name, SKU, and group names."),
    category_id: int | None = Query(default=None, ge=1, description="Exact category id."),
    top_group: str | None = Query(
        default=None,
        max_length=200,
        description="Section filter: فرش، مبلمان، or لوازم خانگی.",
    ),
    main_group: str | None = Query(
        default=None, max_length=200, description="Exact raw group name."
    ),
    min_price: int | None = Query(default=None, ge=0, description="Minimum unit price, Toman."),
    max_price: int | None = Query(default=None, ge=0, description="Maximum unit price, Toman."),
    competitor_store: Literal["digikala", "technolife", "sofa", "digifresh", "other"]
    | None = Query(default=None, description="Only products with a fresh price from this store."),
    min_competitor_price: int | None = Query(
        default=None, ge=0, description="Minimum fresh competitor price."
    ),
    max_competitor_price: int | None = Query(
        default=None, ge=0, description="Maximum fresh competitor price."
    ),
    min_stock: int | None = Query(default=None, ge=0, description="Minimum stock."),
    max_stock: int | None = Query(default=None, ge=0, description="Maximum stock."),
    in_stock: bool | None = Query(
        default=None, description="`true` for stock > 0, `false` for zero stock."
    ),
    sort: Literal["newest", "cheapest", "most_expensive"] = Query(
        default="newest", description="`newest` by id, or unit-price order."
    ),
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(
        default=0,
        ge=0,
        le=500,
        description="0 returns all matches; explicit sizes are capped at 500.",
    ),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> ProductPage:
    items, total = ProductService(session).list(
        query=q,
        category_id=category_id,
        top_group=top_group,
        main_group=main_group,
        min_price=min_price,
        max_price=max_price,
        competitor_store=competitor_store,
        min_competitor_price=min_competitor_price,
        max_competitor_price=max_competitor_price,
        min_stock=min_stock,
        max_stock=max_stock,
        in_stock=in_stock,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    response_page_size = page_size if page_size > 0 else len(items)
    # "Show all" ignores the requested page offset, so always report page 1
    # to keep row numbers and totalPages consistent on the client.
    response_page = page if page_size > 0 else 1
    competitor_prices = CompetitorService(session).prices_for_products({p.id for p in items})
    return ProductPage(
        items=[
            ProductOut.model_validate(p).model_copy(
                update={"competitor_prices": competitor_prices.get(p.id, [])}
            )
            for p in items
        ],
        total=total,
        page=response_page,
        page_size=response_page_size,
    )


@router.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
    description=(
        "Creates a manual catalog row. Prices are integer Toman; an unknown "
        "`category_id` is rejected with `422`."
    ),
    responses={422: VALIDATION_ERROR},
)
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


@router.patch(
    "/products/{product_id}/price-bounds",
    response_model=ProductOut,
    summary="Update product price bounds",
    description=(
        "Sets the per-product clamp for the suggested price: m% below and n% "
        "above the Parsina base price. A null value disables that side. The "
        "suggested price never leaves `[Pb × (1 − m), Pb × (1 + n)]`."
    ),
    responses={404: NOT_FOUND, 422: VALIDATION_ERROR},
)
def update_product_price_bounds(
    product_id: int,
    payload: ProductPriceBoundsUpdate,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> ProductOut:
    try:
        product = ProductService(session).update_price_bounds(product_id, payload)
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کالا پیدا نشد",
        ) from None
    return ProductOut.model_validate(product)


@router.get(
    "/products/summary",
    response_model=InventorySummaryOut,
    summary="Inventory summary",
    description=(
        "Catalog totals computed server-side: total, in stock, low stock "
        "(below `threshold`), out of stock, and stock value in Toman."
    ),
    responses={422: VALIDATION_ERROR},
)
def products_summary(
    threshold: int = Query(default=10, ge=0, description="Low-stock cutoff."),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> InventorySummaryOut:
    summary = ProductService(session).summary(low_stock_threshold=threshold)
    return InventorySummaryOut(**summary)


@router.get(
    "/products/groups",
    response_model=list[str],
    summary="List product groups",
    description=(
        "Distinct raw Parsina `main_group_name` values used by the catalog "
        "filters. The response carries a weak `ETag` and a 60-second private cache hint."
    ),
)
def product_groups(
    response: Response,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[str]:
    groups = ProductService(session).groups()
    etag = hashlib.sha256("|".join(groups).encode()).hexdigest()[:32]
    response.headers["Cache-Control"] = "private, max-age=60"
    response.headers["ETag"] = f'"{etag}"'
    return groups
