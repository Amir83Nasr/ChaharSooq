"""Furniture/carpet links, daily price history, and per-product price bounds."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.integrations import competitor_prices as prices
from app.integrations.competitor_prices import FetchedPrice
from app.models import CompetitorPriceObservation, Product
from tests.helpers import login


def _group_product_id(client: TestClient, group: str) -> int:
    login(client)
    with Session(get_engine()) as session:
        product = Product(
            name=f"کالای {group}",
            sku=f"GROUP-{group}",
            price=1_000_000,
            stock=1,
            main_group_name=group,
            is_active=True,
        )
        session.add(product)
        session.commit()
        return product.id


def _create_link(client: TestClient, product_id: int, store: str, url: str) -> int:
    response = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": store, "url": url},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


@pytest.mark.parametrize(
    ("group", "store", "url"),
    [
        ("مبلمان راحتی", "sofa", "https://sofamobl.com/product/carloos-sofa-manya/"),
        ("فرش ماشینی", "digifresh", "https://digifarsh.com/product/test-carpet/"),
    ],
)
def test_group_specific_links_are_accepted(
    client: TestClient, group: str, store: str, url: str
) -> None:
    product_id = _group_product_id(client, group)
    _create_link(client, product_id, store, url)


@pytest.mark.parametrize(("group", "store"), [("مبلمان راحتی", "digikala"), ("فرش", "sofa")])
def test_links_for_the_wrong_group_are_rejected(client: TestClient, group: str, store: str) -> None:
    login(client)
    product_id = _group_product_id(client, group)
    response = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": store, "url": "https://www.digikala.com/product/dkp-123456/"},
    )
    assert response.status_code == 422


def test_daily_change_compares_with_previous_day(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    product_id = _group_product_id(client, "مبلمان راحتی")
    listing_id = _create_link(
        client,
        product_id,
        "sofa",
        "https://sofamobl.com/product/carloos-sofa-manya/",
    )

    def fake_fetch(_store: str, _url: str) -> FetchedPrice:
        return FetchedPrice(Decimal("100000000"), "IRT", True, datetime.now(UTC))

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", fake_fetch)
    checked = client.post(f"/api/v1/competitors/{listing_id}/check")
    assert checked.status_code == 200, checked.text

    with Session(get_engine()) as session:
        session.add(
            CompetitorPriceObservation(
                listing_id=listing_id,
                price=Decimal("80000000"),
                currency="IRT",
                in_stock=True,
                observed_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        session.commit()

    listings = client.get(f"/api/v1/products/{product_id}/competitors").json()
    assert len(listings) == 1
    assert listings[0]["price_change_percent"] == 25.0
    assert listings[0]["previous_price"] == 80000000
    assert listings[0]["previous_currency"] == "IRT"

    products = client.get("/api/v1/products", params={"top_group": "مبلمان"}).json()
    price = products["items"][0]["competitor_prices"][0]
    assert price["price_change_percent"] == 25.0


def test_price_bounds_round_trip_and_validation(client: TestClient) -> None:
    login(client)
    created = client.post(
        "/api/v1/products",
        json={"name": "کالای بازه", "sku": "BOUND-1", "price": 1_000_000},
    )
    product_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/products/{product_id}/price-bounds",
        json={"allowed_decrease_percent": 5, "allowed_increase_percent": 10},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["allowed_decrease_percent"] == 5
    assert updated.json()["allowed_increase_percent"] == 10

    listed = client.get("/api/v1/products", params={"q": "BOUND-1"}).json()
    assert listed["items"][0]["allowed_decrease_percent"] == 5
    assert listed["items"][0]["allowed_increase_percent"] == 10

    cleared = client.patch(
        f"/api/v1/products/{product_id}/price-bounds",
        json={"allowed_decrease_percent": None, "allowed_increase_percent": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["allowed_decrease_percent"] is None

    invalid = client.patch(
        f"/api/v1/products/{product_id}/price-bounds",
        json={"allowed_decrease_percent": 101},
    )
    assert invalid.status_code == 422

    missing = client.patch(
        "/api/v1/products/999999/price-bounds",
        json={"allowed_decrease_percent": 5},
    )
    assert missing.status_code == 404


def test_digifresh_aggregate_low_price_is_toman() -> None:
    html = (
        '<html><script type="application/ld+json">'
        '{"@type":"Product","offers":{"@type":"AggregateOffer",'
        '"priceCurrency":"IRR","lowPrice":"7615100",'
        '"availability":"https://schema.org/InStock"}}'
        "</script></html>"
    )
    assert prices._parse_digifresh(html) == FetchedPrice(Decimal("7615100"), "IRT", True)
