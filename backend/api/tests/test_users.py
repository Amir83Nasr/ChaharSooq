"""Role-based access + admin user management."""

from fastapi.testclient import TestClient

from tests.helpers import login, login_as

VIEWER_PASSWORD = "viewer-pass-123"


def create_viewer(client: TestClient, username: str = "viewer") -> dict[str, object]:
    r = client.post(
        "/api/v1/users",
        json={"username": username, "password": VIEWER_PASSWORD, "role": "viewer"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == username
    assert body["role"] == "viewer"
    return body


def test_admin_can_list_users(client: TestClient) -> None:
    login(client)
    r = client.get("/api/v1/users")
    assert r.status_code == 200
    assert [user["username"] for user in r.json()] == ["admin"]


def test_admin_creates_viewer_with_read_only_access(client: TestClient) -> None:
    login(client)
    create_viewer(client)
    login_as(client, "viewer", VIEWER_PASSWORD)

    # Reads stay available to every signed-in account.
    assert client.get("/api/v1/products").status_code == 200
    assert client.get("/api/v1/dashboard/summary").status_code == 200
    assert client.get("/api/v1/settings").status_code == 200
    assert client.get("/api/v1/categories").status_code == 200
    assert client.get("/api/v1/integrations/parsina/status").status_code == 200

    # Writes and account management require the admin role.
    product = {"name": "کالای آزمایشی", "sku": "VIEW-1", "price": 100, "stock": 1}
    writes = [
        client.post("/api/v1/products", json=product),
        client.post("/api/v1/categories", json={"name": "دسته آزمایشی"}),
        client.put("/api/v1/settings", json={"low_stock_threshold": 3}),
        client.post("/api/v1/integrations/parsina/sync"),
        client.post("/api/v1/integrations/competitors/sync"),
        client.get("/api/v1/users"),
        client.post(
            "/api/v1/users",
            json={"username": "sneaky", "password": "sneaky-pass-123", "role": "viewer"},
        ),
    ]
    for response in writes:
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "forbidden"


def test_admin_creates_another_admin(client: TestClient) -> None:
    login(client)
    r = client.post(
        "/api/v1/users",
        json={"username": "second-admin", "password": "second-pass-123", "role": "admin"},
    )
    assert r.status_code == 201, r.text
    login_as(client, "second-admin", "second-pass-123")
    assert client.get("/api/v1/users").status_code == 200


def test_duplicate_username_is_409(client: TestClient) -> None:
    login(client)
    create_viewer(client)
    r = client.post(
        "/api/v1/users",
        json={"username": "viewer", "password": VIEWER_PASSWORD, "role": "viewer"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_short_password_is_rejected_with_persian_details(client: TestClient) -> None:
    login(client)
    r = client.post(
        "/api/v1/users",
        json={"username": "shortpass", "password": "123", "role": "viewer"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    messages = [m for msgs in body["error"]["details"].values() for m in msgs]
    assert any("گذرواژه" in m for m in messages)


def test_delete_user_removes_account_and_sessions(client: TestClient) -> None:
    login(client)
    created = create_viewer(client)
    user_id = created["id"]

    login_as(client, "viewer", VIEWER_PASSWORD)
    viewer_cookie = client.cookies.get("charsooq_session")
    assert viewer_cookie

    login(client)
    assert client.delete(f"/api/v1/users/{user_id}").status_code == 204
    assert [u["username"] for u in client.get("/api/v1/users").json()] == ["admin"]

    stale = TestClient(client.app)
    stale.cookies.set("charsooq_session", viewer_cookie)
    assert stale.get("/api/v1/auth/me").status_code == 401


def test_admin_cannot_delete_self(client: TestClient) -> None:
    login(client)
    me = client.get("/api/v1/auth/me").json()
    r = client.delete(f"/api/v1/users/{me['id']}")
    assert r.status_code == 409
    assert "خودتان" in r.json()["error"]["message"]
    assert client.get("/api/v1/users").status_code == 200


def test_delete_unknown_user_is_404(client: TestClient) -> None:
    login(client)
    r = client.delete("/api/v1/users/9999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
