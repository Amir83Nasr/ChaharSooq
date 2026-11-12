"""CSV exports — presentation rows for products and competitor listings.

Exports are user-facing files: Persian headers, Persian digits, Jalali dates.
The JSON API keeps machine values; this module is the deliberate exception
documented in docs/api/README.md.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.csv_export import EXPORT_MAX_ROWS, csv_response
from app.core.persian_format import (
    format_amount,
    format_bool,
    format_jalali_datetime,
    format_percent,
)
from app.models import CompetitorListing, Product
from app.repositories import (
    CompetitorRepository,
    ProductFilters,
    ProductRepository,
    ProductSort,
)
from app.schemas.competitor import CompetitorListingOut, CompetitorPriceOut
from app.services.competitor import STORE_LABELS, CompetitorService
from app.services.settings import SettingsService

# Canonical store order for the per-store price columns.
STORE_COLUMNS = ("digikala", "technolife", "sofa", "digifresh")

LISTING_STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "success": "دریافت شد",
    "not_found": "صفحه پیدا نشد",
    "unavailable": "استخراج در دسترس نیست",
    "blocked": "دسترسی محدود شد",
    "failed": "دریافت ناموفق",
    "manual": "ثبت دستی",
}

PRODUCT_HEADERS = (
    "شناسه",
    "نام",
    "کد",
    "دسته‌بندی",
    "گروه اصلی",
    "زیرگروه",
    "واحد",
    "قیمت (تومان)",
    "موجودی",
    "وضعیت موجودی",
    *(f"قیمت {STORE_LABELS[store]}" for store in STORE_COLUMNS),
    "کمینه قیمت رقبا",
    "اختلاف با کمینه رقبا (٪)",
    "قیمت خرید",
    "ویژه",
    "شناسه پارسینا",
    "آخرین همگام‌سازی",
)

LISTING_HEADERS = (
    "شناسه محصول",
    "نام محصول",
    "کد کالا",
    "دسته‌بندی",
    "فروشگاه",
    "لینک",
    "وضعیت",
    "فعال",
    "قیمت مؤثر (تومان)",
    "موجود",
    "قیمت تازه",
    "درصد تغییر",
    "قیمت قبلی",
    "تاریخ مشاهده قبلی",
    "آخرین موفقیت",
    "آخرین خطا",
)

EXPORT_TOO_LARGE_MESSAGE = (
    f"خروجی بیش از {format_amount(EXPORT_MAX_ROWS)} ردیف می‌شود؛ فیلترها را محدودتر کنید."
)


class ExportTooLargeError(ValueError):
    """The filtered result exceeds EXPORT_MAX_ROWS; narrow the filters."""


def _filename(kind: str) -> str:
    return f"{kind}-{datetime.now(UTC).date().isoformat()}.csv"


def _to_toman(price: float | Decimal | None, currency: str | None) -> Decimal | None:
    if price is None:
        return None
    amount = Decimal(str(price))
    return amount / 10 if currency == "IRR" else amount


def _top_group(main_group_name: str | None) -> str:
    if not main_group_name:
        return ""
    name = main_group_name.strip()
    if name.startswith("فرش"):
        return "فرش"
    if name.startswith("مبلمان"):
        return "مبلمان"
    return "لوازم خانگی"


def _stock_status(stock: Decimal, threshold: int) -> str:
    if stock <= 0:
        return "ناموجود"
    if stock <= threshold:
        return "موجودی کم"
    return "موجود"


class ExportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._listings = CompetitorRepository(session)

    # ── products ────────────────────────────────────────────────────────

    def products_csv(self, *, filters: ProductFilters, sort: ProductSort) -> StreamingResponse:
        if self._products.count(filters=filters) > EXPORT_MAX_ROWS:
            raise ExportTooLargeError
        threshold = SettingsService(self._session).get_threshold()
        rows = self._product_rows(filters=filters, sort=sort, threshold=threshold)
        return csv_response(_filename("products"), PRODUCT_HEADERS, rows)

    def _product_rows(
        self,
        *,
        filters: ProductFilters,
        sort: ProductSort,
        threshold: int,
    ) -> Iterator[Sequence[str]]:
        competitors = CompetitorService(self._session)
        for batch in self._products.iter_batches(filters=filters, sort=sort):
            prices = competitors.prices_for_products({product.id for product in batch})
            for product in batch:
                yield self._product_row(product, prices.get(product.id, []), threshold)

    def _product_row(
        self,
        product: Product,
        prices: list[CompetitorPriceOut],
        threshold: int,
    ) -> Sequence[str]:
        # Only fresh prices count (same TTL as the products API); a stale
        # number must never look like today's market price in an export.
        fresh = {
            price.store: price for price in prices if price.is_fresh and price.price is not None
        }
        store_prices = [
            _to_toman(fresh[store].price, fresh[store].currency) if store in fresh else None
            for store in STORE_COLUMNS
        ]
        present = [value for value in store_prices if value is not None]
        minimum = min(present) if present else None
        price = Decimal(str(product.price))
        diff = (
            (price - minimum) / minimum * 100
            if minimum is not None and minimum > 0 and price > 0
            else None
        )
        stock = product.stock
        return [
            format_amount(product.id),
            product.name,
            product.sku,
            _top_group(product.main_group_name),
            product.main_group_name or "",
            product.sub_group_name or "",
            product.unit_name or "",
            format_amount(product.price),
            format_amount(stock),
            _stock_status(stock, threshold),
            *(format_amount(value) for value in store_prices),
            format_amount(minimum),
            format_percent(diff),
            format_amount(product.buy_price),
            format_bool(product.is_special),
            format_amount(product.external_id),
            format_jalali_datetime(product.synced_at),
        ]

    # ── competitor listings ─────────────────────────────────────────────

    def competitor_listings_csv(
        self,
        *,
        filters: ProductFilters,
        store: str | None,
        status: str | None,
        is_active: bool | None,
    ) -> StreamingResponse:
        total = self._listings.count_export(
            filters=filters,
            store=store,
            status=status,
            is_active=is_active,
        )
        if total > EXPORT_MAX_ROWS:
            raise ExportTooLargeError
        rows = self._listing_rows(
            filters=filters,
            store=store,
            status=status,
            is_active=is_active,
        )
        return csv_response(_filename("competitor-listings"), LISTING_HEADERS, rows)

    def _listing_rows(
        self,
        *,
        filters: ProductFilters,
        store: str | None,
        status: str | None,
        is_active: bool | None,
    ) -> Iterator[Sequence[str]]:
        competitors = CompetitorService(self._session)
        for batch in self._listings.iter_export_batches(
            filters=filters,
            store=store,
            status=status,
            is_active=is_active,
        ):
            details = {
                detail.id: detail
                for detail in competitors.details_for_listings(
                    [listing for listing, _product in batch]
                )
            }
            for listing, product in batch:
                detail = details.get(listing.id)
                if detail is None:  # pragma: no cover — every row has a detail
                    continue
                yield self._listing_row(listing, product, detail)

    def _listing_row(
        self,
        listing: CompetitorListing,
        product: Product,
        detail: CompetitorListingOut,
    ) -> Sequence[str]:
        effective = _to_toman(detail.effective_price, detail.effective_currency)
        previous = _to_toman(detail.previous_price, detail.previous_currency)
        return [
            format_amount(product.id),
            product.name,
            product.sku,
            _top_group(product.main_group_name),
            STORE_LABELS.get(listing.store, listing.store),
            listing.url,
            LISTING_STATUS_LABELS.get(listing.status, listing.status),
            format_bool(listing.is_active),
            format_amount(effective),
            format_bool(detail.effective_in_stock),
            format_bool(detail.price_is_fresh),
            format_percent(detail.price_change_percent),
            format_amount(previous),
            format_jalali_datetime(detail.previous_observed_at),
            format_jalali_datetime(listing.last_success_at),
            listing.last_error or "",
        ]
