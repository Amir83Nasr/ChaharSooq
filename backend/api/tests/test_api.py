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
from app.main import create_app, reset_rate_limits
from app.models import Admin
from app.services import LOGIN_ERROR


@pytest.fixture()
def client() -> Iterator[TestClient]:
    reset_engine()
    reset_rate_limits()
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


# ── Categories / product filters ─────────────────────────────


def seed(client: TestClient) -> dict[str, int]:
    login(client)
    ids: dict[str, int] = {}
    for name in ["خواربار", "لبنیات"]:
        r = client.post("/api/v1/categories", json={"name": name})
        assert r.status_code == 201, r.text
        ids[name] = r.json()["id"]
    items = [
        {"name": "چای", "sku": "TEA-1", "price": 100, "stock": 5, "category_id": ids["خواربار"]},
        {"name": "پنیر", "sku": "CHE-1", "price": 300, "stock": 0, "category_id": ids["لبنیات"]},
        {"name": "قهوه", "sku": "COF-1", "price": 200, "stock": 2, "category_id": None},
    ]
    for item in items:
        assert client.post("/api/v1/products", json=item).status_code == 201
    return ids


def test_category_crud_and_conflicts(client: TestClient) -> None:
    login(client)
    r = client.post("/api/v1/categories", json={"name": "خواربار"})
    assert r.status_code == 201, r.text
    assert client.post("/api/v1/categories", json={"name": "خواربار"}).status_code == 409
    names = [c["name"] for c in client.get("/api/v1/categories").json()]
    assert names == ["خواربار"]


def test_category_delete_guards(client: TestClient) -> None:
    ids = seed(client)
    assert client.delete("/api/v1/categories/9999").status_code == 404
    busy = client.delete(f"/api/v1/categories/{ids['خواربار']}")
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "category_in_use"


def test_product_search_covers_sku(client: TestClient) -> None:
    seed(client)
    page = client.get("/api/v1/products", params={"q": "CHE-"}).json()
    assert [i["sku"] for i in page["items"]] == ["CHE-1"]


def test_product_filters_and_sort(client: TestClient) -> None:
    ids = seed(client)
    by_cat = client.get("/api/v1/products", params={"category_id": ids["لبنیات"]}).json()
    assert [i["sku"] for i in by_cat["items"]] == ["CHE-1"]
    in_stock = client.get("/api/v1/products", params={"in_stock": True}).json()
    assert in_stock["total"] == 2
    ranged = client.get("/api/v1/products", params={"min_price": 150, "max_price": 250}).json()
    assert [i["sku"] for i in ranged["items"]] == ["COF-1"]
    cheapest = client.get("/api/v1/products", params={"sort": "cheapest"}).json()
    assert [i["price"] for i in cheapest["items"]] == [100, 200, 300]


def test_product_pagination_total(client: TestClient) -> None:
    seed(client)
    first = client.get("/api/v1/products", params={"page": 1, "page_size": 2}).json()
    second = client.get("/api/v1/products", params={"page": 2, "page_size": 2}).json()
    assert (first["total"], second["total"]) == (3, 3)
    assert len(first["items"]) == 2 and len(second["items"]) == 1


def test_product_invalid_category_rejected(client: TestClient) -> None:
    login(client)
    r = client.post(
        "/api/v1/products",
        json={"name": "x", "sku": "X-1", "price": 1, "category_id": 9999},
    )
    assert r.status_code == 422


def test_database_url_trailing_whitespace_stripped() -> None:
    from app.core.config import Settings

    s = Settings(database_url="postgresql+psycopg://u:p@host/db?sslmode=require ")
    assert s.database_url == "postgresql+psycopg://u:p@host/db?sslmode=require"
