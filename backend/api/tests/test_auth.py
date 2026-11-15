"""Auth flow — login/me/logout, validation envelope."""

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import Base, get_engine, reset_engine
from app.core.rate_limit import reset_rate_limits
from app.core.security import hash_password
from app.main import create_app
from app.models import Admin
from app.services import LOGIN_ERROR
from tests.helpers import login

_COOKIE = "charsooq_session"


def _cookie_header(response, name: str = _COOKIE) -> str:
    cookies = response.headers.get_list("set-cookie")
    for value in cookies:
        if value.startswith(f"{name}="):
            return value
    raise AssertionError(f"missing {name} cookie in {cookies!r}")


@contextmanager
def _auth_client(monkeypatch: pytest.MonkeyPatch, **env: str) -> Iterator[TestClient]:
    """Fresh app/client with explicit env overrides for cookie-policy tests."""
    from app.core import config

    reset_engine()
    reset_rate_limits()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    config.get_database_settings.cache_clear()
    config.get_settings.cache_clear()
    config.get_parsina_settings.cache_clear()
    try:
        engine = get_engine()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(Admin(username="admin", password_hash=hash_password("secret123")))
            session.commit()
        with TestClient(create_app()) as client:
            yield client
    finally:
        config.get_database_settings.cache_clear()
        config.get_settings.cache_clear()
        config.get_parsina_settings.cache_clear()
        reset_engine()
        reset_rate_limits()


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_security_headers_present(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
    # HSTS belongs to the TLS terminator (Caddy in Production), which is the only
    # layer that knows the browser connection is HTTPS. See ADR 012.
    assert "strict-transport-security" not in r.headers


def test_login_wrong_password_is_401_without_token(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401
    assert "set-cookie" not in r.headers
    body = r.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["message"] == LOGIN_ERROR


def test_login_validation_errors_are_persian(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "خطای اعتبارسنجی"
    messages = [m for msgs in body["error"]["details"].values() for m in msgs]
    assert any("نام کاربری" in m for m in messages)
    assert any("گذرواژه" in m for m in messages)


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_me_logout_cycle(client: TestClient) -> None:
    login(client)
    me = client.get("/api/v1/auth/me").json()
    assert me["username"] == "admin"
    assert me["role"] == "admin"
    assert isinstance(me["id"], int)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_fresh_login_rotates_previous_session(client: TestClient) -> None:
    """Single-session enforcement — a new login invalidates the old cookie."""
    from fastapi.testclient import TestClient as FreshClient

    first = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret123"})
    assert first.status_code == 200
    old_token = first.headers["set-cookie"].split("charsooq_session=")[1].split(";")[0]
    assert old_token

    second = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret123"})
    assert second.status_code == 200
    new_token = second.headers["set-cookie"].split("charsooq_session=")[1].split(";")[0]
    assert new_token and new_token != old_token
    assert client.get("/api/v1/auth/me").status_code == 200

    stale = FreshClient(client.app)
    stale.cookies.set("charsooq_session", old_token)
    assert stale.get("/api/v1/auth/me").status_code == 401


def test_login_with_corrupt_hash_is_401_not_500(client: TestClient) -> None:
    with Session(get_engine()) as s:
        admin = s.query(Admin).filter_by(username="admin").one()
        admin.password_hash = "not-a-valid-argon2-hash"
        s.commit()
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_login_rate_limited_after_repeated_failures(client: TestClient) -> None:
    for _ in range(10):
        r = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
        )
        assert r.status_code == 401
    limited = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"


def _production_mode_env(**overrides: str) -> dict[str, str]:
    """Production app behavior (Staging identity) with sqlite for hermetic tests."""
    env = {
        "APP_ENV": "production",
        "DEPLOYMENT_ENV": "staging",
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "SESSION_SECRET": "s" * 32,
        "OWNER_PASSWORD": "owner-pass-123",
        "RUN_MIGRATIONS_ON_STARTUP": "false",
        "RUN_OWNER_BOOTSTRAP_ON_STARTUP": "false",
    }
    env.update(overrides)
    return env


def test_session_cookie_secure_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    def load(**env: str):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        config.get_database_settings.cache_clear()
        config.get_settings.cache_clear()
        try:
            return config.Settings()
        finally:
            config.get_database_settings.cache_clear()
            config.get_settings.cache_clear()

    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    dev = load(APP_ENV="development", DEPLOYMENT_ENV="development")
    assert dev.session_cookie_secure is False

    prod = load(
        APP_ENV="production",
        DEPLOYMENT_ENV="staging",
        SESSION_SECRET="s" * 32,
        OWNER_PASSWORD="owner-pass-123",
        RUN_MIGRATIONS_ON_STARTUP="false",
        RUN_OWNER_BOOTSTRAP_ON_STARTUP="false",
    )
    assert prod.session_cookie_secure is True


def test_login_cookie_production_lax_without_secure_when_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _auth_client(
        monkeypatch,
        **_production_mode_env(SESSION_COOKIE_SECURE="false", SESSION_SAMESITE="lax"),
    ) as client:
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "secret123"}
        )
        assert response.status_code == 200
        cookie = _cookie_header(response).lower()
        parts = {part.strip() for part in cookie.split(";")}
        assert "httponly" in parts
        assert "samesite=lax" in parts
        assert "secure" not in parts


def test_login_cookie_production_lax_secure_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _auth_client(
        monkeypatch,
        **_production_mode_env(SESSION_COOKIE_SECURE="true", SESSION_SAMESITE="lax"),
    ) as client:
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "secret123"}
        )
        assert response.status_code == 200
        cookie = _cookie_header(response).lower()
        parts = {part.strip() for part in cookie.split(";")}
        assert "samesite=lax" in parts
        assert "secure" in parts


def test_login_cookie_samesite_none_always_secure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _auth_client(
        monkeypatch,
        **_production_mode_env(SESSION_COOKIE_SECURE="false", SESSION_SAMESITE="none"),
    ) as client:
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "secret123"}
        )
        assert response.status_code == 200
        cookie = _cookie_header(response).lower()
        parts = {part.strip() for part in cookie.split(";")}
        assert "samesite=none" in parts
        assert "secure" in parts


def test_logout_uses_same_secure_policy_as_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _auth_client(
        monkeypatch,
        **_production_mode_env(SESSION_COOKIE_SECURE="false", SESSION_SAMESITE="lax"),
    ) as client:
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "secret123"}
        )
        assert login_response.status_code == 200
        login_parts = {part.strip() for part in _cookie_header(login_response).lower().split(";")}
        assert "secure" not in login_parts

        logout_response = client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 204
        logout_parts = {part.strip() for part in _cookie_header(logout_response).lower().split(";")}
        assert "samesite=lax" in logout_parts
        assert "secure" not in logout_parts
