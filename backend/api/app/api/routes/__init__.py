"""Thin route handlers — validation + status codes only, logic in services."""

from fastapi import APIRouter

from app.api.routes import auth, categories, health, products, settings

router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(products.router)
router.include_router(categories.router)
router.include_router(settings.router)
