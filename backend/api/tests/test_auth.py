"""Auth flow — login/me/logout, validation envelope."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import Admin
from app.services import LOGIN_ERROR
from tests.helpers import login


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
