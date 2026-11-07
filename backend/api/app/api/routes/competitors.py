"""Admin endpoints for competitor product links and prices."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_db_readonly, require_admin
from app.api.openapi import (
    NOT_FOUND,
    RATE_LIMITED,
    UNAUTHORIZED,
    VALIDATION_ERROR,
)
from app.models import Admin
from app.schemas.competitor import (
    CompetitorListingCreate,
    CompetitorListingOut,
    CompetitorListingUpdate,
)
from app.services.competitor import (
    CompetitorNotFoundError,
    CompetitorService,
    CompetitorThrottledError,
    InvalidCompetitorProductError,
)

router = APIRouter(tags=["Competitors"], responses={401: UNAUTHORIZED})


@router.get(
    "/products/{product_id}/competitors",
    response_model=list[CompetitorListingOut],
    summary="List competitor links",
    description=(
        "Every competitor link saved for one product, including fetched and "
        "manual price overrides. `effective_*` fields apply the precedence rules."
    ),
    responses={404: NOT_FOUND, 422: VALIDATION_ERROR},
)
def list_competitor_listings(
    product_id: int,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[CompetitorListingOut]:
    try:
        return CompetitorService(session).list_product_listings(product_id)
    except CompetitorNotFoundError:
        raise HTTPException(status_code=404, detail="کالا پیدا نشد") from None


@router.post(
    "/products/{product_id}/competitors",
    response_model=CompetitorListingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add competitor link",
    description=(
        "Saves a public product URL for one product. Only لوازم خانگی products "
        "accept links, with at most one link per store. Digikala and Technolife "
        "URLs are checked automatically; `other` stores remain manual-only."
    ),
    responses={404: NOT_FOUND, 422: VALIDATION_ERROR},
)
def create_competitor_listing(
    product_id: int,
    payload: CompetitorListingCreate,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> CompetitorListingOut:
    try:
        return CompetitorService(session).create(product_id, payload)
    except CompetitorNotFoundError:
        raise HTTPException(status_code=404, detail="کالا پیدا نشد") from None
    except InvalidCompetitorProductError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.patch(
    "/competitors/{listing_id}",
    response_model=CompetitorListingOut,
    summary="Update competitor link",
    description=(
        "Partial update: URL, active flag, or a manual price/currency/stock "
        "override. Omitted fields keep their current values."
    ),
    responses={404: NOT_FOUND, 422: VALIDATION_ERROR},
)
def update_competitor_listing(
    listing_id: int,
    payload: CompetitorListingUpdate,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> CompetitorListingOut:
    try:
        return CompetitorService(session).update(listing_id, payload)
    except CompetitorNotFoundError:
        raise HTTPException(status_code=404, detail="منبع قیمت پیدا نشد") from None
    except InvalidCompetitorProductError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.delete(
    "/competitors/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete competitor link",
    description="Removes one competitor link and its stored observations.",
    responses={204: {"description": "Listing deleted."}, 404: NOT_FOUND, 422: VALIDATION_ERROR},
)
def delete_competitor_listing(
    listing_id: int,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> Response:
    try:
        CompetitorService(session).delete(listing_id)
    except CompetitorNotFoundError:
        raise HTTPException(status_code=404, detail="منبع قیمت پیدا نشد") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/products/{product_id}/competitors/check",
    response_model=list[CompetitorListingOut],
    summary="Check all links of a product",
    description=(
        "Synchronously re-checks every active competitor link of one product "
        "and returns the refreshed listings."
    ),
    responses={404: NOT_FOUND, 422: VALIDATION_ERROR},
)
def check_all_competitor_listings(
    product_id: int,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> list[CompetitorListingOut]:
    try:
        return CompetitorService(session).check_all(product_id)
    except CompetitorNotFoundError:
        raise HTTPException(status_code=404, detail="کالا پیدا نشد") from None


@router.post(
    "/competitors/{listing_id}/check",
    response_model=CompetitorListingOut,
    summary="Check one competitor link",
    description=(
        "Synchronously fetches the current price and stock for one listing. "
        "Returns `429` when the link is checked again before its politeness "
        "interval elapses."
    ),
    responses={404: NOT_FOUND, 422: VALIDATION_ERROR, 429: RATE_LIMITED},
)
def check_competitor_listing(
    listing_id: int,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> CompetitorListingOut:
    try:
        return CompetitorService(session).check(listing_id)
    except CompetitorNotFoundError:
        raise HTTPException(status_code=404, detail="منبع قیمت پیدا نشد") from None
    except CompetitorThrottledError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from None
    except InvalidCompetitorProductError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
