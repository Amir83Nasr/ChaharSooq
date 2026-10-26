"""Parsina integration handlers — manual sync trigger + status (auth required).

Manual sync is a background job: the POST returns at once and the UI polls
`status`. The shared DB lock is taken inside the POST, so a double click,
a second admin, and the 15-minute scheduler can never run in parallel.
"""

import logging
import threading
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db, require_admin
from app.core.config import get_parsina_settings
from app.core.database import get_engine
from app.models import Admin, ParsinaSyncState
from app.schemas import SyncRunOut, SyncStatusOut
from app.services.sync import (
    ProductSyncService,
    SyncBusyError,
    SyncNotConfiguredError,
)

router = APIRouter()
log = logging.getLogger("charsooq.integrations")


def _is_running(state: ParsinaSyncState, *, now: datetime) -> bool:
    if state.lock_until is None:
        return False
    lock_until = (
        state.lock_until if state.lock_until.tzinfo else state.lock_until.replace(tzinfo=UTC)
    )
    return lock_until > now


def _status(session: Session) -> SyncStatusOut:
    settings = get_parsina_settings()
    state = ProductSyncService(session).state()
    return SyncStatusOut(
        configured=settings.is_configured,
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
        interval_minutes=settings.parsina_sync_interval_minutes,
    )


def _run_manual() -> None:
    """Worker thread — owns its own Session; the HTTP request has returned."""
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        try:
            ProductSyncService(session).run_acquired()
        except Exception:  # noqa: BLE001 — failure is recorded in sync state
            log.exception("manual parsina sync failed")


@router.get("/integrations/parsina/status", response_model=SyncStatusOut)
def parsina_status(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> SyncStatusOut:
    return _status(session)


@router.post(
    "/integrations/parsina/sync",
    response_model=SyncRunOut,
    status_code=status.HTTP_202_ACCEPTED,
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
    return SyncRunOut(status="running", message="همگام‌سازی با پارسینا آغاز شد")


__all__ = ["router"]
