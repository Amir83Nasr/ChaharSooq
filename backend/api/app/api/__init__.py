"""Versioned API router."""

from fastapi import APIRouter

from app.api.routes import router as v1_router

router = APIRouter(prefix="/api/v1")
router.include_router(v1_router)
