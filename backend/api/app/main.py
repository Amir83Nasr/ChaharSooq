"""App factory — secure defaults, predictable error envelope, no secret logging."""

import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.router import router
from app.core.config import get_settings

log = logging.getLogger("charsooq")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 10
RATE_WINDOW_S = 60.0


def reset_rate_limits() -> None:
    """Test hook — clears in-memory login buckets between test clients."""
    _rate_buckets.clear()


_FIELD_LABELS: dict[str, str] = {
    "username": "نام کاربری",
    "password": "گذرواژه",
    "name": "نام",
    "sku": "کد",
    "price": "قیمت",
    "stock": "موجودی",
    "category_id": "دسته‌بندی",
    "category": "دسته‌بندی",
    "q": "جست‌وجو",
    "page": "صفحه",
    "page_size": "اندازه صفحه",
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
        return response


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    bucket = [t for t in _rate_buckets[ip] if now - t < RATE_WINDOW_S]
    _rate_buckets[ip] = bucket
    if len(bucket) >= RATE_LIMIT:
        return True
    bucket.append(now)
    return False


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Charsooq Admin API", version="0.1.0")

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
            if _rate_limited(ip):
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

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            429: "rate_limited",
        }
        message = exc.detail if isinstance(exc.detail, str) else "خطایی رخ داد"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": codes.get(exc.status_code, "error"), "message": message}},
        )

    app.include_router(router)
    return app


app = create_app()
