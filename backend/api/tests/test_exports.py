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
    text = content.decode("utf-8-sig")
    # RTL hint (U+200F) may follow the BOM.
    if text.startswith("\u200f"):
        text = text[1:]
    return list(csv.reader(io.StringIO(text)))


def _product_id(
    client: TestClient,
    *,
    name: str = "یخچال آزمایشی",
    sku: str = "FR-1",
    main_group_name: str | None = "لوازم خانگی یخچال",
) -> int:
    login(client)
    payload = {"name": name, "sku": sku, "price": 100_000_000, "stock": 3}
    if main_group_name is not None:
        payload["main_group_name"] = main_group_name
    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _listing_export(client: TestClient, **params: str | bool) -> list[list[str]]:
    return _rows(client.get("/api/v1/exports/competitor-listings.csv", params=params))


def _add_manual_listing(
    client: TestClient,
    product_id: int,
    *,
    store: str = "digikala",
    url: str = "https://www.digikala.com/product/dkp-123456/",
    price: int = 25_000_000,
) -> int:
    created = client.post(
        f"/api/v1/products/{product_id}/competitors",
        json={"store": store, "url": url},
    )
    assert created.status_code == 201, created.text
    listing_id = int(created.json()["id"])
    saved = client.patch(
        f"/api/v1/competitors/{listing_id}",
        json={"manual_price": price, "manual_currency": "IRT", "manual_in_stock": True},
    )
    assert saved.status_code == 200, saved.text
    return listing_id


def test_exports_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/exports/products.csv").status_code == 401
    assert client.get("/api/v1/exports/competitor-listings.csv").status_code == 401


def test_products_csv_mirrors_visible_table_columns(client: TestClient) -> None:
    seed(client)
    response = client.get("/api/v1/exports/products.csv")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith('attachment; filename="products-')
    assert response.content.startswith(b"\xef\xbb\xbf\xe2\x80\x8f")

    all_response = client.get("/api/v1/exports/products.csv", params={"scope": "all"})
    assert all_response.headers["content-disposition"].startswith(
        'attachment; filename="products-all-'
    )

    rows = _rows(response)
    headers = rows[0]
    # RTL export: columns start from the right, so ردیف is the rightmost column.
    assert headers[-1] == "ردیف"
    assert headers[0] == "موجودی"
    assert "قیمت (تومان)" in headers
    assert "موجودی" in headers
    # Database/internal columns must not be exported.
    assert "شناسه" not in headers
    assert "شناسه پارسینا" not in headers
    assert "تاریخ ایجاد" not in headers
    assert "فعال" not in headers
    assert "وضعیت موجودی" not in headers

    assert len(rows) == 4  # header + the three seeded products
    by_sku = {row[headers.index("کد")]: row for row in rows[1:]}
    tea = by_sku["TEA-1"]
    assert tea[headers.index("قیمت (تومان)")] == "۱۰۰"
    assert tea[headers.index("موجودی")] == "۵"
    # Row numbers are sequential in export order (default sort newest: by id desc).
    assert [row[headers.index("ردیف")] for row in rows[1:]] == ["۱", "۲", "۳"]


def test_products_csv_applies_filters_and_sort(client: TestClient) -> None:
    seed(client)
    response = client.get("/api/v1/exports/products.csv", params={"q": "CHE-1"})
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="products-filtered-'
    )
    filtered = _rows(response)
    headers = filtered[0]
    assert [row[headers.index("کد")] for row in filtered[1:]] == ["CHE-1"]

    cheapest = _rows(client.get("/api/v1/exports/products.csv", params={"sort": "cheapest"}))
    headers = cheapest[0]
    assert cheapest[1][headers.index("کد")] == "TEA-1"


def test_products_csv_respects_visible_columns_and_market(client: TestClient) -> None:
    from sqlalchemy.orm import Session

    from app.core.database import get_engine
    from app.models import Product

    product_id = _product_id(client)
    # Appliance group so the selected competitor market is shown (matches table logic).
    with Session(get_engine()) as db:
        product = db.get(Product, product_id)
        assert product is not None
        product.main_group_name = "لوازم خانگی یخچال"
        db.commit()

    _add_manual_listing(client, product_id)

    response = client.get(
        "/api/v1/exports/products.csv",
        params={
            "columns": "name,sku,price,competitor_price,price_diff,stock",
            "market": "digikala",
        },
    )
    assert response.status_code == 200, response.text
    rows = _rows(response)
    headers = rows[0]
    # RTL export: ردیف is the rightmost column and the rest follow in RTL order.
    assert headers == [
        "موجودی",
        "اختلاف درصد",
        "قیمت رقبا (دیجی‌کالا)",
        "قیمت (تومان)",
        "کد",
        "نام",
        "ردیف",
    ]
    row = rows[1]
    assert row[headers.index("ردیف")] == "۱"
    assert row[headers.index("نام")] == "یخچال آزمایشی"
    assert row[headers.index("قیمت رقبا (دیجی‌کالا)")] == "۲۵۰۰۰۰۰۰"
    # Base price 100m vs 25m market price → 300% more expensive.
    assert row[headers.index("اختلاف درصد")] == "۳۰۰٪ گران‌تر"

    scoped = client.get(
        "/api/v1/exports/products.csv",
        params={
            "columns": "name,sku,price,competitor_price,price_diff,stock",
            "market": "digikala",
            "scope": "filtered",
        },
    )
    assert scoped.headers["content-disposition"].startswith(
        'attachment; filename="products-filtered-'
    )


def test_products_csv_escapes_commas_and_quotes(client: TestClient) -> None:
    tricky = 'هندزفری "سیمی", طرح جدید'
    _product_id(client, name=tricky, sku="HP-9")
    rows = _rows(client.get("/api/v1/exports/products.csv", params={"q": "HP-9"}))
    assert len(rows) == 2
    assert rows[1][rows[0].index("نام")] == tricky


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


def test_products_csv_all_export_shows_both_competitor_markets(client: TestClient) -> None:
    from sqlalchemy.orm import Session

    from app.core.database import get_engine
    from app.models import Product

    product_id = _product_id(client)
    with Session(get_engine()) as db:
        product = db.get(Product, product_id)
        assert product is not None
        product.main_group_name = "لوازم خانگی یخچال"
        db.commit()

    _add_manual_listing(client, product_id, store="digikala", price=25_000_000)
    _add_manual_listing(
        client,
        product_id,
        store="technolife",
        url="https://www.technolife.com/product-123456",
        price=26_000_000,
    )

    response = client.get(
        "/api/v1/exports/products.csv",
        params={
            "columns": "name,sku,competitor_price,stock",
            "scope": "all",
        },
    )
    assert response.status_code == 200, response.text
    rows = _rows(response)
    headers = rows[0]
    # Full export includes both appliance competitor markets side by side.
    assert headers.index("قیمت رقبا (دیجی‌کالا)") > headers.index("قیمت رقبا (تکنولایف)")
    assert headers[-1] == "ردیف"
    row = rows[1]
    assert row[headers.index("قیمت رقبا (دیجی‌کالا)")] == "۲۵۰۰۰۰۰۰"
    assert row[headers.index("قیمت رقبا (تکنولایف)")] == "۲۶۰۰۰۰۰۰"

    filtered = client.get(
        "/api/v1/exports/products.csv",
        params={
            "columns": "name,sku,competitor_price,stock",
            "market": "digikala",
            "scope": "filtered",
        },
    )
    assert filtered.status_code == 200, filtered.text
    filtered_headers = _rows(filtered)[0]
    assert "قیمت رقبا (دیجی‌کالا)" in filtered_headers
    assert "قیمت رقبا (تکنولایف)" not in filtered_headers


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
