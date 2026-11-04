"""Dashboard aggregates — overview, competitor gaps, attention items."""

from fastapi.testclient import TestClient

from tests.helpers import login, seed


def test_dashboard_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/overview").status_code == 401
    assert client.get("/api/v1/dashboard/competitor-gaps").status_code == 401
    assert client.get("/api/v1/dashboard/attention").status_code == 401


def test_dashboard_overview_empty(client: TestClient) -> None:
    login(client)
    body = client.get("/api/v1/dashboard/overview").json()
    assert body == {
        "total": 0,
        "in_stock": 0,
        "low": 0,
        "out": 0,
        "stock_value": 0,
        "competitor_coverage": 0,
        "groups": [],
    }


def test_dashboard_overview_seed(client: TestClient) -> None:
    seed(client)
    body = client.get("/api/v1/dashboard/overview", params={"threshold": 5}).json()
    # seed: TEA-1 (5×100), CHE-1 (0×300), COF-1 (2×200) → value 500+0+400
    assert body["total"] == 3
    assert (body["in_stock"], body["low"], body["out"]) == (0, 2, 1)
    assert body["stock_value"] == 900
    assert body["competitor_coverage"] == 0
    # Seeded rows carry no group name, so everything collapses to "سایر".
    assert body["groups"] == [{"name": "سایر", "count": 3, "stock_value": 900}]


def test_dashboard_overview_rejects_negative_threshold(client: TestClient) -> None:
    login(client)
    r = client.get("/api/v1/dashboard/overview", params={"threshold": -1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def _add_manual_price(client: TestClient, product_id: int, price: int) -> None:
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "digikala", "url": "https://digikala.com/product/dkp-1/"},
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"manual_price": price, "manual_currency": "IRT"},
    )
    assert updated.status_code == 200, updated.text


def test_dashboard_competitor_gaps_empty(client: TestClient) -> None:
    seed(client)
    assert client.get("/api/v1/dashboard/competitor-gaps").json() == []


def test_dashboard_competitor_gaps_rank_by_abs_diff(client: TestClient) -> None:
    ids = seed(client)
    products = {
        item["sku"]: item
        for item in client.get("/api/v1/products", params={"page_size": 0}).json()["items"]
    }
    # TEA-1 ours 100 vs 80 → +25%; COF-1 ours 200 vs 220 → −9.1%
    _add_manual_price(client, products["TEA-1"]["id"], 80)
    _add_manual_price(client, products["COF-1"]["id"], 220)
    assert set(ids) == {"خواربار", "لبنیات"}
    gaps = client.get("/api/v1/dashboard/competitor-gaps").json()
    assert [(g["name"], g["diff_percent"]) for g in gaps] == [
        ("چای", 25.0),
        ("قهوه", -9.1),
    ]
    assert gaps[0]["competitor_store"] == "digikala"
    assert (gaps[0]["our_price"], gaps[0]["competitor_price"]) == (100, 80)


def test_dashboard_competitor_gaps_rejects_bad_limit(client: TestClient) -> None:
    login(client)
    r = client.get("/api/v1/dashboard/competitor-gaps", params={"limit": 0})
    assert r.status_code == 422


def test_dashboard_attention_seed(client: TestClient) -> None:
    seed(client)
    body = client.get("/api/v1/dashboard/attention", params={"threshold": 5}).json()
    # Out: CHE-1 (0×300). Low: COF-1 (2×200) before TEA-1 (5×100) — priciest first.
    assert [(i["name"], i["price"]) for i in body["out"]] == [("پنیر", 300)]
    assert [(i["name"], i["price"]) for i in body["low"]] == [
        ("قهوه", 200),
        ("چای", 100),
    ]
    assert body["out"][0]["stock"] == 0
