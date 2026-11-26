"""Parsina base-URL handling, typed config errors, and failure reporting.

A malformed address must never look like "Parsina is unreachable": it is a
settings problem, reported as such, and it must not be retried as if transient.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import ParsinaSettings
from app.core.database import get_engine
from app.integrations.parsina import (
    ParsinaClient,
    ParsinaConfigError,
    _transport_reason,
    normalize_base_url,
)
from app.repositories import SyncStateRepository
from app.services.parsina_connection import (
    ParsinaConnectionConfigError,
    update_parsina_connection,
)
from app.services.sync import ProductSyncService
from tests.helpers import login_owner


def _settings(base_url: str) -> ParsinaSettings:
    return ParsinaSettings(
        parsina_base_url=base_url,
        parsina_username="user",
        parsina_password="pass",
        parsina_org_id=1,
        parsina_year=1405,
        parsina_timeout_seconds=2,
    )


@pytest.fixture()
def session(client: TestClient) -> Iterator[Session]:
    """Depends on `client` so the in-memory schema exists before use."""
    with Session(get_engine()) as s:
        yield s


# ── NORMALIZATION ────────────────────────────────────────────


def test_normalize_adds_missing_http_scheme() -> None:
    assert normalize_base_url("172.30.1.2/Api/V1") == "http://172.30.1.2/Api/V1"


def test_normalize_keeps_scheme_host_port_and_trims_path() -> None:
    assert (
        normalize_base_url(" HTTPS://Parsina.local:8443/Api/V1/ ")
        == "https://Parsina.local:8443/Api/V1"
    )


def test_normalize_empty_value_is_allowed() -> None:
    # Empty means "fall back to env/secrets"; it is not a validation failure.
    assert normalize_base_url("   ") == ""


@pytest.mark.parametrize(
    "raw",
    [
        "ftp://172.30.1.2/Api/V1",
        "http://172.30.1.2:abc/Api/V1",
        "http://",
        "172.30.1.2 /Api/V1",
        "http://172.30.1.2:0/Api/V1",
        "http:/172.30.1.2/Api/V1",
    ],
)
def test_normalize_rejects_unusable_values(raw: str) -> None:
    with pytest.raises(ParsinaConfigError):
        normalize_base_url(raw)


# ── CLIENT ───────────────────────────────────────────────────


def test_client_uses_the_normalized_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path.endswith("/Account"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(200, json={"isSuccess": True, "total": 0, "data": []})

    settings = _settings("172.30.1.2/Api/V1")
    with ParsinaClient(settings, transport=httpx.MockTransport(handler)) as client:
        client.commodities()
    assert seen == [
        "http://172.30.1.2/Api/V1/Account",
        "http://172.30.1.2/Api/V1/Commodity",
    ]


def test_client_rejects_bad_base_url_before_the_network() -> None:
    with pytest.raises(ParsinaConfigError):
        ParsinaClient(_settings("http://172.30.1.2:abc/Api/V1"))


def test_client_does_not_retry_configuration_protocol_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.integrations.parsina.TRANSIENT_REQUEST_BACKOFF_SECONDS", 0)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.UnsupportedProtocol("unsupported", request=request)

    settings = _settings("http://parsina.test/Api/V1")
    with ParsinaClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ParsinaConfigError):
            client.commodities()
    # Deterministic settings bug: one attempt, never the transient retry loop.
    assert calls["count"] == 1


def test_transport_reason_distinguishes_dns_refused_tls_and_fallback() -> None:
    dns = httpx.ConnectError("dns")
    dns.__cause__ = socket.gaierror(8, "nodename nor servname provided")
    assert _transport_reason(dns) == "نام میزبان پارسینا پیدا نشد"

    refused = httpx.ConnectError("refused")
    refused.__cause__ = ConnectionRefusedError(111, "Connection refused")
    assert _transport_reason(refused) == "اتصال به پارسینا رد شد"

    tls = httpx.ConnectError("tls")
    tls.__cause__ = ssl.SSLError("bad certificate")
    assert _transport_reason(tls) == "خطای امنیتی TLS در اتصال به پارسینا"

    assert _transport_reason(httpx.ConnectError("other")) == "ارتباط با پارسینا برقرار نشد"
    assert _transport_reason(httpx.ReadTimeout("slow")) == "پاسخی از پارسینا دریافت نشد (timeout)"


# ── SAVE PATH ────────────────────────────────────────────────


def test_save_normalizes_the_base_url(client: TestClient, session: Session) -> None:
    login_owner(client)
    response = client.put(
        "/api/v1/integrations/parsina/connection",
        json={
            "base_url": "172.30.1.2/Api/V1/",
            "username": "user",
            "org_id": 1,
            "fiscal_year": 1405,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["base_url"] == "http://172.30.1.2/Api/V1"
    assert SyncStateRepository(session).get().base_url == "http://172.30.1.2/Api/V1"


def test_save_rejects_a_malformed_base_url_without_overwriting(
    client: TestClient, session: Session
) -> None:
    login_owner(client)
    client.put(
        "/api/v1/integrations/parsina/connection",
        json={"base_url": "http://172.30.1.2/Api/V1"},
    )
    response = client.put(
        "/api/v1/integrations/parsina/connection",
        json={"base_url": "http://172.30.1.2:abc/Api/V1"},
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert "آدرس سرور پارسینا" in body["message"]
    assert SyncStateRepository(session).get().base_url == "http://172.30.1.2/Api/V1"


def test_update_service_raises_the_typed_error(session: Session) -> None:
    with pytest.raises(ParsinaConnectionConfigError):
        update_parsina_connection(session, base_url="http://172.30.1.2:abc/Api/V1")


# ── SYNC REPORTING ───────────────────────────────────────────


def test_failed_sync_reports_a_configuration_error(session: Session) -> None:
    service = ProductSyncService(session, settings=_settings("http://172.30.1.2:abc/Api/V1"))
    with pytest.raises(ParsinaConfigError):
        service.run()
    state = service.state()
    assert state.last_error is not None
    assert state.last_error.startswith("خطای تنظیمات پارسینا:")
    assert state.last_success_at is None
    # The lock must be released so the button is usable again immediately.
    assert state.lock_until is None


# ── LOCK HYGIENE ─────────────────────────────────────────────


def test_sync_releases_the_lock_when_status_bookkeeping_fails(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Account"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        if request.url.path.endswith("/UnitCount"):
            return httpx.Response(200, json={"isSuccess": True, "data": []})
        return httpx.Response(
            200,
            json={
                "isSuccess": True,
                "total": 1,
                "data": [
                    {
                        "goodId": 1,
                        "goodCode": "A-1",
                        "goodName": "کالا",
                        "salePrice": 1000,
                    }
                ],
            },
        )

    def boom(self: SyncStateRepository, **_kwargs: object) -> None:
        raise RuntimeError("bookkeeping down")

    monkeypatch.setattr(SyncStateRepository, "record_result", boom)
    service = ProductSyncService(
        session,
        settings=_settings("http://parsina.test/Api/V1"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RuntimeError):
        service.run()
    # The products committed, so the run must not keep the 30-minute lock.
    assert SyncStateRepository(session).get().lock_until is None
