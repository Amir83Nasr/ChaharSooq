"""Dashboard handler — aggregate reads for the dashboard page."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_readonly, require_admin
from app.models import Admin
from app.schemas import (
    CatalogSectionOut,
    CompetitorGapOut,
    DashboardOverviewOut,
    DashboardSummaryOut,
)
from app.services import DashboardService

router = APIRouter()


@router.get("/dashboard/overview", response_model=DashboardOverviewOut)
def dashboard_overview(
    threshold: int = Query(default=10, ge=0),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> DashboardOverviewOut:
    return DashboardService(session).overview(low_stock_threshold=threshold)


@router.get("/dashboard/competitor-gaps", response_model=list[CompetitorGapOut])
def dashboard_competitor_gaps(
    limit: int = Query(default=8, ge=1, le=50),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[CompetitorGapOut]:
    return DashboardService(session).competitor_gaps(limit=limit)


@router.get("/dashboard/catalog-breakdown", response_model=list[CatalogSectionOut])
def dashboard_catalog_breakdown(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[CatalogSectionOut]:
    return DashboardService(session).catalog_breakdown()


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    threshold: int = Query(default=10, ge=0),
    gap_limit: int = Query(default=8, ge=1, le=50),
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> DashboardSummaryOut:
    """Aggregated dashboard payload — one fetch instead of three."""
    return DashboardService(session).summary(low_stock_threshold=threshold, gap_limit=gap_limit)
