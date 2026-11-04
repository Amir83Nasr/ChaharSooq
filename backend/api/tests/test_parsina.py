"""Parsina integration — client contract, sync rules, endpoints (mocked HTTP)."""

import csv
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ParsinaSettings, get_parsina_settings, get_settings
from app.core.database import get_engine
from app.integrations.parsina import (
    ParsinaAuthError,
    ParsinaClient,
    ParsinaNetworkError,
    ParsinaResponseError,
    parse_commodity,
)
from app.models import Product
from app.models.parsina import ParsinaSyncState
from app.repositories import SyncStateRepository
from app.repositories.sync import _acquired_by_us
from app.services.sync import (
    ProductSyncService,
    SyncBusyError,
    SyncNotConfiguredError,
    run_scheduled_sync,
)
from tests.helpers import login

SETTINGS = ParsinaSettings(
    parsina_base_url="http://parsina.test/Api/V1",
    parsina_username="u",
    parsina_password="p",
    parsina_org_id=1,
    parsina_year=1400,
    parsina_timeout_seconds=2,
)


def _goods(*rows: dict[str, Any], total: int | None = None) -> dict[str, Any]:
    return {
        "isSuccess": True,
        "statusCode": "Success",
        "message": None,
        "data": list(rows),
        "total": len(rows) if total is None else total,
    }


def _good(good_id: int, code: str, name: str, sale: Any = 1000, remain: Any = 3) -> dict[str, Any]:
    return {
        "goodId": good_id,
        "goodCode": code,
        "goodName": name,
        "mainGroup": 1,
        "subGroup": 2,
        "mainGroupName": "گروه اصلی",
        "subGroupName": "زیرگروه",
        "countUnit": 7,
        "weight": 1.5,
        "khas": False,
        "salePackPrice": 0,
        "saleBoxPrice": 0,
        "usePrice": 0,
        "discount": 0,
        "extra": 0,
        "numberInBox": 0,
        "numberInPack": 0,
        "buyPrice": 900,
        "salePrice": sale,
        "remain": remain,
        "wareRemain": None,
    }


class FakeParsina:
    """MockTransport handler with token rotation + request log."""

    def __init__(self, goods: list[dict[str, Any]] | dict[str, Any], *, expire_first: bool = False):
        self.goods = goods
        self.expire_first = expire_first
        self.requests: list[httpx.Request] = []
        self.auth_calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/Account"):
            self.auth_calls += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"token-{self.auth_calls}",
                    "expires_in": 28799,
                    "userName": "admin",
                },
            )
        if self.expire_first and request.headers.get("Authorization") == "Bearer token-1":
            return httpx.Response(401, json={"isSuccess": False, "message": "expired"})
        if request.url.path.endswith("/UnitCount/BaseInfo"):
            return httpx.Response(
                200,
                json={"isSuccess": True, "data": [{"id": 7, "Title": "عدد"}], "total": 1},
            )
        if "LoadByFilter" in request.url.path:
            return httpx.Response(200, json=self.goods)
        return httpx.Response(200, json=self.goods)


def _service(session: Session, fake: FakeParsina) -> ProductSyncService:
    return ProductSyncService(session, settings=SETTINGS, transport=httpx.MockTransport(fake))


@pytest.fixture()
def session(client: TestClient) -> Iterator[Session]:
    """Depends on `client` so the in-memory schema exists before use."""
    with Session(get_engine()) as s:
        yield s


# ── CLIENT ───────────────────────────────────────────────────


def test_client_sends_bearer_and_parses_envelope() -> None:
    fake = FakeParsina(_goods(_good(1, "A-1", "کالا")))
    with ParsinaClient(SETTINGS, transport=httpx.MockTransport(fake)) as client:
        rows, total = client.commodities()
    assert total == 1
    assert rows[0]["goodId"] == 1
    assert fake.auth_calls == 1
    assert fake.requests[-1].headers["Authorization"] == "Bearer token-1"


def test_client_refreshes_token_once_on_401() -> None:
    fake = FakeParsina(_goods(_good(1, "A-1", "کالا")), expire_first=True)
    with ParsinaClient(SETTINGS, transport=httpx.MockTransport(fake)) as client:
        rows, _ = client.commodities()
    assert rows[0]["goodId"] == 1
    assert fake.auth_calls == 2


def test_client_rejects_failed_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Account"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 100})
        return httpx.Response(200, json={"isSuccess": False, "message": "خطا"})

    with ParsinaClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ParsinaResponseError):
            client.commodities()


def test_client_maps_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with ParsinaClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ParsinaNetworkError):
            client.commodities()


def test_client_refuses_unconfigured_settings() -> None:
    with pytest.raises(ParsinaAuthError):
        ParsinaClient(ParsinaSettings())


def test_parse_commodity_requires_stable_identity() -> None:
    assert parse_commodity({}) is None
    assert parse_commodity({"goodId": 0, "goodName": "x"}) is None
    assert parse_commodity({"goodId": 5}) is None
    row = parse_commodity(_good(5, "K-5", "کالا"))
    assert row is not None
    assert row.good_id == 5
    assert row.sale_price == Decimal("1000")
    assert row.good_code == "K-5"


# ── SYNC ─────────────────────────────────────────────────────


def test_sync_inserts_then_updates_without_duplicates(session: Session) -> None:
    fake = FakeParsina(_goods(_good(1, "A-1", "کالا یک"), _good(2, "A-2", "کالا دو")))
    first = _service(session, fake).run()
    assert (first.created, first.updated, first.processed) == (2, 0, 2)
    second = _service(session, fake).run()
    assert (second.created, second.updated, second.processed) == (0, 2, 2)
    products = session.execute(select(Product)).scalars().all()
    assert len(products) == 2
    assert {p.external_id for p in products} == {1, 2}
    assert products[0].unit_name in {"عدد", None}
    assert all(p.synced_at is not None for p in products)


def test_sync_rejects_short_listing_and_keeps_previous_data(session: Session) -> None:
    good = _good(1, "A-1", "کالا")
    _service(session, FakeParsina(_goods(good))).run()
    broken = FakeParsina(_goods(good, total=5))
    with pytest.raises(ParsinaResponseError):
        _service(session, broken).run()
    products = session.execute(select(Product)).scalars().all()
    assert len(products) == 1 and products[0].is_active
    state = SyncStateRepository(session).get()
    assert state.last_success_at is not None
    assert state.last_error is not None


def test_sync_rejects_payload_without_valid_ids(session: Session) -> None:
    fake = FakeParsina(_goods({"goodName": "بدون شناسه"}, {"goodId": 0, "goodName": "صفر"}))
    with pytest.raises(ParsinaResponseError):
        _service(session, fake).run()
    assert session.execute(select(Product)).scalars().all() == []


def test_sync_deactivates_rows_missing_from_listing(session: Session) -> None:
    _service(session, FakeParsina(_goods(_good(1, "A-1", "یک"), _good(2, "A-2", "دو")))).run()
    result = _service(session, FakeParsina(_goods(_good(1, "A-1", "یک")))).run()
    assert result.deactivated == 1
    session.expire_all()
    rows = {p.external_id: p for p in session.execute(select(Product)).scalars()}
    assert rows[1] is not None and rows[1].is_active
    assert rows[2] is not None and not rows[2].is_active


def test_sync_source_wins_over_manual_sku_collision(session: Session) -> None:
    """Exact mirror: the source row is created and the manual row is deactivated."""
    session.add(Product(name="دستی", sku="A-1", price=Decimal(1), stock=Decimal(1)))
    session.commit()
    result = _service(session, FakeParsina(_goods(_good(1, "A-1", "از پارسینا")))).run()
    assert result.skipped == 0
    assert result.created == 1
    assert result.deactivated == 1
    session.expire_all()
    rows = session.execute(select(Product)).scalars().all()
    assert len(rows) == 2
    by_external = {p.external_id: p for p in rows}
    assert by_external[1].is_active
    assert by_external[1].name == "از پارسینا"
    assert by_external[None] is not None and not by_external[None].is_active


def test_sync_deactivates_manual_rows_missing_from_listing(session: Session) -> None:
    """Manual rows are part of the mirror: absent = deactivated."""
    session.add(Product(name="دستی", sku="MANUAL-1", price=Decimal(1), stock=Decimal(1)))
    session.commit()
    result = _service(session, FakeParsina(_goods(_good(1, "A-1", "از پارسینا")))).run()
    assert result.deactivated == 1
    session.expire_all()
    rows = {p.sku: p for p in session.execute(select(Product)).scalars()}
    assert rows["A-1"].is_active
    assert not rows["MANUAL-1"].is_active


def test_sync_lock_guard_and_acquired_run(session: Session) -> None:
    service = _service(session, FakeParsina(_goods(_good(1, "A-1", "کالا"))))
    service.acquire()
    assert SyncStateRepository(session).get().running_since is not None
    with pytest.raises(SyncBusyError):
        # A second worker cannot take the lock while the first holds it.
        _service(session, FakeParsina(_goods(_good(1, "A-1", "کالا")))).acquire()
    assert service.run_acquired().created == 1
    assert SyncStateRepository(session).get().running_since is None


def test_sync_fails_without_settings(session: Session) -> None:
    with pytest.raises(SyncNotConfiguredError):
        ProductSyncService(session, settings=ParsinaSettings()).run()


def test_acquired_by_us_tolerates_naive_datetimes() -> None:
    """SQLite returns tz-naive datetimes; the lock holder must still match."""
    now = datetime.now(UTC)
    assert _acquired_by_us(None, now) is False
    assert _acquired_by_us(ParsinaSyncState(id=1, running_since=None), now) is False
    assert (
        _acquired_by_us(ParsinaSyncState(id=1, running_since=now.replace(tzinfo=None)), now) is True
    )
    other = datetime.now(UTC).replace(year=datetime.now(UTC).year + 1)
    assert _acquired_by_us(ParsinaSyncState(id=1, running_since=other), now) is False


def test_scheduled_sync_noop_when_not_configured() -> None:
    fake = FakeParsina(_goods(_good(1, "A-1", "کالا")))
    result = run_scheduled_sync(
        session_factory=lambda: Session(get_engine()),
        interval_minutes=15,
        transport=httpx.MockTransport(fake),
    )
    assert result is None  # test env never ticks; no Parsina credentials either
    assert fake.auth_calls == 0


@pytest.fixture()
def dev_csv_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Pretend to be the dev process: APP_ENV=development + a tiny CSV fixture."""
    path = tmp_path / "parsina.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["goodId", "goodCode", "goodName"])
        writer.writerow(["1", "A-1", "کالا یک"])
        writer.writerow(["2", "A-2", "کالا دو"])
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PRODUCTS_CSV_PATH", str(path))
    get_settings.cache_clear()
    get_parsina_settings.cache_clear()
    yield path
    get_settings.cache_clear()
    get_parsina_settings.cache_clear()


def test_scheduled_sync_runs_csv_and_respects_interval(session: Session, dev_csv_env: Path) -> None:
    assert dev_csv_env.is_file()
    first = run_scheduled_sync(
        session_factory=lambda: Session(get_engine()),
        interval_minutes=60,
    )
    assert first is not None
    assert (first.created, first.updated, first.processed) == (2, 0, 2)
    assert {p.external_id for p in session.execute(select(Product)).scalars()} == {1, 2}
    assert (
        run_scheduled_sync(session_factory=lambda: Session(get_engine()), interval_minutes=60)
        is None
    )


# ── ENDPOINTS ────────────────────────────────────────────────


def test_sync_endpoints_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/integrations/parsina/status").status_code == 401
    assert client.post("/api/v1/integrations/parsina/sync").status_code == 401


def test_sync_status_reports_unconfigured(client: TestClient) -> None:
    login(client)
    body = client.get("/api/v1/integrations/parsina/status").json()
    assert body["configured"] is False
    assert body["running"] is False
    assert body["interval_minutes"] == 60


def test_sync_endpoint_reports_missing_configuration(client: TestClient) -> None:
    login(client)
    r = client.post("/api/v1/integrations/parsina/sync")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "error"


def test_sync_endpoint_returns_409_while_another_run_holds_lock(client: TestClient) -> None:
    login(client)
    with Session(get_engine()) as s:
        state = SyncStateRepository(s).get()
        state.lock_until = datetime.now(UTC).replace(year=datetime.now(UTC).year + 1)
        state.running_since = datetime.now(UTC)
        s.commit()
    r = client.post("/api/v1/integrations/parsina/sync")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"
    body = client.get("/api/v1/integrations/parsina/status").json()
    assert body["running"] is True
    assert body["running_since"] is not None


def test_products_endpoint_exposes_parsina_fields_and_groups(client: TestClient) -> None:
    login(client)
    session = Session(get_engine())
    fake = FakeParsina(_goods(_good(1, "A-1", "کالا")))
    _service(session, fake).run()
    session.close()
    page = client.get("/api/v1/products", params={"q": "کالا"}).json()
    assert page["total"] == 1
    item = page["items"][0]
    assert item["external_id"] == 1
    assert item["main_group_name"] == "گروه اصلی"
    assert client.get("/api/v1/products", params={"main_group": "گروه اصلی"}).json()["total"] == 1
    assert client.get("/api/v1/products/groups").json() == ["گروه اصلی"]


def test_inactive_products_are_hidden(client: TestClient) -> None:
    login(client)
    session = Session(get_engine())
    _service(session, FakeParsina(_goods(_good(1, "A-1", "یک"), _good(2, "A-2", "دو")))).run()
    _service(session, FakeParsina(_goods(_good(1, "A-1", "یک")))).run()
    session.close()
    page = client.get("/api/v1/products").json()
    assert page["total"] == 1
    assert page["items"][0]["external_id"] == 1
