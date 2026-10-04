"""Auth flow — login/me/logout, validation envelope."""

from fastapi.testclient import TestClient

from app.services import LOGIN_ERROR
from tests.helpers import login


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


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
    assert client.get("/api/v1/auth/me").json() == {"username": "admin"}
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
