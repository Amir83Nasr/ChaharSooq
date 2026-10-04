"""Shared test helpers — login + catalog seed."""

from fastapi.testclient import TestClient


def login(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}


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
        {"name": "قهوه", "sku": "COF-1", "price": 200, "stock": 2},
    ]
    for payload in items:
        r = client.post("/api/v1/products", json=payload)
        assert r.status_code == 201, r.text
    return ids
