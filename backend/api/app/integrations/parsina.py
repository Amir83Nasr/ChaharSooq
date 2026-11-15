"""Parsina HTTP client — auth, envelope parsing, typed transport errors.

Contract (docs/api/parsina-api.pdf):
  POST {base}/Account                      {username, password, org, year} → access_token
  GET  {base}/Commodity                    list of goods
  GET  {base}/commodity/LoadByFilter?Ware&Saletype&Id
  GET  {base}/UnitCount/BaseInfo           counting units
Every envelope: {isSuccess, statusCode, message, data, total}.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import httpx

from app.core.config import ParsinaSettings

log = logging.getLogger("charsooq.parsina")

# Refresh a little before the documented 2h lifetime; API stays the authority
# (a 401 forces an immediate refresh and one retry).
TOKEN_REFRESH_MARGIN_SECONDS = 300
TOKEN_FALLBACK_TTL_SECONDS = 2 * 60 * 60
TRANSIENT_REQUEST_ATTEMPTS = 3
TRANSIENT_REQUEST_BACKOFF_SECONDS = 0.5


class ParsinaError(Exception):
    """Base class — transport, auth and contract failures stay distinguishable."""


class ParsinaAuthError(ParsinaError):
    pass


class ParsinaNetworkError(ParsinaError):
    pass


class ParsinaResponseError(ParsinaError):
    """Envelope reported failure, non-JSON body, or a contract violation."""


@dataclass(frozen=True)
class CommodityRow:
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


def _int(raw: Any) -> int | None:
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


def _field(record: dict[str, Any], *names: str) -> Any:
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
    good_id = _int(record.get("goodId"))
    good_name = _str(record.get("goodName"))
    if good_id is None or good_id <= 0 or good_name is None:
        return None
    return CommodityRow(
        good_id=good_id,
        good_code=_str(record.get("goodCode")) or str(good_id),
        good_name=good_name,
        main_group=_int(record.get("mainGroup")),
        sub_group=_int(record.get("subGroup")),
        main_group_name=_str(record.get("mainGroupName")),
        sub_group_name=_str(record.get("subGroupName")),
        count_unit=_int(record.get("countUnit")),
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
        self._settings = settings
        self._http = httpx.Client(
            base_url=settings.base_url,
            timeout=httpx.Timeout(settings.parsina_timeout_seconds),
            transport=transport,
        )
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
        expires_in = _int(body.get("expires_in"))
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
            raise ParsinaNetworkError("پاسخی از پارسینا دریافت نشد (timeout)") from exc
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
            raise ParsinaNetworkError("ارتباط با پارسینا برقرار نشد") from exc

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
        total = _int(self._envelope(body).get("total"))
        return self._data_list(body), total

    def units(self) -> dict[int, str]:
        """Best-effort countUnit id → title map; a failure never aborts a sync.

        The catalog only carries `countUnit` (an id); the display name comes
        from `GET /UnitCount/BaseInfo`, whose rows are matched here by id so
        the products table can show «عدد» instead of `4`.
        """
        try:
            body = self._request("GET", "/UnitCount/BaseInfo")
            rows = self._unit_rows(body)
        except ParsinaError:
            # Do not log request/URL details; credentials live in auth payloads.
            log.warning("parsina units lookup failed")
            return {}
        out: dict[int, str] = {}
        unexpected_keys: set[str] = set()
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            row = cast("dict[str, Any]", raw)
            unit_id = _int(_field(row, "id", "unitId", "unit_id", "unitCode", "code"))
            title = _str(_field(row, "Title", "title", "unitName", "unit_name", "name"))
            if unit_id is not None and title:
                out[unit_id] = title
            elif title is None:
                unexpected_keys.update(str(key) for key in row)
        if not out:
            # Field names are safe to log; values (and credentials) are not.
            log.warning(
                "parsina units lookup returned no usable rows (keys: %s)",
                ", ".join(sorted(unexpected_keys)) or "-",
            )
        return out

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
