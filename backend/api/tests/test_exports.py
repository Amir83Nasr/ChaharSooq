"""CSV exports — headers, filters, Persian formatting, and access rules."""

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.core.persian_format import format_amount, format_jalali_datetime, format_percent
from app.services import exports as export_service
from tests.helpers import login, seed


def _rows(response: object) -> list[list[str]]:
    content: bytes = response.content  # type: ignore[attr-defined]
    assert content.startswith(b"\xef\xbb\xbf"), "CSV must start with a UTF-8 BOM"
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def _product_id(client: TestClient, *, name: str = "یخچال آزمایشی", sku: str = "FR-1") -> int:
    login(client)
    response = client.post(
        "/api/v1/products",
        json={"name": name, "sku": sku, "price": 100_000_000, "stock": 3},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _listing_export(client: TestClient, **params: str | bool) -> list[list[str]]:
    return _rows(client.get("/api/v1/exports/competitor-listings.csv", params=params))


def _add_manual_listing(client: TestClient, product_id: int) -> int:
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": "digikala", "url": "https://www.digikala.com/product/dkp-123456/"},
    )
    assert created.status_code == 201, created.text
    listing_id = int(created.json()["id"])
    saved = client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"manual_price": 25_000_000, "manual_currency": "IRT", "manual_in_stock": True},
    )
    assert saved.status_code == 200, saved.text
    return listing_id


def test_exports_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/exports/products.csv").status_code == 401
    assert client.get("/api/v1/exports/competitor-listings.csv").status_code == 401


def test_products_csv_headers_values_and_jalali_dates(client: TestClient) -> None:
    seed(client)
    response = client.get("/api/v1/exports/products.csv")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith('attachment; filename="products-')
    headers = _rows(response)[0]
    assert headers[0] == "شناسه"
    assert "قیمت (تومان)" in headers
    # Operational noise stays out of the analysis file.
    assert "تاریخ ایجاد" not in headers
    assert "فعال" not in headers

    rows = _rows(response)
    assert len(rows) == 4  # header + the three seeded products
    by_sku = {row[headers.index("کد")]: row for row in rows[1:]}
    tea = by_sku["TEA-1"]
    assert tea[headers.index("قیمت (تومان)")] == "۱۰۰"
    assert tea[headers.index("موجودی")] == "۵"
    # Default low-stock threshold is 5.
    assert tea[headers.index("وضعیت موجودی")] == "موجودی کم"
    assert by_sku["CHE-1"][headers.index("وضعیت موجودی")] == "ناموجود"


def test_products_csv_applies_filters_and_sort(client: TestClient) -> None:
    seed(client)
    filtered = _rows(client.get("/api/v1/exports/products.csv", params={"q": "CHE-1"}))
    assert [row[2] for row in filtered[1:]] == ["CHE-1"]

    cheapest = _rows(client.get("/api/v1/exports/products.csv", params={"sort": "cheapest"}))
    assert cheapest[1][2] == "TEA-1"


def test_products_csv_escapes_commas_and_quotes(client: TestClient) -> None:
    tricky = 'هندزفری "سیمی", طرح جدید'
    _product_id(client, name=tricky, sku="HP-9")
    rows = _rows(client.get("/api/v1/exports/products.csv", params={"q": "HP-9"}))
    assert len(rows) == 2
    assert rows[1][rows[0].index("نام")] == tricky


def test_products_csv_includes_fresh_competitor_prices(client: TestClient) -> None:
    product_id = _product_id(client)
    _add_manual_listing(client, product_id)

    response = client.get("/api/v1/exports/products.csv")
    headers = _rows(response)[0]
    row = _rows(response)[1]
    assert row[headers.index("قیمت دیجی‌کالا")] == "۲۵۰۰۰۰۰۰"
    assert row[headers.index("کمینه قیمت رقبا")] == "۲۵۰۰۰۰۰۰"
    # Base price 100m vs the 25m market minimum → +300%.
    assert row[headers.index("اختلاف با کمینه رقبا (٪)")] == "+۳۰۰٪"
    # Stores without a fresh price stay empty rather than showing a stale one.
    assert row[headers.index("قیمت تکنولایف")] == ""


def test_competitor_listings_csv_filters_and_labels(client: TestClient) -> None:
    product_id = _product_id(client)
    _add_manual_listing(client, product_id)

    response = client.get("/api/v1/exports/competitor-listings.csv")
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="competitor-listings-'
    )
    rows = _rows(response)
    headers = rows[0]
    assert len(rows) == 2
    row = rows[1]
    assert row[headers.index("فروشگاه")] == "دیجی‌کالا"
    assert row[headers.index("وضعیت")] == "ثبت دستی"
    assert row[headers.index("فعال")] == "بله"
    assert row[headers.index("قیمت مؤثر (تومان)")] == "۲۵۰۰۰۰۰۰"
    assert row[headers.index("قیمت تازه")] == "بله"
    assert row[headers.index("موجود")] == "بله"

    assert len(_listing_export(client, store="sofa")) == 1
    assert len(_listing_export(client, status="success")) == 1
    assert len(_listing_export(client, is_active=False)) == 1


def test_competitor_listings_csv_respects_product_filters(client: TestClient) -> None:
    seed(client)
    product_id = _product_id(client)
    _add_manual_listing(client, product_id)

    rows = _listing_export(client, q="CHE-1")
    assert len(rows) == 1  # header only: the seeded catalog has no competitor links


def test_export_rejects_results_above_the_cap(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    seed(client)
    monkeypatch.setattr(export_service, "EXPORT_MAX_ROWS", 1)

    response = client.get("/api/v1/exports/products.csv")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "export_too_large"

    listing = client.get("/api/v1/exports/competitor-listings.csv")
    assert listing.status_code == 200  # zero listings still exports fine


def test_persian_format_helpers() -> None:
    assert format_amount(Decimal("1000000.00")) == "۱۰۰۰۰۰۰"
    assert format_amount(Decimal("12.500")) == "۱۲٫۵"
    assert format_amount(None) == ""
    assert format_percent(Decimal("-5")) == "−۵٪"
    assert format_percent(Decimal("2.5")) == "+۲٫۵٪"
    assert format_percent(Decimal("0")) == "۰٪"
    assert format_percent(None) == ""
    assert format_jalali_datetime(None) == ""
    # UTC 12:30 is 16:00 in Tehran.
    assert format_jalali_datetime(datetime(2026, 11, 12, 12, 30, tzinfo=UTC)) == "۱۴۰۵٫۰۸٫۲۱ ۱۶:۰۰"
