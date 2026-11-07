"""Health probes — liveness plus DB readiness."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_readonly

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns `ok` while the process is running. It does not touch the database.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Runs `SELECT 1` and returns `ready` only when the database answers.",
)
def ready(session: Session = Depends(get_db_readonly)) -> dict[str, str]:  # noqa: B008
    session.execute(text("SELECT 1"))
    return {"status": "ready"}
