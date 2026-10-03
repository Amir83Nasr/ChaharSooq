# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
"""Tests: auth flow + product CRUD."""

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import Base, get_engine, reset_engine
from app.core.security import hash_password
from app.main import create_app
from app.models import Admin


@pytest.fixture()
def client() -> Iterator[TestClient]:
    reset_engine()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Admin(username="admin", password_hash=hash_password("secret123")))
        s.commit()
    with TestClient(create_app()) as c:
        yield c


def login(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_login_wrong_password_is_401_without_token(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401
    assert "set-cookie" not in r.headers


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_me_logout_cycle(client: TestClient) -> None:
    login(client)
    assert client.get("/api/v1/auth/me").json() == {"username": "admin"}
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_products_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/products").status_code == 401


def test_product_crud_roundtrip(client: TestClient) -> None:
    login(client)
    created = client.post(
        "/api/v1/products",
        json={"name": "چای", "sku": "TEA-1", "price": 1000000, "stock": 5},
    )
    assert created.status_code == 201, created.text
    assert created.json()["price"] == 1000000  # machine value, never Persian digits
    page = client.get("/api/v1/products").json()
    assert page["total"] == 1
    assert page["items"][0]["sku"] == "TEA-1"


def test_product_validation_envelope(client: TestClient) -> None:
    login(client)
    r = client.post("/api/v1/products", json={"name": "", "sku": "x", "price": -1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
