"""CSV exports — presentation rows for products and competitor listings.

Exports are user-facing files: Persian headers, Persian digits, Jalali dates.
The JSON API keeps machine values; this module is the deliberate exception
documented in docs/api/README.md.
"""

from __future__ import annotations

import re
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
    to_persian_digits,
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
from app.services.settings import PRODUCT_TABLE_COLUMNS, SettingsService

MARKET_LABELS = {
    "digikala": "دیجی‌کالا",
    "technolife": "تکنولایف",
    "sofa": "سوفا",
    "digifresh": "دیجی‌فرش",
}

COMPETITOR_STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "success": "قیمت تازه دریافت نشده",
    "not_found": "صفحه پیدا نشد",
    "unavailable": "نیازمند بررسی",
    "blocked": "دسترسی محدود شد",
    "failed": "دریافت ناموفق",
    "manual": "قیمت تازه ثبت نشده",
}

LISTING_STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "success": "دریافت شد",
    "not_found": "صفحه پیدا نشد",
    "unavailable": "استخراج در دسترس نیست",
    "blocked": "دسترسی محدود شد",
    "failed": "دریافت ناموفق",
    "manual": "ثبت دستی",
}

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


def _has_filters(filters: ProductFilters) -> bool:
    return any(
        (
            bool(filters.query),
            filters.category_id is not None,
            bool(filters.top_group),
            bool(filters.main_group),
            filters.min_price is not None,
            filters.max_price is not None,
            bool(filters.competitor_store),
            filters.min_competitor_price is not None,
            filters.max_competitor_price is not None,
            filters.min_stock is not None,
            filters.max_stock is not None,
            filters.in_stock is not None,
        )
    )


def _to_toman(price: float | Decimal | None, currency: str | None) -> Decimal | None:
    if price is None:
        return None
    amount = Decimal(str(price))
    return amount / 10 if currency == "IRR" else amount


def _top_group(main_group_name: str | None) -> str | None:
    if not main_group_name:
        return None
    name = main_group_name.strip()
    if name.startswith("فرش"):
        return "فرش"
    if name.startswith("مبلمان"):
        return "مبلمان"
    return "لوازم خانگی"


def _brand_of(main_group_name: str | None, top: str | None) -> str | None:
    if not main_group_name:
        return None
    name = main_group_name.strip()
    if top == "فرش":
        rest = re.sub(r"^فرش\s*", "", name).strip()
        return rest or None
    if top == "مبلمان":
        rest = re.sub(r"^مبلمان\s*", "", name).strip()
        return rest or None
    if top == "لوازم خانگی":
        rest = re.sub(r"^لوازم\s+خان[گک]ی\s*", "", name).strip()
        return rest or name
    return name


def _format_percent_magnitude(percent: float) -> str:
    rounded = round(percent * 10) / 10
    if rounded == 0:
        rounded = 0.0
    text = f"{abs(rounded):.1f}".rstrip("0").rstrip(".")
    return f"{to_persian_digits(text)}٪"


def _diff_percent(ours: float, theirs: float | None) -> float | None:
    if theirs is None or theirs <= 0 or ours <= 0:
        return None
    return (ours - theirs) / theirs * 100


def _change_percent(base: float, value: float | None) -> float | None:
    if value is None or base <= 0:
        return None
    return (value - base) / base * 100


def _suggested_price_for(
    base_price: float, competitor_price: float | None, weight: float | None
) -> float | None:
    if competitor_price is None or weight is None:
        return None
    if base_price <= 0 or competitor_price <= 0:
        return None
    if weight < 0 or weight > 1:
        return None
    blended = weight * competitor_price + (1 - weight) * base_price
    low = min(base_price, competitor_price)
    high = max(base_price, competitor_price)
    return round(min(max(blended, low), high))


def _suggested_price_from_daily_change(
    base_price: float, change_percent: float | None, weight: float | None
) -> float | None:
    if change_percent is None or weight is None:
        return None
    if base_price <= 0 or weight < 0 or weight > 1:
        return None
    value = base_price * (1 + (weight * change_percent) / 100)
    return round(max(value, 0))


def _apply_price_bounds(
    base_price: float,
    suggested: float | None,
    allowed_decrease_percent: float | None,
    allowed_increase_percent: float | None,
) -> float | None:
    if suggested is None:
        return None
    if base_price <= 0:
        return suggested
    floor = (
        -float("inf")
        if allowed_decrease_percent is None or allowed_decrease_percent < 0
        else base_price * (1 - allowed_decrease_percent / 100)
    )
    ceiling = (
        float("inf")
        if allowed_increase_percent is None or allowed_increase_percent < 0
        else base_price * (1 + allowed_increase_percent / 100)
    )
    return round(min(max(suggested, floor), ceiling))


def _normalize_columns(columns: list[str] | None) -> list[str]:
    if not columns:
        return list(PRODUCT_TABLE_COLUMNS)
    allowed = set(PRODUCT_TABLE_COLUMNS)
    selected = [col for col in columns if col in allowed]
    if not selected:
        selected = list(PRODUCT_TABLE_COLUMNS)
    # Always include row number as the first column in the export.
    if "row" in selected:
        selected = ["row"] + [col for col in selected if col != "row"]
    else:
        selected = ["row"] + selected
    return selected


def _header_for(column: str, market: str) -> str:
    market_label = MARKET_LABELS.get(market, MARKET_LABELS["digikala"])
    headers = {
        "row": "ردیف",
        "name": "نام",
        "sku": "کد",
        "category": "دسته‌بندی",
        "brand": "برند",
        "unit": "واحد",
        "price": "قیمت (تومان)",
        "competitor_price": f"قیمت رقبا ({market_label})",
        "price_diff": "اختلاف درصد",
        "suggested_price": "قیمت پیشنهادی (تومان)",
        "suggested_price_change": "درصد تغییر",
        "stock": "موجودی",
    }
    return headers[column]


class ExportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._listings = CompetitorRepository(session)

    # ── products ────────────────────────────────────────────────────────

    def products_csv(
        self,
        *,
        filters: ProductFilters,
        sort: ProductSort,
        columns: list[str] | None = None,
        market: str | None = None,
    ) -> StreamingResponse:
        if self._products.count(filters=filters) > EXPORT_MAX_ROWS:
            raise ExportTooLargeError
        settings = SettingsService(self._session)
        threshold = settings.get_threshold()
        formulas = settings.get_suggested_price_formulas()
        weights: dict[str, float] = {}
        for item in formulas:
            top_group = item.get("top_group")
            weight = item.get("weight")
            if isinstance(top_group, str) and weight is not None:
                weights[top_group] = float(str(weight))
        selected_market = market or settings.get_competitor_store()
        if selected_market not in MARKET_LABELS:
            selected_market = "digikala"
        selected_columns = _normalize_columns(columns)
        headers = tuple(_header_for(col, selected_market) for col in selected_columns)
        rows = self._product_rows(
            filters=filters,
            sort=sort,
            threshold=threshold,
            weights=weights,
            market=selected_market,
            columns=selected_columns,
        )
        filename_kind = "products-filtered" if _has_filters(filters) else "products"
        return csv_response(_filename(filename_kind), headers, rows)

    def _product_rows(
        self,
        *,
        filters: ProductFilters,
        sort: ProductSort,
        threshold: int,
        weights: dict[str, float],
        market: str,
        columns: list[str],
    ) -> Iterator[Sequence[str]]:
        competitors = CompetitorService(self._session)
        row_number = 0
        for batch in self._products.iter_batches(filters=filters, sort=sort):
            prices = competitors.prices_for_products({product.id for product in batch})
            for product in batch:
                row_number += 1
                yield self._product_row(
                    row_number=row_number,
                    product=product,
                    prices=prices.get(product.id, []),
                    threshold=threshold,
                    weights=weights,
                    market=market,
                    columns=columns,
                )

    def _product_row(
        self,
        *,
        row_number: int,
        product: Product,
        prices: list[CompetitorPriceOut],
        threshold: int,
        weights: dict[str, float],
        market: str,
        columns: list[str],
    ) -> Sequence[str]:
        top = _top_group(product.main_group_name)
        brand = _brand_of(product.main_group_name, top)
        base_price = float(product.price or 0)

        is_appliance = top == "لوازم خانگی"
        tracked_store = (
            market
            if is_appliance
            else ("sofa" if top == "مبلمان" else ("digifresh" if top == "فرش" else None))
        )
        competitor = (
            next((p for p in prices if p.store == tracked_store), None) if tracked_store else None
        )
        show_competitor = tracked_store is not None and (
            is_appliance if market in ("digikala", "technolife") else market == tracked_store
        )
        amount: float | None = None
        if competitor and competitor.price is not None:
            toman = _to_toman(competitor.price, competitor.currency)
            if toman is not None:
                amount = float(toman)
        fresh = bool(competitor and competitor.is_fresh and amount is not None)

        # competitor price cell
        if not show_competitor:
            competitor_price_text = "—"
        elif fresh and amount is not None:
            competitor_price_text = format_amount(amount)
        else:
            status = competitor.status if competitor else None
            competitor_price_text = COMPETITOR_STATUS_LABELS.get(
                str(status) if status else "", "لینک ثبت نشده"
            )

        # price diff (appliances, fresh)
        pct = _diff_percent(base_price, amount) if is_appliance and fresh else None
        if not is_appliance or pct is None:
            price_diff_text = "—"
        else:
            rounded = round(pct * 10) / 10
            if rounded == 0:
                price_diff_text = "بدون اختلاف"
            else:
                word = "گران‌تر" if pct > 0 else "ارزان‌تر"
                price_diff_text = f"{_format_percent_magnitude(pct)} {word}"

        # suggested price
        weight = weights.get(top) if top is not None else None
        if fresh:
            if is_appliance:
                raw_suggested = _suggested_price_for(base_price, amount, weight)
            else:
                raw_suggested = _suggested_price_from_daily_change(
                    base_price, competitor.price_change_percent if competitor else None, weight
                )
        else:
            raw_suggested = None
        decrease = (
            float(product.allowed_decrease_percent)
            if product.allowed_decrease_percent is not None
            else None
        )
        increase = (
            float(product.allowed_increase_percent)
            if product.allowed_increase_percent is not None
            else None
        )
        suggested = _apply_price_bounds(base_price, raw_suggested, decrease, increase)
        suggested_text = format_amount(suggested) if suggested is not None else "—"

        suggested_change = _change_percent(base_price, suggested)
        if suggested_change is None:
            suggested_change_text = "—"
        else:
            rounded_c = round(suggested_change * 10) / 10
            if rounded_c == 0:
                suggested_change_text = "بدون تغییر"
            else:
                word = "بیشتر" if suggested_change > 0 else "کمتر"
                suggested_change_text = f"{_format_percent_magnitude(suggested_change)} {word}"

        # brand cell: "brand - subgroup" when both, like table shows both
        brand_parts = [part for part in [brand, product.sub_group_name] if part]
        brand_text = " - ".join(brand_parts) if brand_parts else "—"

        values = {
            "row": format_amount(row_number),
            "name": product.name,
            "sku": product.sku,
            "category": top or "—",
            "brand": brand_text,
            "unit": product.unit_name or "—",
            "price": format_amount(product.price),
            "competitor_price": competitor_price_text,
            "price_diff": price_diff_text,
            "suggested_price": suggested_text,
            "suggested_price_change": suggested_change_text,
            "stock": format_amount(product.stock),
        }
        return [values[col] for col in columns]

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
            _top_group(product.main_group_name) or "",
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
