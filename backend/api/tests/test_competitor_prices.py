"""Manual competitor link management and safe page parsing."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.integrations import competitor_prices as prices
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
        assert url.startswith("https://api.digikala.com/v2/product/")
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
