"""Settings handlers — admin display preferences get/update."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.models import Admin
from app.schemas import SettingsOut, SettingsUpdateIn
from app.services import SettingsService

router = APIRouter()


@router.get("/settings", response_model=SettingsOut)
def get_settings_view(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> SettingsOut:
    return SettingsOut.model_validate(SettingsService(session).get_all())


@router.put("/settings", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdateIn,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> SettingsOut:
    svc = SettingsService(session)
    threshold = svc.get_threshold()
    page_size = svc.get_page_size()
    interval = svc.get_sync_interval()
    competitor_interval = svc.get_competitor_sync_interval()
    competitor_store = svc.get_competitor_store()
    formulas = svc.get_suggested_price_formulas()
    if payload.low_stock_threshold is not None:
        threshold = svc.update_threshold(payload.low_stock_threshold)
    if payload.default_page_size is not None:
        page_size = svc.update_page_size(payload.default_page_size)
    if payload.sync_interval_minutes is not None:
        interval = svc.update_sync_interval(payload.sync_interval_minutes)
    if payload.competitor_sync_interval_minutes is not None:
        competitor_interval = svc.update_competitor_sync_interval(
            payload.competitor_sync_interval_minutes
        )
    if payload.default_competitor_store is not None:
        competitor_store = svc.update_competitor_store(payload.default_competitor_store)
    if payload.suggested_price_formulas is not None:
        formulas = svc.update_suggested_price_formulas(
            [item.model_dump() for item in payload.suggested_price_formulas]
        )
    return SettingsOut.model_validate(
        {
            "low_stock_threshold": threshold,
            "default_page_size": page_size,
            "sync_interval_minutes": interval,
            "competitor_sync_interval_minutes": competitor_interval,
            "default_competitor_store": competitor_store,
            "suggested_price_formulas": formulas,
        }
    )
