"""Product cardex — Parsina invoice aggregation and API boundary."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import ParsinaSettings
from app.core.database import get_engine
from app.integrations.cardex_demo import demo_invoices
from app.models import Product
from app.services.cardex import ProductCardexService, _toman
from tests.helpers import login

SETTINGS = ParsinaSettings(
    parsina_base_url="http://parsina.test/Api/V1",
    parsina_username="u",
    parsina_password="p",
    parsina_org_id=1,
    parsina_year=1404,
    parsina_timeout_seconds=2,
)


def _envelope(data: Any) -> dict[str, Any]:
    return {"isSuccess": True, "statusCode": "Success", "message": None, "data": data, "total": 1}


class CardexParsina:
    def __init__(self) -> None:
        self.paths: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        if request.url.path.endswith("/Account"):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
        if request.url.path.endswith("/SaleFactor"):
            return httpx.Response(
                200,
                json=_envelope(
                    [{"id": 11, "Number": 5, "Date": "1404/08/20", "BuyerName": "مشتری"}]
                ),
            )
        if request.url.path.endswith("/buyFactor"):
            return httpx.Response(
                200,
                json=_envelope(
                    [{"id": 12, "Number": 9, "Date": "1404/08/19", "SellerName": "تأمینکننده"}]
                ),
            )
        if request.url.path.endswith("/SaleFactor/11"):
            return httpx.Response(
                200,
                json=_envelope(
                    {
                        "id": 11,
                        "Details": [
                            {"goodid": 42, "goodcode": "X-1", "TotalCount": 2, "NetPrice": 20000},
                            {"goodid": 99, "goodcode": "Y-1", "TotalCount": 1, "NetPrice": 5000},
                        ],
                    }
                ),
            )
        if request.url.path.endswith("/BuyFactor/12"):
            return httpx.Response(
                200,
                json=_envelope(
                    {
                        "id": 12,
                        "Details": [
                            {"goodid": 42, "goodcode": "X-1", "TotalCount": 3, "NetPrice": 30000}
                        ],
                    }
                ),
            )
        return httpx.Response(404, json={"isSuccess": False, "message": "not found"})


@pytest.fixture()
def session(client: TestClient) -> Iterator[Session]:
    """Depends on `client` so the in-memory schema exists before use."""
    with Session(get_engine()) as s:
        yield s


def _product(session: Session) -> Product:
    product = Product(
        name="کالای کارتکس",
        sku="X-1",
        price=1000,
        stock=0,
        external_id=42,
        is_active=True,
    )
    session.add(product)
    session.flush()
    return product


def test_invoice_rial_amounts_become_integer_toman() -> None:
    """Cardex amounts are integer Toman; odd Rial input rounds to whole Toman."""
    assert _toman(20000) == 2000
    assert _toman("20000") == 2000
    assert _toman(20000.0) == 2000
    assert _toman(None) == 0
    # Financial half-up rounding: 5 rials → 1 toman, 15 rials → 2 toman.
    assert _toman(5) == 1
    assert _toman(15) == 2


def test_cardex_aggregates_purchases_and_sales(session: Session) -> None:
    product = _product(session)
    fake = CardexParsina()
    service = ProductCardexService(session, settings=SETTINGS, transport=httpx.MockTransport(fake))

    report = service.get(product_id=product.id, period="30_days")

    assert report.period == "30_days"
    assert len(report.periods) == 4
    assert [p.key for p in report.periods] == ["today", "3_days", "7_days", "30_days"]
    assert report.summary.sale_quantity == 2
    assert report.summary.sale_amount == 2000
    assert report.summary.purchase_quantity == 3
    assert report.summary.purchase_amount == 3000
    assert [(e.kind, e.invoice_id) for e in report.entries] == [
        ("purchase", 12),
        ("sale", 11),
    ]
    assert report.entries[1].counterparty == "مشتری"
    assert report.entries[1].invoice_date == date(2025, 11, 11)
    assert any("SaleFactor" in path for path in fake.paths)
    assert any("buyFactor" in path for path in fake.paths)


def test_development_demo_invoices_cover_both_directions(session: Session) -> None:
    product = _product(session)
    today = date(2026, 11, 26)
    start = today - timedelta(days=6)

    sale = demo_invoices(product, kind="sale", from_date=start, to_date=today)
    purchase = demo_invoices(product, kind="purchase", from_date=start, to_date=today)

    assert sale
    assert purchase
    assert sale == demo_invoices(product, kind="sale", from_date=start, to_date=today)
    assert all(
        invoice["Details"][0]["goodid"] == product.external_id for invoice in sale + purchase
    )


def test_development_cardex_falls_back_to_demo_data(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.core import config

    # No saved fixtures under this path, so every direction comes from demo data.
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PRODUCTS_CSV_PATH", str(tmp_path / "products.json"))
    config.get_settings.cache_clear()
    try:
        product = _product(session)
        service = ProductCardexService(session, settings=ParsinaSettings())

        report = service.get(product_id=product.id, period="7_days")
        again = service.get(product_id=product.id, period="7_days")

        assert report.configured is True
        assert report.summary.purchase_quantity > 0
        assert report.summary.sale_quantity > 0
        assert {entry.kind for entry in report.entries} == {"purchase", "sale"}
        assert all(entry.invoice_date is not None for entry in report.entries)
        # Stable history across requests keeps the chart from jumping around.
        assert [(e.kind, e.invoice_id, e.quantity) for e in report.entries] == [
            (e.kind, e.invoice_id, e.quantity) for e in again.entries
        ]
    finally:
        config.get_settings.cache_clear()


def test_cardex_unconfigured_returns_empty_report(session: Session) -> None:
    product = _product(session)
    # Empty settings: the default tab must still open with an explicit state.
    service = ProductCardexService(session, settings=ParsinaSettings())
    report = service.get(product_id=product.id, period="today")
    assert report.configured is False
    assert report.entries == []
    assert report.summary.sale_amount == 0


def test_cardex_rejects_unknown_period(session: Session) -> None:
    product = _product(session)
    service = ProductCardexService(session, settings=SETTINGS)
    with pytest.raises(ValueError):
        service.get(product_id=product.id, period=" this_year ")


def test_cardex_route_validation_and_auth(client: TestClient, session: Session) -> None:
    product_id = _product(session).id
    # Unauthenticated calls never reach Parsina.
    assert client.get(f"/api/v1/products/{product_id}/cardex").status_code == 401
    login(client)
    response = client.get(f"/api/v1/products/{product_id}/cardex", params={"period": "bogus"})
    assert response.status_code == 422
    missing = client.get("/api/v1/products/999999/cardex")
    assert missing.status_code == 404
