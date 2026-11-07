"""Dashboard handler — aggregate reads for the dashboard page."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_readonly, require_user
from app.api.openapi import UNAUTHORIZED, VALIDATION_ERROR
from app.models import Admin
from app.schemas import (
    CatalogSectionOut,
    CompetitorGapOut,
    DashboardOverviewOut,
    DashboardSummaryOut,
)
from app.services import DashboardService

router = APIRouter(tags=["Dashboard"], responses={401: UNAUTHORIZED})


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverviewOut,
    summary="Catalog overview",
    description=(
        "Totals, stock buckets, stock value, competitor coverage, and the "
        "top groups by stock value."
    ),
    responses={422: VALIDATION_ERROR},
)
def dashboard_overview(
    threshold: int = Query(default=10, ge=0, description="Low-stock cutoff."),
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> DashboardOverviewOut:
    return DashboardService(session).overview(low_stock_threshold=threshold)


@router.get(
    "/dashboard/competitor-gaps",
    response_model=list[CompetitorGapOut],
    summary="Largest competitor price gaps",
    description=(
        "Products ranked by absolute price difference against their cheapest "
        "fresh competitor listing. Positive `diff_percent` means we are pricier."
    ),
    responses={422: VALIDATION_ERROR},
)
def dashboard_competitor_gaps(
    limit: int = Query(default=8, ge=1, le=50, description="Number of gaps to return."),
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[CompetitorGapOut]:
    return DashboardService(session).competitor_gaps(limit=limit)


@router.get(
    "/dashboard/catalog-breakdown",
    response_model=list[CatalogSectionOut],
    summary="Catalog breakdown by section",
    description=(
        "Per-section (فرش / مبلمان / لوازم خانگی / سایر) totals: items, groups, "
        "brands, and stock value."
    ),
)
def dashboard_catalog_breakdown(
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[CatalogSectionOut]:
    return DashboardService(session).catalog_breakdown()


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryOut,
    summary="Dashboard payload",
    description=(
        "One-call dashboard payload combining overview, competitor gaps, and "
        "the catalog breakdown. The individual endpoints remain for compatibility."
    ),
    responses={422: VALIDATION_ERROR},
)
def dashboard_summary(
    threshold: int = Query(default=10, ge=0, description="Low-stock cutoff."),
    gap_limit: int = Query(default=8, ge=1, le=50, description="Number of gaps to return."),
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> DashboardSummaryOut:
    """Aggregated dashboard payload — one fetch instead of three."""
    return DashboardService(session).summary(low_stock_threshold=threshold, gap_limit=gap_limit)
