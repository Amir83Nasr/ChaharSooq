"""Products — CRUD, filters, paging, summary."""

from fastapi.testclient import TestClient

from tests.helpers import login, seed


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


def test_product_stock_range_filters(client: TestClient) -> None:
    seed(client)
    low = client.get("/api/v1/products", params={"in_stock": True, "max_stock": 5}).json()
    assert {i["sku"] for i in low["items"]} == {"TEA-1", "COF-1"}
    good = client.get("/api/v1/products", params={"min_stock": 6}).json()
    assert good["total"] == 0
    assert client.get("/api/v1/products", params={"min_stock": -1}).status_code == 422


def test_products_summary_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/products/summary").status_code == 401


def test_products_summary_counts(client: TestClient) -> None:
    seed(client)
    body = client.get("/api/v1/products/summary", params={"threshold": 5}).json()
    # seed: TEA-1 (5×100), CHE-1 (0×300), COF-1 (2×200) → value 500+0+400
    assert body == {"total": 3, "in_stock": 0, "low": 2, "out": 1, "stock_value": 900}
