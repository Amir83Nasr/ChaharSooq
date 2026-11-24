"""Products — CRUD, filters, paging, summary."""

from fastapi.testclient import TestClient

from app.repositories import SHOW_ALL_MAX
from tests.helpers import login, seed


def test_products_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/products/summary").status_code == 401


def test_product_crud_roundtrip(client: TestClient) -> None:
    login(client)
    created = client.post(
        "/api/v1/products",
        json={"name": "چای", "sku": "TEA-1", "price": 1000000, "stock": 5},
    )
    assert created.status_code == 201, created.text
    assert created.json()["price"] == 1000000  # machine value, never Persian digits
    page = client.get("/api/v1/products").json()
    assert page["total"] == 1
    assert page["items"][0]["sku"] == "TEA-1"


def test_product_validation_envelope(client: TestClient) -> None:
    login(client)
    r = client.post("/api/v1/products", json={"name": "", "sku": "x", "price": -1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_products_reject_page_size_above_service_cap(client: TestClient) -> None:
    login(client)
    r = client.get("/api/v1/products", params={"page_size": 501})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_product_listing_filters_sort_and_search(client: TestClient) -> None:
    ids = seed(client)
    # SKU search
    assert [
        i["sku"] for i in client.get("/api/v1/products", params={"q": "CHE-"}).json()["items"]
    ] == ["CHE-1"]
    # Category + stock + price range + sort in one seeded catalog:
    # TEA-1 (100×5), CHE-1 (300×0), COF-1 (200×2)
    by_cat = client.get("/api/v1/products", params={"category_id": ids["لبنیات"]}).json()
    assert [i["sku"] for i in by_cat["items"]] == ["CHE-1"]
    assert client.get("/api/v1/products", params={"in_stock": True}).json()["total"] == 2
    ranged = client.get("/api/v1/products", params={"min_price": 150, "max_price": 250}).json()
    assert [i["sku"] for i in ranged["items"]] == ["COF-1"]
    cheapest = client.get("/api/v1/products", params={"sort": "cheapest"}).json()
    assert [i["price"] for i in cheapest["items"]] == [100, 200, 300]
    # Stock windows
    low = client.get("/api/v1/products", params={"in_stock": True, "max_stock": 5}).json()
    assert {i["sku"] for i in low["items"]} == {"TEA-1", "COF-1"}
    assert client.get("/api/v1/products", params={"min_stock": 6}).json()["total"] == 0
    assert client.get("/api/v1/products", params={"min_stock": -1}).status_code == 422
    assert client.get("/api/v1/products", params={"pricing_mode": "نامعتبر"}).status_code == 422


def test_product_pagination_total(client: TestClient) -> None:
    seed(client)
    first = client.get("/api/v1/products", params={"page": 1, "page_size": 2}).json()
    second = client.get("/api/v1/products", params={"page": 2, "page_size": 2}).json()
    assert (first["total"], second["total"]) == (3, 3)
    assert len(first["items"]) == 2 and len(second["items"]) == 1


def test_product_invalid_category_rejected(client: TestClient) -> None:
    login(client)
    r = client.post(
        "/api/v1/products",
        json={"name": "x", "sku": "X-1", "price": 1, "category_id": 9999},
    )
    assert r.status_code == 422


def test_no_competitor_price_is_third_mode_and_filterable(client: TestClient) -> None:
    """The old flag/endpoint are gone; no-price state is a pricing mode."""
    login(client)
    created = client.post(
        "/api/v1/products",
        json={"name": "کالای خاص", "sku": "UNIQUE-1", "price": 1000000},
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]
    assert "no_competitor_price" not in created.json()

    missing_endpoint = client.patch(
        f"/api/v1/products/{product_id}/no-competitor-price",
        json={"no_competitor_price": True},
    )
    assert missing_endpoint.status_code == 404

    r = client.patch(
        f"/api/v1/products/{product_id}/pricing-mode",
        json={"pricing_mode": "no_competitor_price"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["pricing_mode"] == "no_competitor_price"
    assert "no_competitor_price" not in r.json()

    listed = client.get("/api/v1/products", params={"q": "UNIQUE-1"}).json()
    assert listed["items"][0]["pricing_mode"] == "no_competitor_price"
    filtered = client.get("/api/v1/products", params={"pricing_mode": "no_competitor_price"}).json()
    assert [item["id"] for item in filtered["items"]] == [product_id]
    other_modes = client.get("/api/v1/products", params={"pricing_mode": "exact_competitor"}).json()
    assert product_id not in [item["id"] for item in other_modes["items"]]


def test_product_pricing_mode_toggles(client: TestClient) -> None:
    login(client)
    created = client.post(
        "/api/v1/products",
        json={"name": "قالیچه", "sku": "MODE-1", "price": 1000000},
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]
    assert created.json()["pricing_mode"] == "exact_competitor"

    changed = client.patch(
        f"/api/v1/products/{product_id}/pricing-mode",
        json={"pricing_mode": "similar_product"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["pricing_mode"] == "similar_product"
    listed = client.get("/api/v1/products", params={"q": "MODE-1"}).json()
    assert listed["items"][0]["pricing_mode"] == "similar_product"

    back = client.patch(
        f"/api/v1/products/{product_id}/pricing-mode",
        json={"pricing_mode": "exact_competitor"},
    )
    assert back.json()["pricing_mode"] == "exact_competitor"
    assert (
        client.patch(
            f"/api/v1/products/{product_id}/pricing-mode",
            json={"pricing_mode": "نامعتبر"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/products/999999/pricing-mode",
            json={"pricing_mode": "similar_product"},
        ).status_code
        == 404
    )


def test_products_summary_counts(client: TestClient) -> None:
    seed(client)
    body = client.get("/api/v1/products/summary", params={"threshold": 5}).json()
    # seed: TEA-1 (5×100), CHE-1 (0×300), COF-1 (2×200) → value 500+0+400
    assert body == {"total": 3, "in_stock": 0, "low": 2, "out": 1, "stock_value": 900}


def test_show_all_cap_matches_web_constant() -> None:
    """Keep backend SHOW_ALL_MAX in sync with apps/web/lib/api.ts."""
    assert SHOW_ALL_MAX == 3000


def test_products_show_all_reports_real_page_size(client: TestClient) -> None:
    """page_size=0 returns the whole list and echoes its length (never 1)."""
    seed(client)
    body = client.get("/api/v1/products", params={"page_size": 0}).json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 3
    assert len(body["items"]) == 3


def test_product_section_filter_separates_digital_goods(client: TestClient) -> None:
    """کالای دیجیتال is its own section, not part of لوازم خانگی."""
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from app.core.database import get_engine
    from app.models import Product

    login(client)
    with Session(get_engine()) as db:
        db.add_all(
            [
                Product(
                    name="فرش آدینا",
                    sku="RUG-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="فرش آدینا",
                ),
                Product(
                    name="مبل راحتی",
                    sku="SOF-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="مبلمان",
                ),
                Product(
                    name="یخچال",
                    sku="FRZ-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="لوازم خانگی اسنوا",
                ),
                Product(
                    name="گوشی",
                    sku="PHN-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="گوشی و تبلت",
                    main_group_id=57,
                ),
                Product(
                    name="کنسول",
                    sku="CON-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="کنسول بازی",
                    main_group_id=56,
                ),
                # Old exports used id 7 for laptops; the current catalog uses
                # it for an appliance group. Name must win over the stale id.
                Product(
                    name="بلانتون",
                    sku="BLN-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="لوازم خانگی بلانتون",
                    main_group_id=7,
                ),
            ]
        )
        db.commit()

    def section_skus(**params: object) -> set[str]:
        body = client.get("/api/v1/products", params=params).json()
        return {item["sku"] for item in body["items"]}

    assert section_skus(top_group="کالای دیجیتال") == {"PHN-1", "CON-1"}
    assert section_skus(top_group="لوازم خانگی") == {"FRZ-1", "BLN-1"}
    assert section_skus(top_group=["لوازم خانگی", "کالای دیجیتال"]) == {
        "FRZ-1",
        "BLN-1",
        "PHN-1",
        "CON-1",
    }
    assert section_skus(top_group="فرش") == {"RUG-1"}
    assert client.get("/api/v1/products", params={"top_group": "نامعتبر"}).status_code == 422


def test_category_sort_groups_by_section_not_stale_group_id(client: TestClient) -> None:
    """Digital first, then appliances — even when an appliance carries id 7."""
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from app.core.database import get_engine
    from app.models import Product

    login(client)
    with Session(get_engine()) as db:
        db.add_all(
            [
                Product(
                    name="یخچال بلانتون",
                    sku="BLN-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="لوازم خانگی بلانتون",
                    main_group_id=7,
                ),
                Product(
                    name="گوشی",
                    sku="PHN-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="گوشی و تبلت",
                    main_group_id=28,
                ),
            ]
        )
        db.commit()

    items = client.get("/api/v1/products", params={"sort": "category"}).json()["items"]
    assert [item["sku"] for item in items] == ["PHN-1", "BLN-1"]


def test_new_group_names_are_classified_by_the_api_and_sql_filter(client: TestClient) -> None:
    """New Parsina group names need no code change to enter the digital section."""
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from app.core.database import get_engine
    from app.models import Product

    login(client)
    with Session(get_engine()) as db:
        db.add_all(
            [
                Product(
                    name="لپتاپ گیمینگ",
                    sku="LAP-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="لپتاپ گیمینگ",
                ),
                Product(
                    name="آیفون",
                    sku="MOB-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="گوشي و تبلت",  # Parsina's Arabic yeh
                ),
                Product(
                    name="تلویزیون",
                    sku="TAP-1",
                    price=Decimal(100),
                    stock=Decimal(1),
                    main_group_name="لوازم خانگی سونی",
                ),
                Product(name="چای", sku="MAN-1", price=Decimal(100), stock=Decimal(1)),
            ]
        )
        db.commit()

    by_sku = {item["sku"]: item for item in client.get("/api/v1/products").json()["items"]}
    assert by_sku["LAP-1"]["top_group"] == "کالای دیجیتال"
    assert by_sku["MOB-1"]["top_group"] == "کالای دیجیتال"
    assert by_sku["TAP-1"]["top_group"] == "لوازم خانگی"
    assert by_sku["MAN-1"]["top_group"] is None
    digital = client.get("/api/v1/products", params={"top_group": "کالای دیجیتال"}).json()
    assert {item["sku"] for item in digital["items"]} == {"LAP-1", "MOB-1"}


def test_product_groups_cache_headers(client: TestClient) -> None:
    seed(client)
    r = client.get("/api/v1/products/groups")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "private, max-age=60"
    assert r.headers["ETag"].startswith('"') and r.headers["ETag"].endswith('"')


def test_categories_list_cache_headers(client: TestClient) -> None:
    seed(client)
    r = client.get("/api/v1/categories")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "private, max-age=60"
    assert "ETag" in r.headers
