"""Manual competitor link management and safe page parsing."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.integrations.competitor_prices import FetchedPrice, PriceFetchError, _price_from_html
from app.models import CompetitorListing
from tests.helpers import login


def _product_id(client: TestClient) -> int:
    login(client)
    response = client.post(
        "/api/v1/products",
        json={"name": "یخچال آزمایشی", "sku": "FRIDGE-1", "price": 100000000},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_manual_link_and_price_are_preserved_after_failed_check(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    product_id = _product_id(client)
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-123456/"},
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    saved = client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"manual_price": 25000000, "manual_currency": "IRT", "manual_in_stock": True},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["effective_price"] == 25000000
    assert saved.json()["price_is_fresh"] is True

    def fail_fetch(_store: str, _url: str) -> FetchedPrice:
        raise PriceFetchError("blocked", "تست محدودیت")

    monkeypatch.setattr("app.services.competitor.fetch_competitor_price", fail_fetch)
    checked = client.post(f"/api/v1/competitors/{listing_id}/check")
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["status"] == "blocked"
    assert body["manual_price"] == 25000000
    assert body["effective_price"] == 25000000
    assert body["last_error"] == "تست محدودیت"


def test_internal_and_direct_ip_urls_are_rejected(client: TestClient) -> None:
    product_id = _product_id(client)
    for url in (
        "http://127.0.0.1/admin",
        "http://localhost/admin",
        "https://www.digikala.com/",
    ):
        response = client.post(
            f"/api/v1/products/{product_id}/competitors",
            json={"store": "digikala", "url": url},
        )
        assert response.status_code == 422


def test_unknown_public_store_is_kept_for_manual_entry_only(client: TestClient) -> None:
    product_id = _product_id(client)
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "other", "url": "https://example.com/product/123"},
    )
    assert created.status_code == 201, created.text
    checked = client.post(f"/api/v1/competitors/{created.json()['id']}/check")
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == "unavailable"
    assert "پشتیبانی" in checked.json()["last_error"]


def test_link_edit_keeps_manual_values_but_marks_them_stale(client: TestClient) -> None:
    product_id = _product_id(client)
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-123456/"},
    )
    listing_id = created.json()["id"]
    client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"manual_price": 25000000, "manual_currency": "IRT"},
    )

    edited = client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"store": "other", "url": "https://example.com/product/123"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["store"] == "other"
    assert edited.json()["manual_price"] == 25000000
    assert edited.json()["effective_price"] is None
    assert edited.json()["price_is_fresh"] is False


def test_only_fresh_prices_appear_and_can_filter(client: TestClient) -> None:
    product_id = _product_id(client)
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "technolife", "url": "https://www.technolife.com/product/fridge"},
    )
    listing_id = created.json()["id"]
    client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"manual_price": 30000000, "manual_currency": "IRT", "manual_in_stock": True},
    )

    fresh = client.get(
        "/api/v1/products",
        params={"competitor_store": "technolife", "min_competitor_price": 20000000},
    ).json()
    assert [item["id"] for item in fresh["items"]] == [product_id]
    assert fresh["items"][0]["competitor_prices"][0]["price"] == 30000000

    with Session(get_engine()) as session:
        row = session.get(CompetitorListing, listing_id)
        assert row is not None
        row.manual_updated_at = datetime.now(UTC) - timedelta(days=4)
        session.commit()

    stale = client.get(
        "/api/v1/products",
        params={"competitor_store": "technolife", "min_competitor_price": 1},
    ).json()
    assert stale["total"] == 0
    assert stale["items"] == []


def test_json_ld_product_price_is_parsed() -> None:
    page = """
    <html><script type="application/ld+json">
    {"@type":"Product","offers":{"price":"42500000","priceCurrency":"IRT",
    "availability":"https://schema.org/InStock"}}
    </script></html>
    """
    assert _price_from_html(page) == FetchedPrice(Decimal("42500000"), "IRT", True)
