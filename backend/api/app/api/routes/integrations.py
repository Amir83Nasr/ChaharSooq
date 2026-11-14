"""Integration handlers — manual sync triggers + status (auth required).

Both manual syncs are background jobs: the POST returns at once and the UI
polls `status`. The shared DB lock is taken inside the POST, so a double
click, a second admin, and the scheduler can never run in parallel.
"""

import logging
import threading
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_db, get_db_readonly, require_admin, require_owner, require_user
from app.api.openapi import CONFLICT, FORBIDDEN, SERVICE_UNAVAILABLE, UNAUTHORIZED, VALIDATION_ERROR
from app.core.database import get_engine
from app.models import Admin, ParsinaSyncState
from app.models.competitor import CompetitorSyncState
from app.schemas import ParsinaConnectionIn, ParsinaConnectionOut, SyncRunOut, SyncStatusOut
from app.schemas.competitor import CompetitorSyncRunOut, CompetitorSyncStatusOut
from app.services import SettingsService
from app.services.competitor_sync import CompetitorSyncBusyError, CompetitorSyncService
from app.services.parsina_connection import get_parsina_connection_view, update_parsina_connection
from app.services.sync import (
    ProductSyncService,
    SyncBusyError,
    SyncNotConfiguredError,
)

router = APIRouter(tags=["Integrations"], responses={401: UNAUTHORIZED})
log = logging.getLogger("charsooq.integrations")


def _is_running(state: ParsinaSyncState | CompetitorSyncState, *, now: datetime) -> bool:
    if state.lock_until is None:
        return False
    lock_until = (
        state.lock_until if state.lock_until.tzinfo else state.lock_until.replace(tzinfo=UTC)
    )
    return lock_until > now


def _status(session: Session) -> SyncStatusOut:
    service = ProductSyncService(session)
    state = service.state()
    interval = SettingsService(session).get_sync_interval()
    return SyncStatusOut(
        configured=service.configured,
        source=service.source_label,
        running=_is_running(state, now=datetime.now(UTC)),
        running_since=state.running_since,
        last_attempt_at=state.last_attempt_at,
        last_success_at=state.last_success_at,
        last_error=state.last_error,
        last_processed=state.last_processed,
        last_created=state.last_created,
        last_updated=state.last_updated,
        last_deactivated=state.last_deactivated,
        last_skipped=state.last_skipped,
        interval_minutes=interval,
    )


def _run_manual() -> None:
    """Worker thread — owns its own Session; the HTTP request has returned."""
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        try:
            ProductSyncService(session).run_acquired()
        except Exception:  # noqa: BLE001 — failure is recorded in sync state
            log.exception("manual parsina sync failed")


def _competitor_status(session: Session) -> CompetitorSyncStatusOut:
    state = CompetitorSyncService(session).state()
    return CompetitorSyncStatusOut(
        running=_is_running(state, now=datetime.now(UTC)),
        running_since=state.running_since,
        last_attempt_at=state.last_attempt_at,
        last_success_at=state.last_success_at,
        last_error=state.last_error,
        last_checked=state.last_checked,
        last_updated=state.last_updated,
        last_failed=state.last_failed,
        last_skipped=state.last_skipped,
    )


def _run_competitor_manual() -> None:
    """Worker thread — owns its own Session; the HTTP request has returned."""
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        try:
            CompetitorSyncService(session).run_acquired()
        except Exception:  # noqa: BLE001 — failure is recorded in sync state
            log.exception("manual competitor refresh failed")


@router.get(
    "/integrations/parsina/status",
    response_model=SyncStatusOut,
    summary="Parsina sync status",
    description=(
        "Current product-sync state: configured source, running flag, last "
        "attempt/success, last error, counters from the last run, and the "
        "configured interval in minutes."
    ),
)
def parsina_status(
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> SyncStatusOut:
    return _status(session)


@router.get(
    "/integrations/parsina/connection",
    response_model=ParsinaConnectionOut,
    summary="Parsina connection config",
    description=(
        "Effective Parsina connection details for the super admin. The password "
        "is never returned; `password_set` indicates whether one is configured."
    ),
    responses={403: FORBIDDEN},
)
def parsina_connection(
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> ParsinaConnectionOut:
    return ParsinaConnectionOut.model_validate(get_parsina_connection_view(session))


@router.put(
    "/integrations/parsina/connection",
    response_model=ParsinaConnectionOut,
    summary="Update Parsina connection config",
    description=(
        "Saves Parsina connection details (base URL, username, password, "
        "organization id, fiscal year). Only the super admin may update them. "
        "Leave `password` empty to keep the existing password."
    ),
    responses={403: FORBIDDEN, 422: VALIDATION_ERROR},
)
def update_parsina_connection_view(
    payload: ParsinaConnectionIn,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> ParsinaConnectionOut:
    result = update_parsina_connection(
        session,
        base_url=payload.base_url,
        username=payload.username,
        password=payload.password,
        org_id=payload.org_id,
        fiscal_year=payload.fiscal_year,
    )
    return ParsinaConnectionOut.model_validate(result)


@router.post(
    "/integrations/parsina/sync",
    response_model=SyncRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start product sync",
    description=(
        "Starts a background catalog sync and returns immediately. Poll the "
        "status endpoint for progress. A run already holding the lock returns "
        "`409`; an unconfigured source returns `503`."
    ),
    responses={409: CONFLICT, 503: SERVICE_UNAVAILABLE},
)
def parsina_sync(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> SyncRunOut:
    service = ProductSyncService(session)
    try:
        service.acquire()
    except SyncNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from None
    except SyncBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    threading.Thread(target=_run_manual, name="parsina-sync-manual", daemon=True).start()
    if service.source_label == "csv":
        message = "بارگذاری داده آزمایشی محصولات آغاز شد"
    elif service.source_label == "dev":
        message = "همگام‌سازی با دیتابیس dev آغاز شد"
    else:
        message = "همگام‌سازی با پارسینا آغاز شد"
    return SyncRunOut(status="running", message=message)


@router.get(
    "/integrations/competitors/status",
    response_model=CompetitorSyncStatusOut,
    summary="Competitor sync status",
    description=(
        "Current bulk-refresh state: running flag, last attempt/success, last "
        "error, and counters from the last run."
    ),
)
def competitors_status(
    _user: Admin = Depends(require_user),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> CompetitorSyncStatusOut:
    return _competitor_status(session)


@router.post(
    "/integrations/competitors/sync",
    response_model=CompetitorSyncRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start competitor refresh",
    description=(
        "Refreshes every active competitor link in the background and returns "
        "immediately. Poll the status endpoint for progress; `409` while "
        "another bulk run holds the lock."
    ),
    responses={409: CONFLICT},
)
def competitors_sync(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> CompetitorSyncRunOut:
    service = CompetitorSyncService(session)
    try:
        service.acquire()
    except CompetitorSyncBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    threading.Thread(
        target=_run_competitor_manual, name="competitor-sync-manual", daemon=True
    ).start()
    return CompetitorSyncRunOut(status="running", message="به‌روزرسانی قیمت رقبا آغاز شد")


__all__ = ["router"]
