"""Role-based access + owner/admin user management."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.core.security import hash_password
from app.models import Admin
from app.models.auth import ROLE_OWNER
from tests.helpers import login, login_as, login_owner

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


def user_id(username: str) -> int:
    with Session(get_engine()) as session:
        return session.query(Admin).filter_by(username=username).one().id


def test_admin_lists_viewers_and_self(client: TestClient) -> None:
    login(client)
    create_viewer(client)
    r = client.get("/api/v1/users")
    assert r.status_code == 200
    # The admin sees their own row plus viewers; the owner and other admins
    # stay hidden.
    assert [user["username"] for user in r.json()] == ["admin", "viewer"]


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

    # Writes and account management require a management role.
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


def test_admin_cannot_create_admin(client: TestClient) -> None:
    login(client)
    r = client.post(
        "/api/v1/users",
        json={"username": "second-admin", "password": "second-pass-123", "role": "admin"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_owner_lists_every_account_and_creates_admins(client: TestClient) -> None:
    login_owner(client)
    assert [user["username"] for user in client.get("/api/v1/users").json()] == [
        "root",
        "admin",
    ]
    r = client.post(
        "/api/v1/users",
        json={"username": "second-admin", "password": "second-pass-123", "role": "admin"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "admin"

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
    user_id_value = created["id"]

    login_as(client, "viewer", VIEWER_PASSWORD)
    viewer_cookie = client.cookies.get("charsooq_session")
    assert viewer_cookie

    login(client)
    assert client.delete(f"/api/v1/users/{user_id_value}").status_code == 204
    assert [user["username"] for user in client.get("/api/v1/users").json()] == ["admin"]

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


def test_admin_cannot_delete_higher_roles(client: TestClient) -> None:
    login(client)
    # Hidden accounts answer 404 so admin usernames never leak to an admin.
    assert client.delete(f"/api/v1/users/{user_id('root')}").status_code == 404
    assert client.delete(f"/api/v1/users/{user_id('admin')}").status_code == 409


def test_owner_deletes_another_admin(client: TestClient) -> None:
    login_owner(client)
    r = client.post(
        "/api/v1/users",
        json={"username": "second-admin", "password": "second-pass-123", "role": "admin"},
    )
    assert r.status_code == 201, r.text
    second_id = r.json()["id"]
    assert client.delete(f"/api/v1/users/{second_id}").status_code == 204
    assert [user["username"] for user in client.get("/api/v1/users").json()] == [
        "root",
        "admin",
    ]


def test_owner_account_cannot_be_deleted(client: TestClient) -> None:
    with Session(get_engine()) as session:
        session.add(
            Admin(
                username="root2",
                password_hash=hash_password(VIEWER_PASSWORD),
                role=ROLE_OWNER,
            )
        )
        session.commit()
    login_owner(client)
    r = client.delete(f"/api/v1/users/{user_id('root2')}")
    assert r.status_code == 409
    assert "سوپرادمین" in r.json()["error"]["message"]


def test_owner_deletes_the_last_admin(client: TestClient) -> None:
    # The owner is still a management account, so removing the only admin
    # leaves the panel manageable.
    login_owner(client)
    assert client.delete(f"/api/v1/users/{user_id('admin')}").status_code == 204
    assert [user["username"] for user in client.get("/api/v1/users").json()] == [
        "root",
    ]


def test_delete_unknown_user_is_404(client: TestClient) -> None:
    login(client)
    r = client.delete("/api/v1/users/9999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
