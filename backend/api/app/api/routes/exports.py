"""CSV export handlers — filtered catalog and competitor listings."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_readonly, require_user
from app.api.openapi import CONFLICT, UNAUTHORIZED, VALIDATION_ERROR
from app.models import Admin
from app.services import (
    EXPORT_TOO_LARGE_MESSAGE,
    ExportService,
    ExportTooLargeError,
    ProductService,
)

router = APIRouter(tags=["Exports"], responses={401: UNAUTHORIZED})

StoreFilter = Literal["digikala", "technolife", "sofa", "digifresh", "other"]
ListingStatus = Literal[
    "pending", "success", "not_found", "unavailable", "blocked", "failed", "manual"
]
ProductSort = Literal["newest", "cheapest", "most_expensive"]
MarketFilter = Literal["digikala", "technolife", "sofa", "digifresh"]
ExportScope = Literal["filtered", "all"]

_EXPORT_DESCRIPTION = (
    "Streams a UTF-8 CSV (with BOM, comma-separated) for Excel. Headers, "
    "digits, and dates are Persian/Jalali, unlike the JSON API. Filters mirror "
    "`GET /products`; omit them for a full export. The file is capped at "
    "50,000 rows (`export_too_large` above that)."
)


def _too_large() -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "export_too_large",
                "message": EXPORT_TOO_LARGE_MESSAGE,
            }
        },
    )


@router.get(
    "/exports/products.csv",
    summary="Export products as CSV",
    description=_EXPORT_DESCRIPTION,
    responses={409: CONFLICT, 422: VALIDATION_ERROR},
)
def export_products_csv(
    q: str = Query(default="", description="Case-insensitive match on name, SKU, and groups."),
    category_id: int | None = Query(default=None, ge=1, description="Exact category id."),
    top_group: str | None = Query(
        default=None, max_length=200, description="Section: فرش، مبلمان، or لوازم خانگی."
    ),
    main_group: str | None = Query(default=None, max_length=200, description="Raw group name."),
    min_price: int | None = Query(default=None, ge=0, description="Minimum unit price, Toman."),
    max_price: int | None = Query(default=None, ge=0, description="Maximum unit price, Toman."),
    competitor_store: StoreFilter | None = Query(  # noqa: B008
        default=None, description="Only products with a fresh price from this store."
    ),
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
    sort: ProductSort = Query(  # noqa: B008
        default="newest", description="Row order in the file."
    ),
    columns: str | None = Query(  # noqa: B008
        default=None,
        description="Comma-separated visible table column ids, in display order.",
    ),
    market: MarketFilter | None = Query(  # noqa: B008
        default=None,
        description="Selected competitor market for competitor/suggested columns.",
    ),
    scope: ExportScope | None = Query(  # noqa: B008
        default=None,
        description="Export mode hint for the default filename (filtered vs all).",
    ),
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> Response:
    service = ProductService(session)
    filters = service.filters(
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
    )
    column_ids = [part.strip() for part in columns.split(",")] if columns else None
    try:
        return ExportService(session).products_csv(
            filters=filters,
            sort=sort,
            columns=column_ids,
            market=market,
            scope=scope,
        )
    except ExportTooLargeError:
        return _too_large()


@router.get(
    "/exports/competitor-listings.csv",
    summary="Export competitor listings as CSV",
    description=(
        f"{_EXPORT_DESCRIPTION} Product filters (q, groups, price, stock) limit "
        "which products contribute their competitor links."
    ),
    responses={409: CONFLICT, 422: VALIDATION_ERROR},
)
def export_competitor_listings_csv(
    q: str = Query(default="", description="Case-insensitive match on product name/SKU/groups."),
    category_id: int | None = Query(default=None, ge=1, description="Exact category id."),
    top_group: str | None = Query(
        default=None, max_length=200, description="Section: فرش، مبلمان، or لوازم خانگی."
    ),
    main_group: str | None = Query(default=None, max_length=200, description="Raw group name."),
    min_price: int | None = Query(default=None, ge=0, description="Minimum product price."),
    max_price: int | None = Query(default=None, ge=0, description="Maximum product price."),
    min_stock: int | None = Query(default=None, ge=0, description="Minimum product stock."),
    max_stock: int | None = Query(default=None, ge=0, description="Maximum product stock."),
    in_stock: bool | None = Query(
        default=None, description="`true` for stock > 0, `false` for zero stock."
    ),
    store: StoreFilter | None = Query(  # noqa: B008
        default=None, description="Only this competitor store."
    ),
    status: ListingStatus | None = Query(  # noqa: B008
        default=None, description="Only this link status."
    ),
    is_active: bool | None = Query(
        default=None, description="`true` for active links, `false` for paused ones."
    ),
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> Response:
    filters = ProductService(session).filters(
        query=q,
        category_id=category_id,
        top_group=top_group,
        main_group=main_group,
        min_price=min_price,
        max_price=max_price,
        min_stock=min_stock,
        max_stock=max_stock,
        in_stock=in_stock,
    )
    try:
        return ExportService(session).competitor_listings_csv(
            filters=filters,
            store=store,
            status=status,
            is_active=is_active,
        )
    except ExportTooLargeError:
        return _too_large()
