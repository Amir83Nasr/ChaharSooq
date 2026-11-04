"""Competitor link lifecycle, freshness, and safe fetch orchestration."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from ipaddress import ip_address
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.competitor_prices import PriceFetchError, fetch_competitor_price
from app.models import CompetitorListing
from app.repositories.competitor import CompetitorRepository
from app.schemas.competitor import (
    CompetitorListingCreate,
    CompetitorListingOut,
    CompetitorListingUpdate,
    CompetitorPriceOut,
)

STORE_HOSTS: dict[str, frozenset[str]] = {
    "digikala": frozenset({"digikala.com", "www.digikala.com"}),
    "technolife": frozenset(
        {"technolife.ir", "www.technolife.ir", "technolife.com", "www.technolife.com"}
    ),
}


class CompetitorNotFoundError(LookupError):
    pass


class InvalidCompetitorProductError(ValueError):
    pass


class CompetitorThrottledError(ValueError):
    """Check attempted before the politeness interval elapsed (HTTP 429)."""


def validate_url(url: str, store: str) -> str:
    raw = url.strip()
    try:
        parts = urlsplit(raw)
        hostname_value = parts.hostname
    except ValueError:
        raise ValueError("آدرس نامعتبر است") from None
    if parts.scheme not in {"http", "https"} or not hostname_value:
        raise ValueError("آدرس باید یک URL با http یا https باشد")
    if parts.username or parts.password:
        raise ValueError("نام کاربری و گذرواژه در آدرس پذیرفته نمی‌شود")
    try:
        port = parts.port
    except ValueError:
        raise ValueError("درگاه آدرس نامعتبر است") from None
    if port not in (None, 80, 443):
        raise ValueError("درگاه سفارشی پذیرفته نمی‌شود")
    hostname = hostname_value.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("آدرس شبکهٔ داخلی پذیرفته نمی‌شود")
    try:
        ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("آدرس IP مستقیم پذیرفته نمی‌شود؛ دامنهٔ فروشگاه را وارد کنید")
    if not hostname or len(hostname) > 253 or ".." in hostname:
        raise ValueError("دامنهٔ آدرس نامعتبر است")
    if not parts.path or parts.path == "/":
        raise ValueError("لینک باید به صفحهٔ یک محصول اشاره کند")
    matching_store = next((key for key, hosts in STORE_HOSTS.items() if hostname in hosts), None)
    if matching_store is not None and matching_store != store:
        raise ValueError("فروشگاه انتخاب‌شده با دامنهٔ لینک هم‌خوانی ندارد")
    if matching_store is None and store != "other":
        raise ValueError("برای این دامنه، گزینهٔ سایر فروشگاه‌ها را انتخاب کنید")
    return raw


def _is_appliance(main_group_name: str | None) -> bool:
    if main_group_name is None:
        return True
    name = main_group_name.strip()
    return not name.startswith(("فرش", "مبلمان"))


class CompetitorService:
    def __init__(self, session: Session) -> None:
        self._repo = CompetitorRepository(session)

    def _out(self, row: CompetitorListing) -> CompetitorListingOut:
        now = datetime.now(UTC)
        ttl = timedelta(hours=get_settings().competitor_price_ttl_hours)
        # Manual values always win over fetched ones (and over the future
        # automatic name-based search): a fresh manual price/in-stock is effective.
        manual_fresh = (
            row.manual_updated_at is not None and now - _aware(row.manual_updated_at) <= ttl
        )
        fetched_fresh = row.last_success_at is not None and now - _aware(row.last_success_at) <= ttl
        if manual_fresh and row.manual_price is not None:
            price, currency = row.manual_price, row.manual_currency
            fresh = True
        elif fetched_fresh and row.fetched_price is not None:
            price, currency = row.fetched_price, row.fetched_currency
            fresh = True
        else:
            price, currency, fresh = None, None, False
        if manual_fresh and row.manual_in_stock is not None:
            in_stock = row.manual_in_stock
        elif fetched_fresh:
            in_stock = row.fetched_in_stock
        else:
            in_stock = None
        return CompetitorListingOut(
            id=row.id,
            product_id=row.product_id,
            store=row.store,  # type: ignore[arg-type]
            url=row.url,
            is_active=row.is_active,
            status=row.status,  # type: ignore[arg-type]
            fetched_price=float(row.fetched_price) if row.fetched_price is not None else None,
            fetched_currency=row.fetched_currency,  # type: ignore[arg-type]
            fetched_in_stock=row.fetched_in_stock,
            manual_price=float(row.manual_price) if row.manual_price is not None else None,
            manual_currency=row.manual_currency,  # type: ignore[arg-type]
            manual_in_stock=row.manual_in_stock,
            effective_price=float(price) if price is not None and row.is_active else None,
            effective_currency=currency if row.is_active else None,  # type: ignore[arg-type]
            effective_in_stock=in_stock if row.is_active else None,
            price_is_fresh=fresh and row.is_active,
            last_checked_at=row.last_checked_at,
            last_success_at=row.last_success_at,
            manual_updated_at=row.manual_updated_at,
            last_error=row.last_error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def list_product_listings(self, product_id: int) -> list[CompetitorListingOut]:
        if self._repo.product(product_id) is None:
            raise CompetitorNotFoundError
        return [self._out(row) for row in self._repo.list_for_product(product_id)]

    def prices_for_products(self, product_ids: set[int]) -> dict[int, list[CompetitorPriceOut]]:
        rows = self._repo.list_for_products(product_ids)
        output: dict[int, list[CompetitorPriceOut]] = {}
        for row in rows:
            detail = self._out(row)
            output.setdefault(row.product_id, []).append(
                CompetitorPriceOut(
                    id=row.id,
                    store=row.store,  # type: ignore[arg-type]
                    url=row.url,
                    status=row.status,  # type: ignore[arg-type]
                    price=detail.effective_price,
                    currency=detail.effective_currency,
                    in_stock=detail.effective_in_stock,
                    is_fresh=detail.price_is_fresh,
                    is_manual=(
                        detail.price_is_fresh
                        and row.manual_price is not None
                        and row.manual_updated_at is not None
                        and detail.effective_price == float(row.manual_price)
                    ),
                    last_checked_at=row.last_checked_at,
                )
            )
        return output

    def create(self, product_id: int, payload: CompetitorListingCreate) -> CompetitorListingOut:
        product = self._repo.product(product_id)
        if product is None:
            raise CompetitorNotFoundError
        if not _is_appliance(product.main_group_name):
            raise InvalidCompetitorProductError("این فاز فقط برای کالاهای لوازم خانگی است")
        # Manual links (digikala / technolife) take priority over the future
        # automatic name-based search: at most one manual link per store.
        if (
            payload.store in ("digikala", "technolife")
            and self._repo.get_by_product_store(product_id, payload.store) is not None
        ):
            raise InvalidCompetitorProductError("برای این فروشگاه قبلاً یک لینک ثبت شده است")
        try:
            url = validate_url(payload.url, payload.store)
        except ValueError as exc:
            raise InvalidCompetitorProductError(str(exc)) from exc
        row = self._repo.add(
            CompetitorListing(
                product_id=product_id,
                store=payload.store,
                url=url,
                is_active=True,
                status="pending",
            )
        )
        return self._out(row)

    def update(self, listing_id: int, payload: CompetitorListingUpdate) -> CompetitorListingOut:
        row = self._repo.get(listing_id)
        if row is None:
            raise CompetitorNotFoundError
        values = payload.model_dump(exclude_unset=True)
        target_store = values.get("store") or row.store
        target_url = values.get("url") or row.url
        if "store" in values or "url" in values:
            try:
                target_url = validate_url(target_url, target_store)
            except ValueError as exc:
                raise InvalidCompetitorProductError(str(exc)) from exc
            link_changed = target_store != row.store or target_url != row.url
            if link_changed:
                if target_store in ("digikala", "technolife") and (
                    self._repo.get_by_product_store(row.product_id, target_store, exclude_id=row.id)
                    is not None
                ):
                    raise InvalidCompetitorProductError("برای این فروشگاه قبلاً یک لینک ثبت شده است")
                row.store = target_store
                row.url = target_url
                row.status = "pending"
                row.fetched_price = None
                row.fetched_currency = None
                row.fetched_in_stock = None
                row.last_success_at = None
                row.manual_updated_at = None
        if "is_active" in values and values["is_active"] is not None:
            row.is_active = values["is_active"]
        manual_fields_changed = any(
            key in values for key in ("manual_price", "manual_currency", "manual_in_stock")
        )
        if "manual_price" in values:
            row.manual_price = (
                Decimal(str(values["manual_price"])) if values["manual_price"] is not None else None
            )
        if "manual_currency" in values:
            row.manual_currency = values["manual_currency"]
        if "manual_in_stock" in values:
            row.manual_in_stock = values["manual_in_stock"]
        if row.manual_price is not None and row.manual_currency is None:
            row.manual_currency = "IRT"
        if manual_fields_changed:
            row.manual_updated_at = (
                datetime.now(UTC)
                if row.manual_price is not None or row.manual_in_stock is not None
                else None
            )
            if row.manual_updated_at is not None:
                row.status = "manual"
        self._repo.flush()
        return self._out(row)

    def delete(self, listing_id: int) -> None:
        row = self._repo.get(listing_id)
        if row is None:
            raise CompetitorNotFoundError
        self._repo.delete(row)

    def check(self, listing_id: int) -> CompetitorListingOut:
        row = self._repo.get(listing_id)
        if row is None:
            raise CompetitorNotFoundError
        now = datetime.now(UTC)
        interval = get_settings().competitor_request_interval_seconds
        if (
            row.last_checked_at is not None
            and (now - _aware(row.last_checked_at)).total_seconds() < interval
        ):
            raise CompetitorThrottledError(
                "برای جلوگیری از درخواست پرتکرار، کمی بعد دوباره تلاش کنید"
            )
        row.last_checked_at = now
        try:
            result = fetch_competitor_price(row.store, row.url)
        except PriceFetchError as exc:
            row.status = exc.status
            row.last_error = str(exc)[:500]
        else:
            row.fetched_price = result.amount
            row.fetched_currency = result.currency
            row.fetched_in_stock = result.in_stock
            row.last_success_at = result.observed_at or now
            row.status = "success"
            row.last_error = None
        self._repo.flush()
        return self._out(row)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
