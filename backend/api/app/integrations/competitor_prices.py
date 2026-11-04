"""Safe, low-rate public product page inspection for supported stores."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, cast
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
_dns_cache: dict[str, tuple[float, set[ipaddress.IPv4Address | ipaddress.IPv6Address]]] = {}
_host_last_request: dict[str, float] = {}
_host_blocked_until: dict[str, float] = {}
_PAGE_CACHE_TTL_SECONDS = 600
_PAGE_CACHE_MAX_ENTRIES = 512
_DNS_CACHE_TTL_SECONDS = 300
_REQUEST_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
_HTML_HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
_ROBOTS_HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/plain,*/*"}
_DIGIKALA_API_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Referer": "https://www.digikala.com/",
}
_EARLY_PARSE_MIN_BYTES = 32_768


class PriceFetchError(Exception):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class FetchedPrice:
    amount: Decimal | None
    currency: str | None
    in_stock: bool | None
    observed_at: datetime | None = None


_DIGIKALA_ID_RE = re.compile(r"dkp-(\d+)", re.IGNORECASE)
_DIGIKALA_API_BASE = "https://api.digikala.com/v2/product"


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
    if parsed.username or parsed.password or port not in (None, 80, 443):
        raise PriceFetchError("failed", "آدرس صفحه معتبر نیست")
    host = hostname.lower().rstrip(".")
    if host not in STORE_HOSTS.get(store, frozenset()):
        raise PriceFetchError("unavailable", "دامنه برای این فروشگاه پشتیبانی نمی‌شود")
    if parsed.scheme != "https":
        raise PriceFetchError("failed", "برای بررسی صفحه، لینک امن https لازم است")
    return parsed.geturl()


def _assert_public_dns(host: str) -> None:
    now = time.monotonic()
    with _lock:
        cached = _dns_cache.get(host)
        if cached and cached[0] > now:
            addresses = cached[1]
            if not addresses or any(not address.is_global for address in addresses):
                raise PriceFetchError("failed", "مقصد آدرس عمومی قابل‌قبولی ندارد")
            return
    try:
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise PriceFetchError("failed", "دامنهٔ فروشگاه قابل دسترسی نیست") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise PriceFetchError("failed", "مقصد آدرس عمومی قابل‌قبولی ندارد")
    with _lock:
        _dns_cache[host] = (now + _DNS_CACHE_TTL_SECONDS, addresses)


def _acquire_slot(rate_key: str) -> None:
    """Wait until this store is due for its next request (once per logical check).

    Redirect hops inside one fetch must not each sleep a full interval —
    otherwise a 4-hop Technolife chain alone costs ~20s. Spacing is enforced
    here, on the first request of a check; later hops only re-check the block.
    """
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


def _is_blocked(rate_key: str) -> bool:
    with _lock:
        return _host_blocked_until.get(rate_key, 0) > time.monotonic()


def _cache_get(key: str) -> FetchedPrice | None:
    with _lock:
        entry = _page_cache.get(key)
        if entry is None:
            return None
        if entry[0] <= time.monotonic():
            del _page_cache[key]
            return None
        return entry[1]


def _cache_set(key: str, value: FetchedPrice) -> None:
    with _lock:
        now = time.monotonic()
        for expired_key in [k for k, (expiry, _) in _page_cache.items() if expiry <= now]:
            del _page_cache[expired_key]
        while len(_page_cache) >= _PAGE_CACHE_MAX_ENTRIES:
            _page_cache.pop(next(iter(_page_cache)))
        _page_cache[key] = (now + _PAGE_CACHE_TTL_SECONDS, value)


def _stream_body_with_early_exit(response: Any, *, max_bytes: int) -> bytes:
    """Read a streamed body, stopping early once structured price data appears.

    JSON-LD product data lives in ``<head>`` (usually the first tens of KB)
    while the rest of the page can be megabytes of body markup. As soon as
    the accumulated prefix already yields a price, the remaining bytes are
    skipped — the stream context still closes the connection cleanly.
    """
    body_parts: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise PriceFetchError("failed", "حجم صفحه از حد مجاز بیشتر است")
        body_parts.append(chunk)
        if total >= _EARLY_PARSE_MIN_BYTES and b"application/ld+json" in chunk.lower():
            prefix = b"".join(body_parts)
            if b"</script>" in prefix.lower():
                # _price_from_json_ld swallows malformed-JSON prefixes and
                # returns None, so a partial head simply keeps streaming.
                if _price_from_json_ld(prefix.decode("utf-8", errors="replace")) is not None:
                    return prefix
    return b"".join(body_parts)


def _request(
    url: str,
    *,
    max_bytes: int = 2_000_000,
    html_only: bool = True,
    acquire_slot: bool = True,
    client: httpx.Client | None = None,
) -> tuple[int, str, str]:
    current = url
    attempt = 0
    owned = client is None
    # One client for the whole redirect chain: reuses TCP/TLS + connection
    # pool across hops instead of a fresh handshake per hop.
    active = client or httpx.Client(
        timeout=_REQUEST_TIMEOUT,
        follow_redirects=False,
        trust_env=False,
        headers=_ROBOTS_HEADERS if not html_only else _HTML_HEADERS,
    )
    try:
        # Technolife slug-less links bounce across domains a few times
        # (technolife.ir → technolife.com → slash normalisation → slug), so allow
        # up to 8 redirects instead of failing on the 4th hop.
        for _ in range(10):
            parsed = urlsplit(current)
            host = (parsed.hostname or "").lower().rstrip(".")
            rate_key = _store_for_host(host)
            _assert_public_dns(host)
            if acquire_slot:
                _acquire_slot(rate_key)
                acquire_slot = False
            elif _is_blocked(rate_key):
                raise PriceFetchError("blocked", "دریافت از این فروشگاه موقتاً متوقف شده است")
            try:
                headers = _ROBOTS_HEADERS if not html_only else _HTML_HEADERS
                with active.stream("GET", current, headers=headers) as response:
                    if response.is_redirect:
                        status_code = response.status_code
                        location = response.headers.get("location")
                        content_type = ""
                        body = b""
                    else:
                        status_code = response.status_code
                        location = None
                        content_type = response.headers.get("content-type", "")
                        body = _stream_body_with_early_exit(response, max_bytes=max_bytes)
            except httpx.HTTPError as exc:
                if attempt == 0:
                    attempt = 1
                    time.sleep(get_settings().competitor_request_interval_seconds)
                    continue
                raise PriceFetchError("failed", "دریافت صفحه با خطای شبکه روبه‌رو شد") from exc
            if status_code in (403, 429):
                with _lock:
                    _host_blocked_until[rate_key] = time.monotonic() + 6 * 60 * 60
                log.warning("competitor store rate-limited store=%s http=%s", rate_key, status_code)
                raise PriceFetchError(
                    "blocked", f"فروشگاه درخواست را محدود کرد (HTTP {status_code})"
                )
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
                    time.sleep(get_settings().competitor_request_interval_seconds)
                    continue
                raise PriceFetchError(
                    "unavailable", f"فروشگاه موقتاً پاسخ‌گو نیست (HTTP {status_code})"
                )
            if status_code == 404:
                raise PriceFetchError("not_found", "صفحهٔ محصول پیدا نشد")
            if status_code >= 400:
                raise PriceFetchError("failed", f"دریافت صفحه ناموفق بود (HTTP {status_code})")
            if html_only and "html" not in content_type.lower():
                raise PriceFetchError("unavailable", "محتوای لینک صفحهٔ محصول نیست")
            html = body.decode("utf-8", errors="replace")
            return status_code, html, current
        raise PriceFetchError("failed", "تعداد تغییرمسیرهای صفحه بیش از حد مجاز است")
    finally:
        if owned:
            active.close()


def _store_for_host(host: str) -> str:
    for store, hosts in STORE_HOSTS.items():
        if host.lower().rstrip(".") in hosts:
            return store
    raise PriceFetchError("unavailable", "تغییرمسیر به دامنهٔ پشتیبانی‌نشده مجاز نیست")


def _robots_allows(url: str, client: httpx.Client | None = None) -> None:
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
            # robots.txt must not consume the check's rate-limit slot: the
            # page/API fetch below already spaces this logical check.
            _, body, resolved_robots_url = _request(
                robots_url, max_bytes=256_000, html_only=False, acquire_slot=False, client=client
            )
        except PriceFetchError as exc:
            # No robots.txt (404) means crawling is allowed; anything else
            # (network error, rate-limit) stays an availability problem.
            if exc.status == "not_found":
                return
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


def _iter_offers(value: object) -> object:
    """Yield offer dicts, descending into nested AggregateOffer.offers."""
    if isinstance(value, list):
        for item in value:
            yield from _iter_offers(item)
    elif isinstance(value, dict):
        if value.get("price") is not None:
            yield value
        nested = value.get("offers")
        if nested is not None:
            yield from _iter_offers(nested)


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
            for offer in _iter_offers(offers):
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
    """Technolife adapter; kept separate for store-specific markup changes.

    Technolife labels its JSON-LD offer with ``priceCurrency: IRR`` while the
    numeric value matches the Toman price shown on the page (e.g. 112900000
    for «۱۱۲٬۹۰۰٬۰۰۰ تومان»). Dividing such values by 10 (IRR→toman) drops
    one zero, so normalise them to IRT at the source.
    """
    result = _price_from_json_ld(html)
    if result is not None and result.currency == "IRR":
        return replace(result, currency="IRT")
    return result


STORE_PARSERS = {
    "digikala": _parse_digikala,
    "technolife": _parse_technolife,
}


def _price_from_html(html: str) -> FetchedPrice | None:
    """Shared JSON-LD parser kept public for focused parser tests."""
    return _price_from_json_ld(html)


def _digikala_product_id(url: str) -> str | None:
    """Extract the numeric product id from a Digikala `/product/dkp-<id>/` URL."""
    match = _DIGIKALA_ID_RE.search(urlsplit(url).path or "")
    return match.group(1) if match else None


def _fetch_digikala_api(product_id: str, client: httpx.Client | None = None) -> FetchedPrice:
    """Read price/stock from Digikala's public product API (prices in Rial)."""
    api_url = f"{_DIGIKALA_API_BASE}/{product_id}/"
    attempt = 0
    owned = client is None
    active = client or httpx.Client(
        timeout=_REQUEST_TIMEOUT,
        follow_redirects=False,
        trust_env=False,
    )
    try:
        while True:
            try:
                response = active.get(api_url, headers=_DIGIKALA_API_HEADERS)
            except httpx.HTTPError as exc:
                if attempt == 0:
                    attempt = 1
                    time.sleep(get_settings().competitor_request_interval_seconds)
                    continue
                raise PriceFetchError(
                    "failed", "دریافت قیمت دیجی‌کالا با خطای شبکه روبه‌رو شد"
                ) from exc
            status_code = response.status_code
            if status_code in (403, 429):
                with _lock:
                    _host_blocked_until["digikala"] = time.monotonic() + 6 * 60 * 60
                log.warning("competitor store rate-limited store=digikala http=%s", status_code)
                raise PriceFetchError(
                    "blocked", f"دیجی‌کالا درخواست را محدود کرد (HTTP {status_code})"
                )
            if status_code == 404:
                raise PriceFetchError("not_found", "صفحهٔ محصول در دیجی‌کالا پیدا نشد")
            if status_code >= 500:
                if attempt == 0:
                    attempt = 1
                    time.sleep(get_settings().competitor_request_interval_seconds)
                    continue
                raise PriceFetchError(
                    "unavailable", f"سرویس دیجی‌کالا موقتاً پاسخ‌گو نیست (HTTP {status_code})"
                )
            if status_code >= 400:
                raise PriceFetchError(
                    "failed", f"دریافت قیمت دیجی‌کالا ناموفق بود (HTTP {status_code})"
                )
            try:
                payload = cast(dict[str, Any], response.json())
                product = cast(dict[str, Any], payload["data"]["product"])
            except (ValueError, KeyError, TypeError):
                raise PriceFetchError(
                    "unavailable", "پاسخ سرویس دیجی‌کالا قابل تفسیر نیست"
                ) from None
            product_status = str(product.get("status", ""))
            variant = product.get("default_variant")
            if isinstance(variant, list):
                variant = None
            variant_map = cast(
                dict[str, Any] | None, variant if isinstance(variant, dict) else None
            )
            price = variant_map.get("price") if variant_map is not None else None
            price_map = cast(dict[str, Any] | None, price if isinstance(price, dict) else None)
            selling = price_map.get("selling_price") if price_map is not None else None
            try:
                amount = Decimal(str(selling)) if selling is not None else None
            except InvalidOperation:
                amount = None
            if amount is not None and (not amount.is_finite() or amount <= 0):
                amount = None
            if amount is not None:
                variant_status = variant_map.get("status") if variant_map is not None else None
                in_stock = product_status == "marketable" and (
                    variant_map is None or variant_status == "marketable"
                )
                return FetchedPrice(amount, "IRR", in_stock)
            if product_status in {"out_of_stock", "unmarketable", "not_sellable", "inactive"}:
                return FetchedPrice(None, None, False)
            raise PriceFetchError("unavailable", "قیمت معتبر در پاسخ دیجی‌کالا پیدا نشد")
    finally:
        if owned:
            active.close()


def fetch_competitor_price(store: str, url: str) -> FetchedPrice:
    safe_url = _normalise_url(url, store)
    cache_key = safe_url
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    # One rate-limit slot per logical check: robots + redirects + API share it.
    # Previously robots.txt consumed a slot and the page waited another full
    # interval (~+5s on every cold check).
    _acquire_slot(store)
    with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=False, trust_env=False) as client:
        if store == "digikala":
            # Bot traffic usually gets a JS-shell page without JSON-LD, so try
            # the light public JSON API first and skip the heavy HTML fetch.
            product_id = _digikala_product_id(safe_url)
            if product_id is not None:
                try:
                    result = _fetch_digikala_api(product_id, client=client)
                except PriceFetchError as exc:
                    if exc.status in ("blocked", "not_found", "failed"):
                        raise
                    # "unavailable" (e.g. no price in API payload) falls
                    # through to the HTML path below.
                else:
                    result = replace(result, observed_at=datetime.now(UTC))
                    _cache_set(cache_key, result)
                    _log_fetched(store, safe_url, result)
                    return result
        _robots_allows(safe_url, client=client)
        _, html, _ = _request(safe_url, acquire_slot=False, client=client)
        result = STORE_PARSERS[store](html)
        if result is None and store == "digikala":
            # HTML fallback missed (or API-first was skipped): last resort is
            # the public product API using the dkp-<id> in the URL.
            product_id = _digikala_product_id(safe_url)
            if product_id is None:
                raise PriceFetchError("unavailable", "قیمت معتبر در دادهٔ ساختاریافتهٔ صفحه پیدا نشد")
            result = _fetch_digikala_api(product_id, client=client)
        if result is None:
            raise PriceFetchError("unavailable", "قیمت معتبر در دادهٔ ساختاریافتهٔ صفحه پیدا نشد")
        result = replace(result, observed_at=datetime.now(UTC))
        _cache_set(cache_key, result)
        _log_fetched(store, safe_url, result)
        return result


def _log_fetched(store: str, safe_url: str, result: FetchedPrice) -> None:
    host = (urlsplit(safe_url).hostname or "").lower()
    log.info(
        "competitor price fetched store=%s host=%s amount=%s currency=%s in_stock=%s",
        store,
        host,
        result.amount,
        result.currency,
        result.in_stock,
    )
