"""Settings handlers — admin display preferences get/update."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models import Admin
from app.schemas import SettingsOut, SettingsUpdateIn
from app.services import SettingsService

router = APIRouter()


@router.get("/settings", response_model=SettingsOut)
def get_settings_view(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> SettingsOut:
    return SettingsOut(**SettingsService(session).get_all())


@router.put("/settings", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdateIn,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> SettingsOut:
    svc = SettingsService(session)
    threshold = svc.get_threshold()
    page_size = svc.get_page_size()
    if payload.low_stock_threshold is not None:
        threshold = svc.update_threshold(payload.low_stock_threshold)
    if payload.default_page_size is not None:
        page_size = svc.update_page_size(payload.default_page_size)
    return SettingsOut(low_stock_threshold=threshold, default_page_size=page_size)
