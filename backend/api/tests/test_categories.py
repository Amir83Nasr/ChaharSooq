"""Categories — CRUD + in-use delete guard."""

from fastapi.testclient import TestClient

from tests.helpers import login, seed


def test_category_crud_and_conflicts(client: TestClient) -> None:
    login(client)
    r = client.post("/api/v1/categories", json={"name": "خواربار"})
    assert r.status_code == 201, r.text
    assert client.post("/api/v1/categories", json={"name": "خواربار"}).status_code == 409
    names = [c["name"] for c in client.get("/api/v1/categories").json()]
    assert names == ["خواربار"]


def test_category_delete_guards(client: TestClient) -> None:
    ids = seed(client)
    assert client.delete("/api/v1/categories/9999").status_code == 404
    busy = client.delete(f"/api/v1/categories/{ids['خواربار']}")
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "category_in_use"
