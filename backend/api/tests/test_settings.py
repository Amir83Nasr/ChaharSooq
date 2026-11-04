"""Settings + config — threshold CRUD, DATABASE_URL trim."""

from fastapi.testclient import TestClient

from tests.helpers import login


def test_settings_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/settings").status_code == 401
    assert client.put("/api/v1/settings", json={"low_stock_threshold": 3}).status_code == 401


def test_settings_default_update_and_partial_keep(client: TestClient) -> None:
    login(client)
    assert client.get("/api/v1/settings").json() == {
        "low_stock_threshold": 5,
        "default_page_size": 0,
        "sync_interval_minutes": 1440,
        "competitor_sync_interval_minutes": 1440,
        "default_competitor_store": "digikala",
        "suggested_price_formulas": [],
    }
    r = client.put(
        "/api/v1/settings",
        json={"low_stock_threshold": 3, "default_page_size": 100},
    )
    assert r.status_code == 200, r.text
    # Partial update keeps the other field.
    partial = client.put("/api/v1/settings", json={"default_page_size": 500})
    assert partial.status_code == 200, partial.text
    assert partial.json() == {
        "low_stock_threshold": 3,
        "default_page_size": 500,
        "sync_interval_minutes": 1440,
        "competitor_sync_interval_minutes": 1440,
        "default_competitor_store": "digikala",
        "suggested_price_formulas": [],
    }


def test_settings_reject_invalid_values(client: TestClient) -> None:
    login(client)
    assert client.put("/api/v1/settings", json={"low_stock_threshold": -1}).status_code == 422
    assert client.put("/api/v1/settings", json={"low_stock_threshold": "زیاد"}).status_code == 422
    assert client.put("/api/v1/settings", json={"default_page_size": 15}).status_code == 422
    assert client.put("/api/v1/settings", json={"default_page_size": 7}).status_code == 422


def test_settings_competitor_sync_interval_update_and_reject(client: TestClient) -> None:
    login(client)
    r = client.put("/api/v1/settings", json={"competitor_sync_interval_minutes": 120})
    assert r.status_code == 200, r.text
    assert r.json()["competitor_sync_interval_minutes"] == 120
    assert (
        client.put("/api/v1/settings", json={"competitor_sync_interval_minutes": 5}).status_code
        == 422
    )
    assert (
        client.put("/api/v1/settings", json={"competitor_sync_interval_minutes": 20000}).status_code
        == 422
    )


def test_settings_competitor_store_update_and_reject(client: TestClient) -> None:
    login(client)
    r = client.put("/api/v1/settings", json={"default_competitor_store": "technolife"})
    assert r.status_code == 200, r.text
    assert r.json()["default_competitor_store"] == "technolife"
    assert (
        client.put("/api/v1/settings", json={"default_competitor_store": "other"}).status_code
        == 422
    )
    assert (
        client.put("/api/v1/settings", json={"default_competitor_store": "digifresh"}).status_code
        == 422
    )


def test_database_url_trailing_whitespace_stripped() -> None:
    from app.core.config import Settings

    s = Settings(database_url="postgresql+psycopg://u:p@host/db?sslmode=require ")
    assert s.database_url == "postgresql+psycopg://u:p@host/db?sslmode=require"
