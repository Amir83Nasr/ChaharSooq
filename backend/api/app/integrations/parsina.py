"""Parsina HTTP client — auth, envelope parsing, typed transport errors.

Contract (docs/parsina-api.pdf):
  POST {base}/Account                      {username, password, org, year} → access_token
  GET  {base}/Commodity                    list of goods
  GET  {base}/commodity/LoadByFilter?Ware&Saletype&Id
  GET  {base}/BaseInfo/UnitCount           counting units (legacy alias below)
  GET  {base}/SaleFactor?fromDate&toDate   sales invoices (Jalali date range)
  GET  {base}/SaleFactor/{id}              sales invoice with Details[]
  GET  {base}/buyFactor?fromDate&toDate    purchase invoices (Jalali date range)
  GET  {base}/BuyFactor/{id}               purchase invoice with Details[]
Every envelope: {isSuccess, statusCode, message, data, total}.
"""

from __future__ import annotations

import logging
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import urlsplit

import httpx

from app.core.config import ParsinaSettings

log = logging.getLogger("charsooq.parsina")

# Refresh a little before the documented 2h lifetime; API stays the authority
# (a 401 forces an immediate refresh and one retry).
TOKEN_REFRESH_MARGIN_SECONDS = 300
TOKEN_FALLBACK_TTL_SECONDS = 2 * 60 * 60
TRANSIENT_REQUEST_ATTEMPTS = 3
TRANSIENT_REQUEST_BACKOFF_SECONDS = 0.5
# The live export saves this endpoint as `/BaseInfo/UnitCount`; older Parsina
# builds answer `/UnitCount/BaseInfo`. Both return the same Id/Title envelope.
UNIT_PATHS = ("/BaseInfo/UnitCount", "/UnitCount/BaseInfo")


class ParsinaError(Exception):
    """Base class — transport, auth and contract failures stay distinguishable."""


class ParsinaAuthError(ParsinaError):
    pass


class ParsinaNetworkError(ParsinaError):
    pass


class ParsinaResponseError(ParsinaError):
    """Envelope reported failure, non-JSON body, or a contract violation."""


class ParsinaConfigError(ParsinaError):
    """The configured base URL cannot form a valid Parsina request.

    Kept separate from `ParsinaNetworkError`: a malformed address is a settings
    problem, not a reachability problem, and must not be reported as offline.
    """


_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
# How deep to walk wrapper exceptions (httpx -> httpcore -> OSError).
_CAUSE_DEPTH = 5


def normalize_base_url(raw: str) -> str:
    """Return a usable Parsina base URL; raise `ParsinaConfigError` otherwise.

    The contract's BaseUrl is `http://ip:port/Api/V1`. Owners routinely paste a
    scheme-less address; that used to reach httpx, fail as a transport error and
    surface as the misleading «ارتباط با پارسینا برقرار نشد». A missing scheme
    now means HTTP — the only transport the Parsina contract documents — and
    everything else (scheme, host, port, whitespace) is validated up front.
    """
    value = (raw or "").strip()
    if not value:
        return ""
    if any(char.isspace() for char in value):
        raise ParsinaConfigError("آدرس سرور پارسینا نباید فاصله داشته باشد")
    if value.lower().startswith(("http:", "https:")) and not _SCHEME_RE.match(value):
        raise ParsinaConfigError("آدرس سرور پارسینا باید به شکل http:// یا https:// باشد")
    if not _SCHEME_RE.match(value):
        value = f"http://{value}"
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ParsinaConfigError("آدرس سرور پارسینا معتبر نیست (پورت نامعتبر)") from exc
    if parts.scheme.lower() not in {"http", "https"}:
        raise ParsinaConfigError("آدرس سرور پارسینا باید با http:// یا https:// شروع شود")
    if not parts.hostname:
        raise ParsinaConfigError("آدرس سرور پارسینا باید نام میزبان داشته باشد")
    if port == 0:
        raise ParsinaConfigError("آدرس سرور پارسینا معتبر نیست (پورت نامعتبر)")
    normalized = f"{parts.scheme.lower()}://{parts.netloc}{parts.path.rstrip('/')}"
    if parts.query:
        normalized = f"{normalized}?{parts.query}"
    return normalized


def _transport_reason(exc: httpx.HTTPError) -> str:
    """Classify one transport failure just enough to act on it in Persian.

    The generic «ارتباط برقرار نشد» made production incidents indistinguishable
    from a bad settings value. DNS, refused, TLS and timeout now read
    differently; anything unrecognized keeps the original wording.
    """
    if isinstance(exc, httpx.TimeoutException):
        return "پاسخی از پارسینا دریافت نشد (timeout)"
    cause: BaseException | None = exc
    for _ in range(_CAUSE_DEPTH):
        nested = cause.__cause__ or cause.__context__
        if nested is None:
            break
        cause = nested
        if isinstance(cause, socket.gaierror):
            return "نام میزبان پارسینا پیدا نشد"
        if isinstance(cause, ConnectionRefusedError):
            return "اتصال به پارسینا رد شد"
        if isinstance(cause, ssl.SSLError):
            return "خطای امنیتی TLS در اتصال به پارسینا"
    return "ارتباط با پارسینا برقرار نشد"


@dataclass(frozen=True)
class CommodityRow:
    """One raw Parsina catalog row. Every price field here is RIAL, not Toman.

    `parse_commodity` deliberately does not convert: `ProductSyncService` is the
    single rial → toman boundary. `discount`/`extra` are percentages, not money.
    """

    good_id: int
    good_code: str
    good_name: str
    main_group: int | None
    sub_group: int | None
    main_group_name: str | None
    sub_group_name: str | None
    count_unit: int | None
    weight: Decimal | None
    is_special: bool
    sale_pack_price: Decimal | None
    sale_box_price: Decimal | None
    use_price: Decimal | None
    discount: Decimal | None
    extra: Decimal | None
    number_in_box: Decimal | None
    number_in_pack: Decimal | None
    buy_price: Decimal | None
    sale_price: Decimal | None
    remain: Decimal | None
    ware_remain: Decimal | None


def _decimal(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def integer(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _str(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def field(record: dict[str, Any], *names: str) -> Any:
    """Case-insensitive field lookup.

    Parsina serializes some payloads with PascalCase (`Title`, `Id`) and others
    with camelCase (`goodId`); the counting-units endpoint disagrees with the
    rest of the catalog, so match names regardless of case.
    """
    wanted = {name.lower() for name in names}
    for key, value in record.items():
        if str(key).strip().lower() in wanted:
            return value
    return None


def unit_titles_from_rows(rows: Any) -> dict[int, str]:
    """Map Parsina count-unit ids to titles — shared by live API and dev fixture.

    The units endpoint uses PascalCase (`Id`, `Title`) while the catalog uses
    camelCase (`countUnit`); some builds mix the two, so lookup is case-blind.
    Unusable rows are skipped: a failed/missing title never aborts a sync.
    """
    out: dict[int, str] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = cast("dict[str, Any]", raw)
        unit_id = integer(field(row, "id", "unitId", "unit_id", "unitCode", "code"))
        title = _str(field(row, "Title", "title", "unitName", "unit_name", "name"))
        if unit_id is not None and title:
            out[unit_id] = title
    return out


def _as_bool(raw: Any) -> bool:
    """JSON sends real booleans; the dev CSV sends "true"/"false" strings."""
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    return str(raw).strip().lower() in {"true", "1", "yes", "y", "بله"}


def parse_commodity(raw: Any) -> CommodityRow | None:
    """Return None when the record has no usable stable identity."""
    if not isinstance(raw, dict):
        return None
    record = cast("dict[str, Any]", raw)
    good_id = integer(record.get("goodId"))
    good_name = _str(record.get("goodName"))
    if good_id is None or good_id <= 0 or good_name is None:
        return None
    return CommodityRow(
        good_id=good_id,
        good_code=_str(record.get("goodCode")) or str(good_id),
        good_name=good_name,
        main_group=integer(record.get("mainGroup")),
        sub_group=integer(record.get("subGroup")),
        main_group_name=_str(record.get("mainGroupName")),
        sub_group_name=_str(record.get("subGroupName")),
        count_unit=integer(record.get("countUnit")),
        weight=_decimal(record.get("weight")),
        is_special=_as_bool(record.get("khas")),
        sale_pack_price=_decimal(record.get("salePackPrice")),
        sale_box_price=_decimal(record.get("saleBoxPrice")),
        use_price=_decimal(record.get("usePrice")),
        discount=_decimal(record.get("discount")),
        extra=_decimal(record.get("extra")),
        number_in_box=_decimal(record.get("numberInBox")),
        number_in_pack=_decimal(record.get("numberInPack")),
        buy_price=_decimal(record.get("buyPrice")),
        sale_price=_decimal(record.get("salePrice")),
        remain=_decimal(record.get("remain")),
        ware_remain=_decimal(record.get("wareRemain")),
    )


class ParsinaClient:
    """Thread-safe token holder; one instance per sync run is cheap enough."""

    def __init__(
        self,
        settings: ParsinaSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not settings.is_configured:
            raise ParsinaAuthError("اتصال پارسینا تنظیم نشده است")
        # Validate/normalize before httpx sees the value: a scheme-less address
        # must read as a settings error, not as "Parsina is unreachable".
        base_url = normalize_base_url(settings.parsina_base_url)
        if not base_url:
            raise ParsinaAuthError("اتصال پارسینا تنظیم نشده است")
        self._settings = settings
        try:
            self._http = httpx.Client(
                base_url=base_url,
                timeout=httpx.Timeout(settings.parsina_timeout_seconds),
                transport=transport,
            )
        except (httpx.InvalidURL, ValueError) as exc:
            raise ParsinaConfigError("آدرس سرور پارسینا معتبر نیست") from exc
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at = 0.0

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ParsinaClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── AUTH ─────────────────────────────────────────────────

    def _fetch_token(self) -> str:
        settings = self._settings
        payload = {
            "username": settings.parsina_username,
            "password": settings.parsina_password,
            "org": settings.parsina_org_id,
            "year": settings.parsina_year,
        }
        body = self._envelope(self._request("POST", "/Account", json=payload, auth=False))
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise ParsinaAuthError("پاسخ احراز هویت پارسینا توکن معتبر ندارد")
        expires_in = integer(body.get("expires_in"))
        ttl = float(expires_in) if expires_in and expires_in > 0 else TOKEN_FALLBACK_TTL_SECONDS
        self._token = token
        self._token_expires_at = time.monotonic() + max(ttl - TOKEN_REFRESH_MARGIN_SECONDS, 60)
        return token

    def _token_or_refresh(self) -> str:
        with self._lock:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                return self._fetch_token()
            return self._token

    def _invalidate_token(self) -> None:
        with self._lock:
            self._token = None
            self._token_expires_at = 0.0

    # ── TRANSPORT ────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        auth: bool = True,
        _retry: bool = True,
        _network_attempt: int = 1,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._token_or_refresh()}"
        try:
            response = self._http.request(method, path, params=params, json=json, headers=headers)
        except (httpx.UnsupportedProtocol, httpx.InvalidURL) as exc:
            # Deterministic settings bugs, not transient network failures.
            raise ParsinaConfigError("آدرس سرور پارسینا معتبر نیست") from exc
        except httpx.TimeoutException as exc:
            if _network_attempt < TRANSIENT_REQUEST_ATTEMPTS:
                time.sleep(TRANSIENT_REQUEST_BACKOFF_SECONDS * _network_attempt)
                return self._request(
                    method,
                    path,
                    params=params,
                    json=json,
                    auth=auth,
                    _retry=_retry,
                    _network_attempt=_network_attempt + 1,
                )
            raise ParsinaNetworkError(_transport_reason(exc)) from exc
        except httpx.HTTPError as exc:
            if _network_attempt < TRANSIENT_REQUEST_ATTEMPTS:
                time.sleep(TRANSIENT_REQUEST_BACKOFF_SECONDS * _network_attempt)
                return self._request(
                    method,
                    path,
                    params=params,
                    json=json,
                    auth=auth,
                    _retry=_retry,
                    _network_attempt=_network_attempt + 1,
                )
            raise ParsinaNetworkError(_transport_reason(exc)) from exc

        if response.status_code == 401:
            # Token might have been revoked before its advertised lifetime.
            if auth and _retry:
                self._invalidate_token()
                return self._request(
                    method, path, params=params, json=json, auth=auth, _retry=False
                )
            raise ParsinaAuthError("دسترسی پارسینا رد شد")

        try:
            body = response.json()
        except ValueError as exc:
            raise ParsinaResponseError(
                f"پاسخ پارسینا JSON معتبر نیست (HTTP {response.status_code})"
            ) from exc
        if not isinstance(body, dict):
            raise ParsinaResponseError("ساختار پاسخ پارسینا نامعتبر است")
        envelope = cast("dict[str, Any]", body)
        if response.status_code >= 400:
            raise ParsinaResponseError(
                f"خطای پارسینا (HTTP {response.status_code}): "
                f"{envelope.get('message') or 'بدون پیام'}"
            )
        return envelope

    @staticmethod
    def _envelope(body: Any) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise ParsinaResponseError("ساختار پاسخ پارسینا نامعتبر است")
        data = cast("dict[str, Any]", body)
        if data.get("isSuccess") is False:
            raise ParsinaResponseError(f"پارسینا درخواست را رد کرد: {data.get('message') or '-'}")
        return data

    def _data_list(self, body: Any) -> list[Any]:
        data = self._envelope(body).get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise ParsinaResponseError("فیلد data در پاسخ پارسینا لیست نیست")
        rows = cast("list[Any]", data)
        return rows

    # ── ENDPOINTS ────────────────────────────────────────────

    def invoices(
        self,
        *,
        kind: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Raw invoice rows for a Jalali date range.

        Parsina accepts `fromDate`/`toDate` as Jalali strings (e.g. ۱۴۰۴/۰۱/۰۱
        written with Latin digits: `1404/01/01`). The list endpoint does not
        include product lines, so the caller loads details per invoice.
        """
        path = "/SaleFactor" if kind == "sale" else "/buyFactor"
        params = {"fromDate": from_date, "toDate": to_date}
        rows: list[Any] = self._data_list(self._request("GET", path, params=params))
        return [row for row in rows if isinstance(row, dict)]

    def invoice_details(self, *, kind: str, invoice_id: int) -> list[dict[str, Any]]:
        """Product lines of one invoice (`Details[]` in the Parsina contract)."""
        base = "/SaleFactor" if kind == "sale" else "/BuyFactor"
        body = self._envelope(self._request("GET", f"{base}/{invoice_id}"))
        data = body.get("data")
        if not isinstance(data, dict):
            return []
        details: Any = field(cast("dict[str, Any]", data), "Details")
        if not isinstance(details, list):
            return []
        return [cast("dict[str, Any]", row) for row in details if isinstance(row, dict)]

    def commodities(self) -> tuple[list[Any], int | None]:
        """Raw rows + reported total.

        `LoadByFilter` only when a warehouse/sale type is configured.
        """
        settings = self._settings
        if settings.parsina_ware_id is not None or settings.parsina_sale_type_id is not None:
            params = {
                "Ware": settings.parsina_ware_id,
                "Saletype": settings.parsina_sale_type_id,
            }
            body = self._request("GET", "/commodity/LoadByFilter", params=params)
        else:
            body = self._request("GET", "/Commodity")
        total = integer(self._envelope(body).get("total"))
        return self._data_list(body), total

    def units(self) -> dict[int, str]:
        """Best-effort countUnit id → title map; a failure never aborts a sync.

        The catalog only carries `countUnit` (an id); the display name comes
        from the counting-units endpoint, whose rows are matched here by id so
        the products table shows «عدد» instead of `8`. Dev reads the same rows
        from `units.json` through `unit_titles_from_rows`, so both paths agree.
        """
        for path in UNIT_PATHS:
            try:
                rows = self._unit_rows(self._request("GET", path))
            except ParsinaError:
                # Do not log request/URL details; credentials live in auth payloads.
                continue
            titles = unit_titles_from_rows(rows)
            if titles:
                return titles
        log.warning("parsina units lookup returned no usable rows")
        return {}

    def _unit_rows(self, body: Any) -> list[Any]:
        """Rows of the units envelope; some builds wrap the list in a dict."""
        data = self._envelope(body).get("data")
        if isinstance(data, list):
            return cast("list[Any]", data)
        if isinstance(data, dict):
            wrapped = cast("dict[str, Any]", data)
            for value in wrapped.values():
                if isinstance(value, list):
                    return cast("list[Any]", value)
            return [wrapped]
        if data is None:
            return []
        raise ParsinaResponseError("فیلد data در پاسخ واحدهای شمارش پارسینا نامعتبر است")
