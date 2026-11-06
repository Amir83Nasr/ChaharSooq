"""Health probes — liveness plus DB readiness."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_readonly

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(get_db_readonly)) -> dict[str, str]:  # noqa: B008
    session.execute(text("SELECT 1"))
    return {"status": "ready"}
