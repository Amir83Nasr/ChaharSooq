"""HSTS ownership regression: the TLS edge owns it, never the application.

Production terminates TLS in Caddy (`deploy/caddy/site.caddy`).
Staging is served by Vercel, whose edge sends HSTS for every deployment
(`max-age=63072000`, plus `includeSubDomains; preload` on `*.vercel.app`), so the
browser-facing header exists there without the API adding one.

Keeping the API silent gives each environment exactly one owner and stops a
second, weaker policy (the old `max-age=31536000; includeSubDomains`) from
travelling through the Next rewrite. These tests fail if an environment-
conditional HSTS header is reintroduced in the application.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.main import SecurityHeadersMiddleware

pytestmark = pytest.mark.usefixtures("isolated_settings")


async def _ok(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


@pytest.mark.parametrize("deployment_env", ["development", "staging", "production"])
def test_the_application_never_sets_hsts(
    monkeypatch: pytest.MonkeyPatch, deployment_env: str
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", deployment_env)

    app = Starlette(routes=[Route("/", _ok)])
    app.add_middleware(SecurityHeadersMiddleware)
    response = TestClient(app).get("/")

    # The middleware is still active and still sets the other headers.
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["content-security-policy"] == "frame-ancestors 'none'"
    assert "strict-transport-security" not in response.headers
