"""Manual competitor link management and safe page parsing."""

import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_engine
from app.integrations import competitor_prices as prices
from app.integrations.competitor_prices import FetchedPrice, PriceFetchError, _price_from_html
from app.models import CompetitorListing, Product
from app.models.competitor import CompetitorSyncState
from app.services.competitor_sync import (
    CompetitorSyncBusyError,
    CompetitorSyncService,
    run_scheduled_competitor_sync,
)
from tests.helpers import login


@pytest.fixture()
def db_session(client: TestClient) -> Iterator[Session]:
    """Depends on `client` so the in-memory schema exists before use."""
    with Session(get_engine()) as s:
        yield s


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

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", fail_fetch)
    checked = client.post(f"/api/v1/competitors/{listing_id}/check")
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["status"] == "blocked"
    assert body["manual_price"] == 25000000
    assert body["effective_price"] == 25000000
    assert body["last_error"] == "تست محدودیت"


def test_product_delete_is_blocked_while_a_competitor_link_exists(client: TestClient) -> None:
    product_id = _product_id(client)
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-123456/"},
    )
    assert created.status_code == 201, created.text

    with Session(get_engine()) as session:
        # SQLite (local test runs) does not enforce foreign keys unless asked;
        # CI uses PostgreSQL where RESTRICT is always active.
        if session.bind is not None and session.bind.dialect.name == "sqlite":
            session.execute(text("PRAGMA foreign_keys=ON"))
        with pytest.raises(IntegrityError):
            session.execute(delete(Product).where(Product.id == product_id))
            session.commit()


def test_bulk_check_refreshes_all_active_listings(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    product_id = _product_id(client)
    first = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-123456/"},
    )
    second = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "technolife", "url": "https://www.technolife.ir/product-122293/"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    def ok_fetch(_store: str, _url: str) -> FetchedPrice:
        return FetchedPrice(Decimal("27000000"), "IRR", True, datetime.now(UTC))

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", ok_fetch)
    bulk = client.post(f"/api/v1/products/{product_id}/competitors/check")
    assert bulk.status_code == 200, bulk.text
    body = bulk.json()
    assert len(body) == 2
    assert {item["store"] for item in body} == {"digikala", "technolife"}
    assert all(item["status"] == "success" for item in body)
    assert all(item["effective_price"] == 27000000 for item in body)


def test_bulk_check_unknown_product_is_not_found(client: TestClient) -> None:
    login(client)
    response = client.post("/api/v1/products/999999/competitors/check")
    assert response.status_code == 404


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


def test_unknown_public_store_is_legacy_readonly(client: TestClient) -> None:
    product_id = _product_id(client)
    rejected = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "other", "url": "https://example.com/product/123"},
    )
    assert rejected.status_code == 422
    assert "برای این دسته فقط لینک" in rejected.json()["error"]["message"]

    # Links written before the category-only rule stay readable and checkable.
    with Session(get_engine()) as session:
        listing = CompetitorListing(
            product_id=product_id,
            store="other",
            url="https://example.com/product/123",
            is_active=True,
            status="pending",
        )
        session.add(listing)
        session.commit()
        listing_id = listing.id

    listed = client.get(f"/api/v1/products/{product_id}/competitors").json()
    assert [item["store"] for item in listed] == ["other"]
    checked = client.post(f"/api/v1/competitors/{listing_id}/check")
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == "unavailable"
    assert "پشتیبانی" in checked.json()["last_error"]

    # The store may not be switched to another one, but unchanged stays valid.
    unchanged = client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"manual_price": 25000000, "manual_currency": "IRT"},
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["effective_price"] == 25000000
    switched = client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-1/"},
    )
    assert switched.status_code == 422  # cannot move a legacy "other" link to another store


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
        json={"store": "technolife", "url": "https://www.technolife.ir/product/122293/"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["store"] == "technolife"
    assert edited.json()["url"] == "https://www.technolife.ir/product/122293/"
    assert edited.json()["manual_price"] == 25000000
    assert edited.json()["effective_price"] is None
    assert edited.json()["price_is_fresh"] is False


def test_competitor_store_and_pinned_filters(client: TestClient) -> None:
    """Store choice filters by that store; pinned selects owner-marked rows.

    "Best" is display-only and must never restrict the rows.
    """
    technolife_id = _product_id(client)
    digikala_id = client.post(
        "/api/v1/products",
        json={"name": "یخچال دیجی", "sku": "FRIDGE-DIGI", "price": 100000000},
    ).json()["id"]
    pinned_id = client.post(
        "/api/v1/products",
        json={"name": "کالای پین‌شده", "sku": "FRIDGE-PIN", "price": 100000000},
    ).json()["id"]

    for product_id, store, url in (
        (technolife_id, "technolife", "https://www.technolife.com/product/x"),
        (digikala_id, "digikala", "https://www.digikala.com/product/dkp-1/"),
    ):
        listing = client.post(
            f"/api/v1/products/{product_id}/competitors",
            json={"store": store, "url": url},
        ).json()
        client.patch(
            f"/api/v1/competitors/{listing['id']}",
            json={"manual_price": 30000000, "manual_currency": "IRT", "manual_in_stock": True},
        )

    changed = client.patch(
        f"/api/v1/products/{pinned_id}/pin",
        json={"pinned": True},
    )
    assert changed.status_code == 200, changed.text

    # Specific store: only products with a fresh price from that store.
    by_technolife = client.get("/api/v1/products", params={"competitor_store": "technolife"}).json()
    assert [item["id"] for item in by_technolife["items"]] == [technolife_id]
    by_digikala = client.get("/api/v1/products", params={"competitor_store": "digikala"}).json()
    assert [item["id"] for item in by_digikala["items"]] == [digikala_id]

    # Pin: only the owner-marked product, not merely products without prices.
    pinned = client.get("/api/v1/products", params={"pinned": True}).json()
    assert [item["id"] for item in pinned["items"]] == [pinned_id]
    similar = client.get("/api/v1/products", params={"pricing_mode": "similar_product"}).json()
    assert [item["id"] for item in similar["items"]] == []

    # No filter: every active product stays visible.
    all_items = client.get("/api/v1/products").json()
    assert {item["id"] for item in all_items["items"]} == {
        technolife_id,
        digikala_id,
        pinned_id,
    }


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


def _page(price: str, currency: str, availability: str, *, aggregate: bool = False) -> str:
    offers = (
        f'{{"@type":"AggregateOffer","priceCurrency":"{currency}",'
        f'"lowPrice":{price},"highPrice":{price},"offerCount":1,'
        f'"offers":[{{"price":{price},"priceCurrency":"{currency}",'
        f'"availability":"https://schema.org/{availability}"}}]}}'
        if aggregate
        else f'{{"price":"{price}","priceCurrency":"{currency}",'
        f'"availability":"https://schema.org/{availability}"}}'
    )
    return (
        '<html><script type="application/ld+json">'
        f'{{"@type":"Product","offers":{offers}}}'
        "</script></html>"
    )


@pytest.mark.parametrize(
    ("page_kwargs", "expected"),
    [
        (
            {"price": "42500000", "currency": "IRT", "availability": "InStock"},
            FetchedPrice(Decimal("42500000"), "IRT", True),
        ),
        (
            {
                "price": "2329000",
                "currency": "IRR",
                "availability": "InStock",
                "aggregate": True,
            },
            FetchedPrice(Decimal("2329000"), "IRR", True),
        ),
        (
            {
                "price": "112900000",
                "currency": "IRR",
                "availability": "OutOfStock",
                "aggregate": True,
            },
            FetchedPrice(Decimal("112900000"), "IRR", False),
        ),
    ],
)
def test_json_ld_offer_shapes_are_parsed(
    page_kwargs: dict[str, object], expected: FetchedPrice
) -> None:
    assert _price_from_html(_page(**page_kwargs)) == expected  # type: ignore[arg-type]


def test_torob_json_ld_irr_is_divided_to_toman() -> None:
    # Torob labels the 10× Rial figure as IRR; 460000000 → ۴۶٬۰۰۰٬۰۰۰ تومان.
    page = _page("460000000", "IRR", "InStock", aggregate=True)
    assert prices._parse_torob(page) == FetchedPrice(Decimal("46000000"), "IRT", True)


def test_torob_aggregate_without_nested_offer_is_toman() -> None:
    page = (
        '<html><script type="application/ld+json">'
        '{"@type":"Product","offers":{"@type":"AggregateOffer",'
        '"priceCurrency":"IRR","lowPrice":1576000000,"highPrice":1576000000,'
        '"availability":"https://schema.org/InStock"}}'
        "</script></html>"
    )
    assert prices._parse_torob(page) == FetchedPrice(Decimal("157600000"), "IRT", True)


def test_torob_next_data_fallback_uses_toman() -> None:
    page = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"baseProduct":{"price":46000000}}}}'
        "</script></html>"
    )
    assert prices._parse_torob(page) == FetchedPrice(Decimal("46000000"), "IRT", True)


def test_technolife_out_of_stock_without_offer_is_not_a_price_error() -> None:
    """Real out-of-stock pages have JSON-LD Product with no offers at all.

    The page's __NEXT_DATA__ explicitly marks the product unavailable; it must
    be reported as an out-of-stock fetch (amount=None, in_stock=False), never
    as an extraction failure.
    """
    page = (
        '<html><script type="application/ld+json">'
        '{"@type":"Product","name":"آبسردکن بلانتون","sku":"278781"}'
        "</script>"
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"dehydratedState":{"queries":['
        '{"state":{"data":{"product_info":{"code":"TLP-278781",'
        '"is_available":false}}}}]}}}}'
        "</script></html>"
    )
    assert prices._parse_technolife(page) == FetchedPrice(None, None, False)


def test_technolife_missing_availability_stays_unresolved() -> None:
    # No offer, no availability signal: still an extraction problem.
    page = (
        '<html><script type="application/ld+json">'
        '{"@type":"Product","name":"محصول"}</script></html>'
    )
    assert prices._parse_technolife(page) is None


def test_technolife_available_page_keeps_parsed_offer() -> None:
    page = _page("112900000", "IRR", "InStock")
    assert prices._parse_technolife(page) == FetchedPrice(Decimal("112900000"), "IRT", True)


def test_torob_search_url_is_refused() -> None:
    with pytest.raises(PriceFetchError):
        prices._normalise_url("https://torob.com/search/?query=yakhchal", "torob")
    assert prices._normalise_url("https://torob.com/p/06b6dddf-3721-4b01-987e/", "torob")


def test_torob_product_url_validation() -> None:
    from app.services.competitor import validate_url

    assert validate_url("https://torob.com/p/06b6dddf-3721-4b01-987e/", "torob")
    with pytest.raises(ValueError, match="صفحهٔ محصول"):
        validate_url("https://torob.com/search/?query=yakhchal", "torob")


def _stub_settings(monkeypatch: MonkeyPatch, interval: float = 0.0) -> None:
    monkeypatch.setattr(
        prices,
        "get_settings",
        lambda: SimpleNamespace(
            competitor_request_interval_seconds=interval, competitor_price_ttl_hours=24
        ),
    )


class _FakeApiResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class _FakeApiClient:
    response: _FakeApiResponse = _FakeApiResponse(404)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_FakeApiClient":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def close(self) -> None:
        return None

    def get(self, url: str, headers: Any = None, **kwargs: Any) -> _FakeApiResponse:
        assert url.startswith("https://api.digikala.com/product/v1/products/")
        return _FakeApiClient.response


def _stub_digikala_api(monkeypatch: MonkeyPatch, response: _FakeApiResponse) -> None:
    _FakeApiClient.response = response
    monkeypatch.setattr(prices.httpx, "Client", _FakeApiClient)


def _marketable_payload(price: int = 27000000) -> dict[str, Any]:
    return {
        "status": 200,
        "data": {
            "product": {
                "id": 16621422,
                "status": "marketable",
                "default_variant": {
                    "id": 57647981,
                    "status": "marketable",
                    "price": {"selling_price": price, "rrp_price": 30000000},
                },
            }
        },
    }


def test_digikala_product_id_is_extracted_from_url() -> None:
    assert (
        prices._digikala_product_id("https://www.digikala.com/product/dkp-16621422/") == "16621422"
    )
    assert (
        prices._digikala_product_id("https://www.digikala.com/product/dkp-16621422/some-title")
        == "16621422"
    )
    assert prices._digikala_product_id("https://www.digikala.com/mag/") is None


def test_digikala_api_marketable_and_out_of_stock(monkeypatch: MonkeyPatch) -> None:
    _stub_settings(monkeypatch)
    _stub_digikala_api(monkeypatch, _FakeApiResponse(200, _marketable_payload()))
    assert prices._fetch_digikala_api("16621422") == FetchedPrice(Decimal("27000000"), "IRR", True)
    out_of_stock = {
        "status": 200,
        "data": {"product": {"id": 111111, "status": "out_of_stock", "default_variant": []}},
    }
    _stub_digikala_api(monkeypatch, _FakeApiResponse(200, out_of_stock))
    assert prices._fetch_digikala_api("111111") == FetchedPrice(None, None, False)


def test_digikala_api_falls_back_to_variant_list(monkeypatch: MonkeyPatch) -> None:
    _stub_settings(monkeypatch)
    payload = {
        "status": 200,
        "data": {
            "product": {
                "id": 16621422,
                "status": "marketable",
                "default_variant": {"id": 1, "status": "unmarketable", "price": {}},
                "variants": [
                    {"id": 1, "status": "unmarketable", "price": {}},
                    {"id": 2, "status": "marketable", "price": {"selling_price": 15000000}},
                ],
            }
        },
    }
    _stub_digikala_api(monkeypatch, _FakeApiResponse(200, payload))
    assert prices._fetch_digikala_api("16621422") == FetchedPrice(Decimal("15000000"), "IRR", True)


def test_digikala_api_prefers_marketable_variant(monkeypatch: MonkeyPatch) -> None:
    _stub_settings(monkeypatch)
    payload = {
        "status": 200,
        "data": {
            "product": {
                "id": 16621422,
                "status": "marketable",
                "default_variant": None,
                "variants": [
                    {"id": 1, "status": "unmarketable", "price": {"selling_price": 10000000}},
                    {"id": 2, "status": "marketable", "price": {"selling_price": 12000000}},
                ],
            }
        },
    }
    _stub_digikala_api(monkeypatch, _FakeApiResponse(200, payload))
    assert prices._fetch_digikala_api("16621422") == FetchedPrice(Decimal("12000000"), "IRR", True)


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [(404, "not_found"), (403, "blocked")],
)
def test_digikala_api_errors_are_mapped(
    monkeypatch: MonkeyPatch, status_code: int, expected_status: str
) -> None:
    _stub_settings(monkeypatch)
    _stub_digikala_api(monkeypatch, _FakeApiResponse(status_code, {"status": status_code}))
    prices._host_blocked_until.pop("digikala", None)
    with pytest.raises(PriceFetchError) as exc_info:
        prices._fetch_digikala_api("16621422")
    assert exc_info.value.status == expected_status
    if expected_status == "blocked":
        assert prices._host_blocked_until.get("digikala", 0) > 0


def test_fetch_falls_back_to_digikala_api_when_page_has_no_json_ld(
    monkeypatch: MonkeyPatch,
) -> None:
    _stub_settings(monkeypatch)
    prices._page_cache.clear()
    prices._host_blocked_until.clear()
    prices._host_last_request.clear()
    monkeypatch.setattr(prices, "_robots_allows", lambda _url, **_kwargs: None)
    monkeypatch.setattr(
        prices, "_request", lambda _url, **_kwargs: (200, "<html><body>shell</body></html>", _url)
    )
    monkeypatch.setattr(
        prices,
        "_fetch_digikala_api",
        lambda _pid, **_kwargs: FetchedPrice(Decimal("27000000"), "IRR", True),
    )
    result = prices.fetch_competitor_price(
        "digikala", "https://www.digikala.com/product/dkp-16621422/"
    )
    assert result.amount == Decimal("27000000")
    assert result.currency == "IRR"
    assert result.in_stock is True
    assert result.observed_at is not None


def test_fetch_digikala_without_product_id_stays_unavailable(monkeypatch: MonkeyPatch) -> None:
    _stub_settings(monkeypatch)
    prices._page_cache.clear()
    prices._host_blocked_until.clear()
    prices._host_last_request.clear()
    monkeypatch.setattr(prices, "_robots_allows", lambda _url, **_kwargs: None)
    monkeypatch.setattr(
        prices, "_request", lambda _url, **_kwargs: (200, "<html><body>shell</body></html>", _url)
    )
    try:
        prices.fetch_competitor_price("digikala", "https://www.digikala.com/mag/")
    except PriceFetchError as exc:
        assert exc.status == "unavailable"
    else:
        raise AssertionError("expected PriceFetchError")


class _FakeStreamResponse:
    def __init__(self, status_code: int, location: str | None, body: bytes) -> None:
        self.status_code = status_code
        self.headers = {"location": location or "", "content-type": "text/html"}
        self._body = body

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308) and bool(self.headers["location"])

    def iter_bytes(self) -> Any:
        yield self._body


class _FakeStreamContext:
    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    def __enter__(self) -> _FakeStreamResponse:
        return self._response

    def __exit__(self, *args: Any) -> None:
        return None


class _FakeStreamClient:
    routes: dict[str, _FakeStreamResponse] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_FakeStreamClient":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def close(self) -> None:
        return None

    def get(self, url: str, headers: Any = None, **kwargs: Any) -> Any:
        raise AssertionError("stream client should not be used for API GET in this test")

    def stream(
        self, method: str, url: str, headers: Any = None, **kwargs: Any
    ) -> _FakeStreamContext:
        assert method == "GET"
        return _FakeStreamContext(_FakeStreamClient.routes[url])


def test_request_follows_redirect_chain_with_single_rate_slot(monkeypatch: MonkeyPatch) -> None:
    _stub_settings(monkeypatch)
    monkeypatch.setattr(prices, "_assert_public_dns", lambda _host: None)
    body = (
        b'<html><script type="application/ld+json">'
        b'{"@type":"Product","offers":{"price":112900000,"priceCurrency":"IRR",'
        b'"availability":"https://schema.org/InStock"}}</script></html>'
    )
    slug = "https://www.technolife.com/product-122293/title"
    _FakeStreamClient.routes = {
        "https://www.technolife.ir/product-122293/": _FakeStreamResponse(
            301, "https://www.technolife.com/product-122293/", b""
        ),
        "https://www.technolife.com/product-122293/": _FakeStreamResponse(
            308, "/product-122293", b""
        ),
        "https://www.technolife.com/product-122293": _FakeStreamResponse(
            301, "https://www.technolife.com/product-122293/a", b""
        ),
        "https://www.technolife.com/product-122293/a": _FakeStreamResponse(307, slug, b""),
        slug: _FakeStreamResponse(200, None, body),
    }
    monkeypatch.setattr(prices.httpx, "Client", _FakeStreamClient)
    calls: list[str] = []
    real_acquire = prices._acquire_slot

    def counting_acquire(rate_key: str) -> None:
        calls.append(rate_key)
        real_acquire(rate_key)

    monkeypatch.setattr(prices, "_acquire_slot", counting_acquire)
    prices._page_cache.clear()
    prices._host_last_request.clear()
    prices._host_blocked_until.clear()
    monkeypatch.setattr(prices, "_robots_allows", lambda _url, **_kwargs: None)
    result = prices.fetch_competitor_price(
        "technolife", "https://www.technolife.ir/product-122293/"
    )
    assert result.amount == Decimal("112900000")
    # Technolife labels Toman values as IRR; the adapter normalises to IRT.
    assert result.currency == "IRT"
    assert result.in_stock is True
    # Four HTTP hops, but only one interval wait: redirects must not each sleep.
    assert calls == ["technolife"]


def test_technolife_out_of_stock_page_is_a_successful_check(
    monkeypatch: MonkeyPatch,
) -> None:
    """The reported URL: no price, but explicitly out of stock on the site."""
    _stub_settings(monkeypatch)
    monkeypatch.setattr(prices, "_assert_public_dns", lambda _host: None)
    out_of_stock_page = (
        b'<html><script type="application/ld+json">'
        b'{"@type":"Product","name":"out of stock product"}'
        b"</script>"
        b'<script id="__NEXT_DATA__" type="application/json">'
        b'{"props":{"pageProps":{"dehydratedState":{"queries":['
        b'{"state":{"data":{"product_info":{"is_available":false}}}}]}}}}'
        b"</script></html>"
    )
    url = (
        "https://www.technolife.com/product-278781/"
        "%D8%A2%D8%A8%D8%B3%D8%B1%D8%AF%DA%A9%D9%86-%D8%A8%D9%84%D8%A7%D9%86%D8%AA%D9%88%D9%86-"
        "%D9%85%D8%AF%D9%84-bak-wd1201"
    )
    _FakeStreamClient.routes = {url: _FakeStreamResponse(200, None, out_of_stock_page)}
    monkeypatch.setattr(prices.httpx, "Client", _FakeStreamClient)
    prices._page_cache.clear()
    prices._host_last_request.clear()
    prices._host_blocked_until.clear()
    monkeypatch.setattr(prices, "_robots_allows", lambda _url, **_kwargs: None)

    result = prices.fetch_competitor_price("technolife", url)
    assert result.amount is None
    assert result.currency is None
    assert result.in_stock is False
    assert result.observed_at is not None


def test_technolife_out_of_stock_row_is_not_an_extraction_error(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    product_id = _product_id(client)
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={
            "store": "technolife",
            "url": "https://www.technolife.com/product-278781/out-of-stock",
        },
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    monkeypatch.setattr(
        "app.services.competitor_check.fetch_competitor_price",
        lambda _store, _url: FetchedPrice(None, None, False, datetime.now(UTC)),
    )
    checked = client.post(f"/api/v1/competitors/{listing_id}/check")
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["status"] == "success"
    assert body["last_error"] is None
    assert body["effective_in_stock"] is False
    assert body["effective_price"] is None


def _seed_two_products_with_links(client: TestClient) -> tuple[int, int]:
    login(client)
    first = client.post(
        "/api/v1/products",
        json={"name": "یخچال یک", "sku": "FRIDGE-A", "price": 100000000},
    )
    second = client.post(
        "/api/v1/products",
        json={"name": "یخچال دو", "sku": "FRIDGE-B", "price": 90000000},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_id = first.json()["id"]
    second_id = second.json()["id"]
    created = client.post(
        f"/api/v1/products/{first_id}/competitors",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-123456/"},
    )
    assert created.status_code == 201, created.text
    created = client.post(
        f"/api/v1/products/{second_id}/competitors",
        json={"store": "technolife", "url": "https://www.technolife.ir/product-122293/"},
    )
    assert created.status_code == 201, created.text
    return first_id, second_id


def test_global_sync_refreshes_every_active_link(
    client: TestClient, db_session: Session, monkeypatch: MonkeyPatch
) -> None:
    _seed_two_products_with_links(client)

    def ok_fetch(_store: str, _url: str) -> FetchedPrice:
        return FetchedPrice(Decimal("27000000"), "IRR", True, datetime.now(UTC))

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", ok_fetch)
    result = CompetitorSyncService(db_session).run()
    assert (result.checked, result.updated, result.failed, result.skipped) == (2, 2, 0, 0)

    state = db_session.get(CompetitorSyncState, 1)
    assert state is not None
    assert state.last_checked == 2
    assert state.last_updated == 2
    assert state.last_failed == 0
    assert state.last_success_at is not None
    assert state.last_error is None

    rows = db_session.query(CompetitorListing).all()
    assert len(rows) == 2
    assert all(row.status == "success" for row in rows)
    assert all(row.last_success_at is not None for row in rows)


def test_global_sync_counts_failures_without_aborting(
    client: TestClient, db_session: Session, monkeypatch: MonkeyPatch
) -> None:
    _seed_two_products_with_links(client)

    def flaky_fetch(store: str, _url: str) -> FetchedPrice:
        if store == "digikala":
            return FetchedPrice(Decimal("27000000"), "IRR", True, datetime.now(UTC))
        raise PriceFetchError("blocked", "تست محدودیت")

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", flaky_fetch)
    result = CompetitorSyncService(db_session).run()
    assert (result.checked, result.updated, result.failed) == (2, 1, 1)


def test_global_sync_skips_inactive_links(
    client: TestClient, db_session: Session, monkeypatch: MonkeyPatch
) -> None:
    first_id, _second_id = _seed_two_products_with_links(client)
    listings = client.get(f"/api/v1/products/{first_id}/competitors").json()
    assert len(listings) == 1
    disabled = client.patch(f"/api/v1/competitors/{listings[0]['id']}", json={"is_active": False})
    assert disabled.status_code == 200, disabled.text

    def ok_fetch(_store: str, _url: str) -> FetchedPrice:
        return FetchedPrice(Decimal("27000000"), "IRR", True, datetime.now(UTC))

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", ok_fetch)
    result = CompetitorSyncService(db_session).run()
    assert (result.checked, result.updated, result.skipped) == (1, 1, 1)


def test_global_sync_second_run_while_locked_raises_busy(
    client: TestClient, db_session: Session
) -> None:
    login(client)
    CompetitorSyncService(db_session).acquire()
    with Session(get_engine()) as other:
        with pytest.raises(CompetitorSyncBusyError):
            CompetitorSyncService(other).acquire()


def test_global_sync_endpoints_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/integrations/competitors/status").status_code == 401
    assert client.post("/api/v1/integrations/competitors/sync").status_code == 401


def test_global_sync_status_reports_idle_counters(client: TestClient) -> None:
    login(client)
    body = client.get("/api/v1/integrations/competitors/status").json()
    assert body["running"] is False
    assert body["last_checked"] == 0
    assert body["last_updated"] == 0


def test_global_sync_endpoint_returns_409_while_locked(client: TestClient) -> None:
    login(client)
    with Session(get_engine()) as s:
        state = s.get(CompetitorSyncState, 1)
        if state is None:
            state = CompetitorSyncState(id=1)
            s.add(state)
        state.lock_until = datetime.now(UTC).replace(year=datetime.now(UTC).year + 1)
        state.running_since = datetime.now(UTC)
        s.commit()
    response = client.post("/api/v1/integrations/competitors/sync")
    assert response.status_code == 409
    body = client.get("/api/v1/integrations/competitors/status").json()
    assert body["running"] is True


def test_scheduled_competitor_sync_runs_when_due(client: TestClient, db_session: Session) -> None:
    result = run_scheduled_competitor_sync(
        session_factory=lambda: Session(get_engine()), interval_minutes=360
    )
    assert result is not None
    assert (result.checked, result.updated, result.failed, result.skipped) == (0, 0, 0, 0)


def test_scheduled_competitor_sync_skips_before_interval_elapses(
    client: TestClient, db_session: Session
) -> None:
    factory = lambda: Session(get_engine())  # noqa: E731
    assert run_scheduled_competitor_sync(session_factory=factory, interval_minutes=360) is not None
    assert run_scheduled_competitor_sync(session_factory=factory, interval_minutes=360) is None


def test_scheduled_competitor_sync_skips_while_locked(
    client: TestClient, db_session: Session
) -> None:
    CompetitorSyncService(db_session).acquire()
    assert (
        run_scheduled_competitor_sync(
            session_factory=lambda: Session(get_engine()), interval_minutes=360
        )
        is None
    )


def test_global_sync_runs_different_stores_concurrently(
    client: TestClient, db_session: Session, monkeypatch: MonkeyPatch
) -> None:
    """Workers must overlap across stores, each with its own Session."""
    _seed_two_products_with_links(client)
    # Another test may have left a long-held lock in the shared state row.
    state = db_session.get(CompetitorSyncState, 1)
    if state is not None:
        state.lock_until = None
        state.running_since = None
        db_session.commit()
    barrier = threading.Barrier(2, timeout=15)
    seen: list[str] = []

    def blocking_fetch(store: str, _url: str) -> FetchedPrice:
        seen.append(store)
        barrier.wait()  # deadlocks if the two links are checked sequentially
        return FetchedPrice(Decimal("27000000"), "IRR", True, datetime.now(UTC))

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", blocking_fetch)
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        result = CompetitorSyncService(session, session_factory=factory).run()
    assert (result.checked, result.updated, result.failed) == (2, 2, 0)
    assert sorted(seen) == ["digikala", "technolife"]

    rows = db_session.query(CompetitorListing).all()
    assert len(rows) == 2
    assert all(row.status == "success" for row in rows)


def test_blocked_fetch_does_not_throttle_the_next_check(
    client: TestClient, db_session: Session, monkeypatch: MonkeyPatch
) -> None:
    """A local cooldown sends no request, so no check timestamp is recorded."""
    first_id, _second_id = _seed_two_products_with_links(client)
    listing = client.get(f"/api/v1/products/{first_id}/competitors").json()[0]
    listing_id = listing["id"]

    from app.services.competitor import CompetitorService

    monkeypatch.setattr(
        "app.services.competitor_check.fetch_competitor_price",
        lambda _store, _url: (_ for _ in ()).throw(
            PriceFetchError("blocked", "محدودیت موقت فروشگاه")
        ),
    )
    CompetitorService(db_session).check(listing_id)
    db_session.expire_all()
    row = db_session.get(CompetitorListing, listing_id)
    assert row is not None
    assert row.last_checked_at is None
    assert row.status == "blocked"

    # The next check is allowed immediately because nothing was actually sent.
    monkeypatch.setattr(
        "app.services.competitor_check.fetch_competitor_price",
        lambda _store, _url: FetchedPrice(Decimal("27000000"), "IRR", True, datetime.now(UTC)),
    )
    result = CompetitorService(db_session).check(listing_id)
    assert result.status == "success"


def test_global_sync_uses_one_worker_per_store(
    client: TestClient, db_session: Session, monkeypatch: MonkeyPatch
) -> None:
    """Links of one store stay in a single worker; stores run in parallel."""
    first_id, second_id = _seed_two_products_with_links(client)
    # Add a second digikala link so that store has two links to serialize.
    third = client.post(
        "/api/v1/products",
        json={"name": "یخچال سه", "sku": "FRIDGE-C", "price": 95000000},
    )
    assert third.status_code == 201, third.text
    created = client.post(
        f"/api/v1/products/{third.json()['id']}/competitors",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-654321/"},
    )
    assert created.status_code == 201, created.text

    barrier = threading.Barrier(2, timeout=15)
    digikala_calls = 0
    digikala_lock = threading.Lock()
    store_starts: list[str] = []

    def tracking_fetch(store: str, _url: str) -> FetchedPrice:
        nonlocal digikala_calls
        if store == "digikala":
            with digikala_lock:
                digikala_calls += 1
                call_no = digikala_calls
            if call_no == 1:
                store_starts.append("digikala")
                barrier.wait()  # waits for the technolife worker
        else:
            store_starts.append(store)
            barrier.wait()
        return FetchedPrice(Decimal("27000000"), "IRR", True, datetime.now(UTC))

    monkeypatch.setattr("app.services.competitor_check.fetch_competitor_price", tracking_fetch)
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        result = CompetitorSyncService(session, session_factory=factory).run()
    assert (result.checked, result.updated, result.failed) == (3, 3, 0)
    assert digikala_calls == 2
    assert sorted(store_starts) == ["digikala", "technolife"]
