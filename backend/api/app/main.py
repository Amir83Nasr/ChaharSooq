"""App factory — secure defaults, predictable error envelope, no secret logging."""

import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api import router
from app.api.dependencies import get_db_readonly
from app.api.openapi import API_DESCRIPTION, TAGS_METADATA
from app.core.config import get_settings
from app.core.rate_limit import login_rate_key, rate_limited

log = logging.getLogger("charsooq")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


_FIELD_LABELS: dict[str, str] = {
    "username": "نام کاربری",
    "password": "گذرواژه",
    "role": "سطح دسترسی",
    "name": "نام",
    "sku": "کد",
    "price": "قیمت",
    "stock": "موجودی",
    "category_id": "دسته‌بندی",
    "category": "دسته‌بندی",
    "q": "جست‌وجو",
    "threshold": "آستانه",
    "page": "صفحه",
    "page_size": "اندازه صفحه",
    "main_group": "گروه اصلی",
    "product_id": "کالا",
    "url": "لینک محصول",
    "store": "فروشگاه",
    "manual_price": "قیمت دستی",
    "weight": "وزن",
    "allowed_decrease_percent": "حداکثر کاهش",
    "allowed_increase_percent": "حداکثر افزایش",
}


def _persian_issue(err_type: str) -> str:
    if err_type == "missing":
        return "وارد کردن این فیلد الزامی است"
    if err_type.startswith("string_too_short"):
        return "کوتاه‌تر از حد مجاز است"
    if err_type.startswith("string_too_long"):
        return "طولانی‌تر از حد مجاز است"
    if err_type.startswith("greater_than"):
        return "کمتر از حد مجاز است"
    if err_type.startswith("less_than"):
        return "بیشتر از حد مجاز است"
    if err_type.startswith("value_error"):
        return "مقدار نامعتبر است"
    return "نامعتبر است"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        # Never allow this admin panel to be framed elsewhere.
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # HSTS is only meaningful behind TLS; only send in production so
        # local HTTP dev never caches a sticky HTTPS upgrade. max-age stays
        # at the recommended one year (31536000).
        if get_settings().is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Migrate, then start/stop the Parsina scheduler (never in tests)."""
    from app.core.migrations import upgrade_to_head
    from app.core.scheduler import build_scheduler

    settings = get_settings()
    if settings.app_env != "test":
        upgrade_to_head()
    scheduler = None if settings.app_env == "test" else build_scheduler()
    if scheduler is not None:
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.stop()


def _operation_id(route: APIRoute) -> str:
    """Stable, readable ids (`list_products`) instead of generated path ids."""
    return route.name


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Charsooq Admin API",
        summary="Catalog, pricing, and competitor administration for چهارسوق.",
        description=API_DESCRIPTION,
        version="0.1.0",
        openapi_tags=TAGS_METADATA,
        license_info={"name": "MIT"},
        generate_unique_id_function=_operation_id,
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": 0,
            "displayRequestDuration": True,
            "filter": True,
            "persistAuthorization": True,
            "tryItOutEnabled": True,
        },
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def login_rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.endswith("/auth/login") and request.method == "POST":
            ip = request.client.host if request.client else "unknown"
            username: str | None = None
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    if isinstance(data, dict) and isinstance(data.get("username"), str):
                        username = data["username"]
            except (ValueError, UnicodeDecodeError):
                username = None
            if rate_limited(login_rate_key(ip, username)):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": {
                            "code": "rate_limited",
                            "message": "تلاش‌های مکرر؛ لطفاً بعداً تلاش کنید",
                        }
                    },
                )
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details: dict[str, list[str]] = {}
        for err in exc.errors():
            raw = ".".join(str(p) for p in err["loc"] if p != "body") or "body"
            field = raw.split(".")[-1]
            label = _FIELD_LABELS.get(field, field)
            details.setdefault(raw, []).append(f"{label} {_persian_issue(str(err.get('type')))}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "خطای اعتبارسنجی",
                    "details": details,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            422: "validation_error",
            429: "rate_limited",
        }
        defaults = {
            400: "درخواست نامعتبر است.",
            401: "نام کاربری یا گذرواژه نادرست است.",
            403: "دسترسی ندارید.",
            404: "یافت نشد.",
            405: "روش مجاز نیست.",
            409: "این مقدار قبلاً ثبت شده است.",
            422: "خطای اعتبارسنجی",
            429: "تلاش‌های مکرر؛ لطفاً بعداً تلاش کنید.",
        }
        # Unmatched routes reach us with Starlette's English defaults
        # ("Not Found", "Method Not Allowed") — never leak those to the UI.
        detail = exc.detail if isinstance(exc.detail, str) else ""
        if not detail.strip() or detail in ("Not Found", "Method Not Allowed"):
            message = defaults.get(exc.status_code, "خطایی رخ داد")
        else:
            message = detail
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": codes.get(exc.status_code, "error"), "message": message}},
        )

    # Service discovery for humans hitting the bare origin (e.g. browsers).
    # Excluded from the OpenAPI contract — /api/v1/* remains the documented API.
    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": app.title,
            "version": app.version,
            "status": "ok",
            "docs": "/docs",
            "health": "/health",
            "ready": "/ready",
            "api": "/api/v1/health",
        }

    # Root probes (outside /api/v1) for container orchestrators and platform
    # health checks. Excluded from the OpenAPI contract — the versioned
    # /api/v1/health and /api/v1/ready aliases remain the documented ones.
    @app.get("/health", include_in_schema=False)
    def root_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    def root_ready(session: Session = Depends(get_db_readonly)) -> dict[str, str]:  # noqa: B008
        session.execute(text("SELECT 1"))
        return {"status": "ready"}

    app.include_router(router)
    return app


app = create_app()
