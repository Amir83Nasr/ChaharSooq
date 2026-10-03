"""App factory — secure defaults, predictable error envelope, no secret logging."""

import logging
import time
from collections import defaultdict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import router
from app.core.config import get_settings

log = logging.getLogger("charsooq")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 10
RATE_WINDOW_S = 60.0


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
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
    async def login_rate_limit(request: Request, call_next):  # type: ignore[no-untyped-def]
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
            field = ".".join(str(p) for p in err["loc"] if p != "body") or "body"
            details.setdefault(field, []).append(err["msg"])
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "خطای اعتبارسنجی",
                    "details": details,
                }
            },
        )

    app.include_router(router)
    return app


app = create_app()
