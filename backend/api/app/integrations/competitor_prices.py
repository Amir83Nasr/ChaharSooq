"""Safe, low-rate public product page inspection for supported stores."""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import get_settings

log = logging.getLogger("charsooq.competitors")
USER_AGENT = "CharsooqPriceChecker/1.0 (+admin product price comparison)"
STORE_HOSTS: dict[str, frozenset[str]] = {
    "digikala": frozenset({"digikala.com", "www.digikala.com"}),
    "technolife": frozenset(
        {"technolife.ir", "www.technolife.ir", "technolife.com", "www.technolife.com"}
    ),
}
_lock = threading.Lock()
_robot_cache: dict[str, tuple[float, RobotFileParser]] = {}
_page_cache: dict[str, tuple[float, FetchedPrice]] = {}
_host_last_request: dict[str, float] = {}
_host_blocked_until: dict[str, float] = {}


class PriceFetchError(Exception):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class FetchedPrice:
    amount: Decimal
    currency: str
    in_stock: bool | None
    observed_at: datetime | None = None


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside = False
        self._buffer: list[str] = []
        self.documents: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and (attributes.get("type") or "").lower() == "application/ld+json":
            self._inside = True
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._inside:
            self.documents.append("".join(self._buffer))
            self._inside = False

    def handle_data(self, data: str) -> None:
        if self._inside:
            self._buffer.append(data)


def _normalise_url(url: str, store: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        hostname = parsed.hostname
    except ValueError:
        raise PriceFetchError("failed", "آدرس نامعتبر است") from None
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise PriceFetchError("failed", "آدرس باید با http یا https شروع شود")
    try:
        port = parsed.port
    except ValueError:
        raise PriceFetchError("failed", "درگاه آدرس معتبر نیست") from None
    if parsed.username or parsed.password or port not in (None, 443):
        raise PriceFetchError("failed", "آدرس صفحه معتبر نیست")
    host = hostname.lower().rstrip(".")
    if host not in STORE_HOSTS.get(store, frozenset()):
        raise PriceFetchError("unavailable", "دامنه برای این فروشگاه پشتیبانی نمی‌شود")
    if parsed.scheme != "https":
        raise PriceFetchError("failed", "برای بررسی صفحه، لینک امن https لازم است")
    return parsed.geturl()


def _assert_public_dns(host: str) -> None:
    try:
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise PriceFetchError("failed", "دامنهٔ فروشگاه قابل دسترسی نیست") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise PriceFetchError("failed", "مقصد آدرس عمومی قابل‌قبولی ندارد")


def _request(
    url: str, *, max_bytes: int = 2_000_000, html_only: bool = True
) -> tuple[int, str, str]:
    current = url
    attempt = 0
    for _ in range(4):
        parsed = urlsplit(current)
        host = (parsed.hostname or "").lower().rstrip(".")
        rate_key = _store_for_host(host)
        _assert_public_dns(host)
        with _lock:
            if _host_blocked_until.get(rate_key, 0) > time.monotonic():
                raise PriceFetchError("blocked", "دریافت از این فروشگاه موقتاً متوقف شده است")
            now = time.monotonic()
            scheduled = max(
                now,
                _host_last_request.get(rate_key, 0)
                + get_settings().competitor_request_interval_seconds,
            )
            _host_last_request[rate_key] = scheduled
        if scheduled > now:
            time.sleep(scheduled - now)
        try:
            with httpx.Client(
                timeout=httpx.Timeout(10.0),
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            ) as client:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        status_code = response.status_code
                        location = response.headers.get("location")
                        content_type = ""
                        body = b""
                    else:
                        status_code = response.status_code
                        location = None
                        content_type = response.headers.get("content-type", "")
                        body_parts: list[bytes] = []
                        total = 0
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > max_bytes:
                                raise PriceFetchError("failed", "حجم صفحه از حد مجاز بیشتر است")
                            body_parts.append(chunk)
                        body = b"".join(body_parts)
        except httpx.HTTPError as exc:
            if attempt == 0:
                attempt = 1
                time.sleep(get_settings().competitor_request_interval_seconds * 2)
                continue
            raise PriceFetchError("failed", "دریافت صفحه با خطای شبکه روبه‌رو شد") from exc
        if status_code in (403, 429):
            with _lock:
                _host_blocked_until[rate_key] = time.monotonic() + 6 * 60 * 60
            raise PriceFetchError("blocked", f"فروشگاه درخواست را محدود کرد (HTTP {status_code})")
        if 300 <= status_code < 400:
            if not location:
                break
            current = urljoin(current, location)
            try:
                redirect_host = urlsplit(current).hostname or ""
            except ValueError:
                raise PriceFetchError("failed", "تغییرمسیر نامعتبر است") from None
            current = _normalise_url(current, _store_for_host(redirect_host))
            attempt = 0
            continue
        if status_code >= 500:
            if attempt == 0:
                attempt = 1
                time.sleep(get_settings().competitor_request_interval_seconds * 2)
                continue
            raise PriceFetchError("unavailable", f"فروشگاه موقتاً پاسخ‌گو نیست (HTTP {status_code})")
        if status_code == 404:
            raise PriceFetchError("not_found", "صفحهٔ محصول پیدا نشد")
        if status_code >= 400:
            raise PriceFetchError("failed", f"دریافت صفحه ناموفق بود (HTTP {status_code})")
        if html_only and "html" not in content_type.lower():
            raise PriceFetchError("unavailable", "محتوای لینک صفحهٔ محصول نیست")
        encoding = "utf-8"
        html = body.decode(encoding, errors="replace")
        return status_code, html, current
    raise PriceFetchError("failed", "تعداد تغییرمسیرهای صفحه بیش از حد مجاز است")


def _store_for_host(host: str) -> str:
    for store, hosts in STORE_HOSTS.items():
        if host.lower().rstrip(".") in hosts:
            return store
    raise PriceFetchError("unavailable", "تغییرمسیر به دامنهٔ پشتیبانی‌نشده مجاز نیست")


def _robots_allows(url: str) -> None:
    host = urlsplit(url).hostname or ""
    with _lock:
        entry = _robot_cache.get(host)
        if entry and entry[0] > time.monotonic():
            parser = entry[1]
        else:
            parser = None
    if parser is None:
        parser = RobotFileParser()
        robots_url = f"https://{host}/robots.txt"
        try:
            _, body, resolved_robots_url = _request(robots_url, max_bytes=256_000, html_only=False)
        except PriceFetchError:
            raise PriceFetchError("unavailable", "قوانین robots.txt قابل بررسی نیست") from None
        parser.set_url(resolved_robots_url)
        parser.parse(body.splitlines())
        with _lock:
            _robot_cache[host] = (time.monotonic() + 3600, parser)
    if not parser.can_fetch(USER_AGENT, url):
        raise PriceFetchError("blocked", "robots.txt اجازهٔ بررسی این صفحه را نمی‌دهد")


def _as_object(value: object) -> list[dict[str, object]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        graph = value.get("@graph")
        if isinstance(graph, list):
            return [item for item in graph if isinstance(item, dict)]
        return [value]
    return []


def _price_from_json_ld(html: str) -> FetchedPrice | None:
    parser = JsonLdParser()
    parser.feed(html)
    for document in parser.documents:
        try:
            root = json.loads(document)
        except (ValueError, TypeError):
            continue
        for item in _as_object(root):
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if not any(str(kind).lower().rsplit("/", 1)[-1] == "product" for kind in types):
                continue
            offers = item.get("offers")
            offer_list = offers if isinstance(offers, list) else [offers]
            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                raw_price = offer.get("price")
                currency = str(offer.get("priceCurrency", "")).upper()
                try:
                    amount = Decimal(str(raw_price).replace(",", "").strip())
                except (InvalidOperation, ValueError):
                    continue
                if not amount.is_finite() or amount <= 0 or currency not in {"IRR", "IRT"}:
                    continue
                availability = str(offer.get("availability", "")).lower()
                in_stock = (
                    True
                    if availability.endswith("instock")
                    else (
                        False
                        if any(term in availability for term in ("outofstock", "soldout"))
                        else None
                    )
                )
                return FetchedPrice(amount, currency, in_stock)
    return None


def _parse_digikala(html: str) -> FetchedPrice | None:
    """Digikala adapter; only public structured product data is inspected."""
    return _price_from_json_ld(html)


def _parse_technolife(html: str) -> FetchedPrice | None:
    """Technolife adapter; kept separate for store-specific markup changes."""
    return _price_from_json_ld(html)


STORE_PARSERS = {
    "digikala": _parse_digikala,
    "technolife": _parse_technolife,
}


def _price_from_html(html: str) -> FetchedPrice | None:
    """Shared JSON-LD parser kept public for focused parser tests."""
    return _price_from_json_ld(html)


def fetch_competitor_price(store: str, url: str) -> FetchedPrice:
    safe_url = _normalise_url(url, store)
    cache_key = safe_url
    cached = _page_cache.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    _robots_allows(safe_url)
    _, html, _ = _request(safe_url)
    result = STORE_PARSERS[store](html)
    if result is None:
        raise PriceFetchError("unavailable", "قیمت معتبر در دادهٔ ساختاریافتهٔ صفحه پیدا نشد")
    result = replace(result, observed_at=datetime.now(UTC))
    _page_cache[cache_key] = (time.monotonic() + 120, result)
    return result
