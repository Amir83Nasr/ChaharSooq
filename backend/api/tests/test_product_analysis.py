"""Product-analysis context — metrics, privacy, and owner-only route."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models import Product
from app.schemas import CardexEntryOut, CardexPeriod, CardexSummaryOut, ProductCardexOut
from app.schemas.competitor import CompetitorListingOut
from app.services.product_analysis import build_analysis_payload
from tests.helpers import login, login_as, login_owner

ANALYSIS_URL = "/api/v1/ai/products/{product_id}/analysis"
REPORT_URL = "/api/v1/ai/products/{product_id}/analysis/report"
TO_DATE = date(2026, 11, 26)
PERIODS = [
    CardexPeriod(
        key="30_days",
        label="۳۰ روز گذشته",
        from_date=TO_DATE - timedelta(days=29),
        to_date=TO_DATE,
    )
]


def _sale(
    *,
    days_ago: int,
    quantity: float = 1,
    amount: int = 38_000_000,
    invoice_id: int,
    cancelled: bool = False,
) -> CardexEntryOut:
    return CardexEntryOut(
        kind="sale",
        invoice_id=invoice_id,
        invoice_date=TO_DATE - timedelta(days=days_ago),
        quantity=quantity,
        net_price=amount,
        is_cancelled=cancelled,
    )


def _cardex(
    entries: list[CardexEntryOut],
    *,
    configured: bool = True,
    purchase_quantity: float = 0,
    purchase_amount: int = 0,
) -> ProductCardexOut:
    return ProductCardexOut(
        product_id=1,
        sku="TV-55",
        period="30_days",
        periods=PERIODS,
        summary=CardexSummaryOut(
            purchase_quantity=purchase_quantity,
            purchase_amount=purchase_amount,
            sale_quantity=sum(e.quantity for e in entries if not e.is_cancelled),
            sale_amount=sum(e.net_price for e in entries if not e.is_cancelled),
        ),
        entries=entries,
        configured=configured,
    )


def _product(**overrides: object) -> Product:
    values: dict[str, object] = {
        "name": "تلویزیون سامسونگ ۵۵ اینچ",
        "sku": "TV-55",
        "external_id": 42,
        "price": Decimal("38000000"),
        "stock": Decimal("18"),
        "buy_price": Decimal("30000000"),
        "main_group_name": "تلویزیون",
        "unit_name": "عدد",
        "allowed_decrease_percent": Decimal("5"),
        "allowed_increase_percent": Decimal("10"),
        "is_active": True,
    }
    values.update(overrides)
    return Product(**values)  # type: ignore[arg-type]


def _listing(
    *,
    listing_id: int,
    store: str,
    price: float | None,
    currency: str | None,
    fresh: bool,
    fetched_price: float | None = None,
) -> CompetitorListingOut:
    now = datetime.now(UTC)
    return CompetitorListingOut(
        id=listing_id,
        product_id=1,
        store=store,  # type: ignore[arg-type]
        url="https://shop.example/product/1",
        is_active=True,
        status="success",
        fetched_price=fetched_price,
        fetched_currency=currency,  # type: ignore[arg-type]
        effective_price=price if fresh else None,
        effective_currency=currency if fresh else None,  # type: ignore[arg-type]
        effective_in_stock=True,
        price_is_fresh=fresh,
        price_change_percent=-1.2 if fresh else None,
        created_at=now,
        updated_at=now,
    )


# ── PAYLOAD ───────────────────────────────────────────────────────────


def test_payload_computes_sales_inventory_reorder_and_market() -> None:
    sales = [_sale(days_ago=day, invoice_id=day + 1) for day in range(6)] + [
        _sale(days_ago=day, invoice_id=day + 1) for day in range(7, 25)
    ]
    cancelled = _sale(days_ago=0, quantity=5, invoice_id=99, cancelled=True)
    entries = [*sales, cancelled]

    payload = build_analysis_payload(
        product=_product(),
        cardex=_cardex(entries),
        listings=[
            _listing(
                listing_id=1,
                store="digikala",
                price=375_000_000,
                currency="IRR",
                fresh=True,
            ),
            _listing(
                listing_id=2,
                store="technolife",
                price=38_000_000,
                currency="IRT",
                fresh=True,
            ),
            _listing(
                listing_id=3,
                store="torob",
                price=None,
                currency="IRR",
                fresh=False,
                fetched_price=360_000_000,
            ),
        ],
        app_env="test",
    )

    sales_block = payload["sales"]
    assert sales_block["last_30_days"]["quantity"] == 24
    assert sales_block["last_7_days"]["quantity"] == 6
    assert sales_block["avg_daily_30d"] == 0.8
    assert sales_block["available"] is True

    inventory = payload["inventory"]
    assert inventory["stock"] == 18.0
    assert inventory["cover_days"] == 22.5
    assert inventory["stockout_risk"] == "low"
    assert inventory["overstock"] is False

    reorder = payload["reorder"]
    assert reorder["needed"] is True
    assert reorder["suggested_quantity"] == 24
    assert reorder["order_by"] is not None
    assert reorder["capital_toman"] == 720_000_000

    product = payload["product"]
    assert product["price_toman"] == 38_000_000
    assert product["margin_percent"] == 21.1

    market = payload["market"]
    # IRR is divided by 10 at this edge; IRT passes through.
    assert market["avg_price_toman"] == 37_750_000
    assert market["min_price_toman"] == 37_500_000
    assert market["max_price_toman"] == 38_000_000
    assert market["sample_size"] == 2
    assert market["our_diff_percent"] == 0.7
    assert market["price_bounds"] == {
        "floor_toman": 36_100_000,
        "ceiling_toman": 41_800_000,
    }
    assert payload["data_quality"]["stale_prices"] == 1


def test_payload_is_privacy_safe() -> None:
    entries = [_sale(days_ago=1, invoice_id=7)]
    payload = build_analysis_payload(
        product=_product(),
        cardex=_cardex(entries),
        listings=[],
        app_env="test",
    )
    serialized = json.dumps(payload, ensure_ascii=False)
    # Buyer/seller names, invoice ids, competitor URLs, and raw links stay out.
    assert "https://" not in serialized
    assert "invoice_id" not in serialized
    assert "counterparty" not in serialized
    assert "url" not in serialized


def test_payload_reports_missing_sales_and_cost_explicitly() -> None:
    product = _product(stock=Decimal("0"), buy_price=None)
    payload = build_analysis_payload(
        product=product,
        cardex=_cardex([], configured=False),
        listings=[
            _listing(
                listing_id=1,
                store="digikala",
                price=None,
                currency="IRR",
                fresh=False,
                fetched_price=100_000_000,
            )
        ],
        app_env="test",
    )

    assert payload["sales"]["available"] is False
    assert payload["sales"]["last_30_days"]["quantity"] == 0
    assert payload["sales"]["avg_daily_30d"] == 0
    assert payload["inventory"]["cover_days"] is None
    assert payload["inventory"]["stockout_risk"] == "unknown"
    assert payload["reorder"]["needed"] is False
    assert payload["reorder"]["suggested_quantity"] == 0
    assert payload["reorder"]["order_by"] is None
    assert payload["reorder"]["capital_toman"] == 0
    assert payload["market"]["sample_size"] == 0
    assert payload["market"]["avg_price_toman"] is None
    assert payload["data_quality"]["stale_prices"] == 1

    notes = " ".join(payload["data_quality"]["notes"])
    assert "پارسینا" in notes
    assert "دورهٔ قبل" in notes
    assert "قیمت خرید" in notes


def test_payload_flags_stockout_with_positive_sales() -> None:
    entries = [_sale(days_ago=day % 10, invoice_id=day + 1) for day in range(10)]
    payload = build_analysis_payload(
        product=_product(stock=Decimal("0"), buy_price=Decimal("30000000")),
        cardex=_cardex(entries),
        listings=[],
        app_env="test",
    )
    assert payload["inventory"]["stockout_risk"] == "high"
    assert payload["inventory"]["cover_days"] == 0.0
    assert payload["reorder"]["needed"] is True
    assert payload["reorder"]["suggested_quantity"] > 0
    assert payload["reorder"]["capital_toman"] is not None


# ── ROUTE ─────────────────────────────────────────────────────────────


def test_analysis_route_requires_a_management_account(client: TestClient) -> None:
    assert client.post(ANALYSIS_URL.format(product_id=1)).status_code == 401

    login(client)
    created = client.post(
        "/api/v1/users",
        json={"username": "analysis-viewer", "password": "viewer-pass-123", "role": "viewer"},
    )
    assert created.status_code == 201, created.text

    # Viewers can read reports but never generate one.
    login_as(client, "analysis-viewer", "viewer-pass-123")
    assert client.post(ANALYSIS_URL.format(product_id=1)).status_code == 403

    # Admins may generate; 503 proves the role guard passed and AI is unconfigured.
    login(client)
    assert client.post(ANALYSIS_URL.format(product_id=1)).status_code == 503


def test_analysis_route_fails_fast_when_ai_is_unconfigured(client: TestClient) -> None:
    login_owner(client)
    created = client.post(
        "/api/v1/products",
        json={"name": "کالای آزمون", "sku": "AI-1", "price": 1000, "stock": 4},
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    # AI is not configured, so the route fails before the cardex fetch and
    # never calls the provider.
    assert client.post(ANALYSIS_URL.format(product_id=product_id)).status_code == 503


def test_analysis_route_reports_missing_product_when_ai_is_configured(
    client: TestClient,
) -> None:
    login_owner(client)
    saved = client.put(
        "/api/v1/ai/settings",
        json={
            "base_url": "https://ai.example/v1",
            "api_key": "sk-test",
            "model_id": "test-model",
        },
    )
    assert saved.status_code == 200, saved.text

    # Product lookup fails before any provider request.
    assert client.post(ANALYSIS_URL.format(product_id=999)).status_code == 404


def test_analysis_route_streams_frames_from_server_built_context(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.ai import AIStream

    login_owner(client)
    saved = client.put(
        "/api/v1/ai/settings",
        json={
            "base_url": "https://ai.example/v1",
            "api_key": "sk-test",
            "model_id": "test-model",
        },
    )
    assert saved.status_code == 200, saved.text
    created = client.post(
        "/api/v1/products",
        json={"name": "کالای آزمون", "sku": "AI-1", "price": 1000, "stock": 4},
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]
    captured: dict[str, str] = {}
    chunks = ["سلام", " دنیا"]

    def fake_stream(_self: object, messages: list[dict[str, str]]) -> AIStream:
        captured["content"] = messages[0]["content"]
        return AIStream(model="test-model", chunks=iter(chunks))

    monkeypatch.setattr("app.services.ai.AIService.stream", fake_stream)

    assert client.get(REPORT_URL.format(product_id=product_id)).status_code == 404
    response = client.post(ANALYSIS_URL.format(product_id=product_id))

    assert response.status_code == 200, response.text
    assert "event: delta" in response.text
    assert "سلام" in response.text
    assert "event: done" in response.text
    # The client cannot supply the prompt: the route sends its own JSON context.
    assert "دادهٔ کالا برای تحلیل" in captured["content"]
    assert '"sku": "AI-1"' in captured["content"]

    saved_report = client.get(REPORT_URL.format(product_id=product_id))
    assert saved_report.status_code == 200, saved_report.text
    assert saved_report.json()["content"] == "سلام دنیا"
    # Reports use the one configured model.
    assert saved_report.json()["model_id"] == "test-model"

    # A new complete analysis replaces the previous report.
    chunks[:] = ["نسخه", " تازه"]
    assert client.post(ANALYSIS_URL.format(product_id=product_id)).status_code == 200
    replaced = client.get(REPORT_URL.format(product_id=product_id))
    assert replaced.json()["content"] == "نسخه تازه"

    assert client.delete(REPORT_URL.format(product_id=product_id)).status_code == 204
    assert client.get(REPORT_URL.format(product_id=product_id)).status_code == 404


def test_report_routes_access(client: TestClient) -> None:
    assert client.get(REPORT_URL.format(product_id=1)).status_code == 401
    assert client.delete(REPORT_URL.format(product_id=1)).status_code == 401

    login(client)
    created = client.post(
        "/api/v1/users",
        json={"username": "report-viewer", "password": "viewer-pass-123", "role": "viewer"},
    )
    assert created.status_code == 201, created.text

    # A viewer may read the report (404 when none is saved) but never delete it.
    login_as(client, "report-viewer", "viewer-pass-123")
    assert client.get(REPORT_URL.format(product_id=1)).status_code == 404
    assert client.delete(REPORT_URL.format(product_id=1)).status_code == 403

    # Admins keep full access; deleting a missing report is idempotent.
    login(client)
    assert client.delete(REPORT_URL.format(product_id=1)).status_code == 204
    assert client.delete(REPORT_URL.format(product_id=1)).status_code == 204
