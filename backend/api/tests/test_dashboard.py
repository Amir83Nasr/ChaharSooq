"""Dashboard aggregates — overview, competitor gaps, catalog breakdown."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_engine
from tests.helpers import login, seed


@pytest.fixture()
def session(client: TestClient) -> Iterator[Session]:
    """Depends on `client` so the in-memory schema exists before use."""
    with Session(get_engine()) as s:
        yield s


def test_dashboard_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/overview").status_code == 401
    assert client.get("/api/v1/dashboard/competitor-gaps").status_code == 401
    assert client.get("/api/v1/dashboard/catalog-breakdown").status_code == 401


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
        "appliance_total": 0,
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
    # Seeded rows carry no group name, so none count as لوازم خانگی.
    assert body["appliance_total"] == 0
    # Seeded rows carry no group name, so everything collapses to "سایر".
    assert body["groups"] == [{"name": "سایر", "count": 3, "stock_value": 900}]


def test_dashboard_overview_appliance_total(client: TestClient, session: Session) -> None:
    """Only grouped non-فرش/مبلمان rows count toward the coverage denominator."""
    from decimal import Decimal

    from app.models import Product

    login(client)
    session.add_all(
        [
            Product(
                name="فرش",
                sku="RUG-1",
                price=Decimal(100),
                stock=Decimal(1),
                main_group_name="فرش نگین",
            ),
            Product(
                name="مبل",
                sku="SOF-1",
                price=Decimal(100),
                stock=Decimal(1),
                main_group_name="مبلمان راحتی",
            ),
            Product(
                name="یخچال",
                sku="FRZ-1",
                price=Decimal(100),
                stock=Decimal(1),
                main_group_name="یخچال اسنوا",
            ),
            Product(name="بدون گروه", sku="NOG-1", price=Decimal(100), stock=Decimal(1)),
        ]
    )
    session.commit()
    body = client.get("/api/v1/dashboard/overview").json()
    assert body["total"] == 4
    assert body["appliance_total"] == 1


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


def test_dashboard_catalog_breakdown_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/catalog-breakdown").status_code == 401


def test_dashboard_catalog_breakdown_empty(client: TestClient) -> None:
    login(client)
    body = client.get("/api/v1/dashboard/catalog-breakdown").json()
    assert [s["top_group"] for s in body] == ["فرش", "مبلمان", "لوازم خانگی", "سایر"]
    assert all(
        s["items"] == 0
        and s["group_count"] == 0
        and s["brand_count"] == 0
        and s["stock_value"] == 0
        and s["brands"] == []
        for s in body
    )


def test_dashboard_catalog_breakdown_seed(client: TestClient) -> None:
    """Seeded rows carry no group name — everything collapses to سایر."""
    seed(client)
    body = client.get("/api/v1/dashboard/catalog-breakdown").json()
    by_section = {s["top_group"]: s for s in body}
    assert by_section["فرش"]["items"] == 0
    assert by_section["مبلمان"]["items"] == 0
    assert by_section["لوازم خانگی"]["items"] == 0
    other = by_section["سایر"]
    assert other["items"] == 3
    assert other["group_count"] == 1
    assert other["brand_count"] == 1
    assert other["stock_value"] == 900
    assert other["brands"] == [
        {"group_name": "سایر", "brand": "سایر", "count": 3, "stock_value": 900}
    ]


def test_dashboard_catalog_breakdown_groups_by_section(
    client: TestClient, session: Session
) -> None:
    from decimal import Decimal

    from app.models import Product

    login(client)
    session.add_all(
        [
            Product(
                name="فرش یک",
                sku="RUG-1",
                price=Decimal(100),
                stock=Decimal(2),
                main_group_name="فرش نگین",
            ),
            Product(
                name="فرش دو",
                sku="RUG-2",
                price=Decimal(100),
                stock=Decimal(3),
                main_group_name="فرش نگین",
            ),
            Product(
                name="مبل یک",
                sku="SOF-1",
                price=Decimal(200),
                stock=Decimal(1),
                main_group_name="مبلمان راحتی",
            ),
            Product(
                name="یخچال",
                sku="FRZ-1",
                price=Decimal(500),
                stock=Decimal(1),
                main_group_name="یخچال اسنوا",
            ),
        ]
    )
    session.commit()
    body = client.get("/api/v1/dashboard/catalog-breakdown").json()
    by_section = {s["top_group"]: s for s in body}
    rug = by_section["فرش"]
    assert (rug["items"], rug["group_count"], rug["brand_count"]) == (2, 1, 1)
    assert rug["stock_value"] == 500
    assert rug["brands"] == [
        {"group_name": "فرش نگین", "brand": "نگین", "count": 2, "stock_value": 500}
    ]
    sofa = by_section["مبلمان"]
    assert (sofa["items"], sofa["group_count"], sofa["brand_count"]) == (1, 1, 1)
    assert sofa["brands"][0]["brand"] == "راحتی"
    fridge = by_section["لوازم خانگی"]
    assert (fridge["items"], fridge["group_count"], fridge["brand_count"]) == (1, 1, 1)
    assert fridge["brands"][0] == {
        "group_name": "یخچال اسنوا",
        "brand": "یخچال اسنوا",
        "count": 1,
        "stock_value": 500,
    }
    assert by_section["سایر"]["items"] == 0
