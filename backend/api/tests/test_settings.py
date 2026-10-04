"""Settings + config — threshold CRUD, DATABASE_URL trim."""

from fastapi.testclient import TestClient

from tests.helpers import login


def test_settings_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/settings").status_code == 401
    assert client.put("/api/v1/settings", json={"low_stock_threshold": 3}).status_code == 401


def test_settings_default_and_update(client: TestClient) -> None:
    login(client)
    assert client.get("/api/v1/settings").json() == {
        "low_stock_threshold": 10,
        "default_page_size": 10,
    }
    r = client.put(
        "/api/v1/settings",
        json={"low_stock_threshold": 3, "default_page_size": 20},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"low_stock_threshold": 3, "default_page_size": 20}
    assert client.get("/api/v1/settings").json() == {
        "low_stock_threshold": 3,
        "default_page_size": 20,
    }


def test_settings_partial_update_keeps_other_field(client: TestClient) -> None:
    login(client)
    r = client.put("/api/v1/settings", json={"default_page_size": 50})
    assert r.status_code == 200, r.text
    assert r.json() == {"low_stock_threshold": 10, "default_page_size": 50}


def test_settings_reject_invalid_threshold(client: TestClient) -> None:
    login(client)
    assert client.put("/api/v1/settings", json={"low_stock_threshold": -1}).status_code == 422
    assert client.put("/api/v1/settings", json={"low_stock_threshold": "زیاد"}).status_code == 422


def test_settings_reject_invalid_page_size(client: TestClient) -> None:
    login(client)
    assert client.put("/api/v1/settings", json={"default_page_size": 15}).status_code == 422
    assert client.put("/api/v1/settings", json={"default_page_size": 0}).status_code == 422


def test_database_url_trailing_whitespace_stripped() -> None:
    from app.core.config import Settings

    s = Settings(database_url="postgresql+psycopg://u:p@host/db?sslmode=require ")
    assert s.database_url == "postgresql+psycopg://u:p@host/db?sslmode=require"
