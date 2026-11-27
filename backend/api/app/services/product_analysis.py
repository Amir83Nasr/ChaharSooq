"""Product-analysis context for the owner-facing AI analyst.

The model never touches the database or Parsina. This service assembles one
bounded, privacy-safe payload from the product row, fresh competitor listings,
and the live 30-day cardex, and computes every number the model may use.

Counterparty names, invoice ids, competitor URLs, and raw invoice lines stay in
Charsooq: the model only sees aggregates and dates. The payload is model-facing,
not an API response — Jalali display dates are pre-formatted and money is
integer Toman so the model never converts either.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import jdatetime  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Product
from app.models.base import utcnow
from app.repositories import ProductAnalysisReportRepository, ProductRepository
from app.schemas import CardexEntryOut, ProductAnalysisReportOut, ProductCardexOut
from app.schemas.competitor import CompetitorListingOut
from app.services.cardex import TEHRAN_OFFSET, ProductCardexService
from app.services.competitor import STORE_LABELS, CompetitorNotFoundError, CompetitorService

# ── POLICY ────────────────────────────────────────────────────────────
ANALYSIS_PERIOD = "30_days"
ANALYSIS_WINDOW_DAYS = 30
RECENT_WINDOW_DAYS = 7
LEAD_TIME_DAYS = 7
SAFETY_DAYS = 3
TARGET_COVER_DAYS = 30
TOP_DAYS_LIMIT = 3
STOCKOUT_HIGH_DAYS = 7
STOCKOUT_MEDIUM_DAYS = 14
OVERSTOCK_DAYS = 45


class ProductAnalysisProductNotFoundError(LookupError):
    """No local product with the requested id."""


# ── FORMATTING HELPERS ────────────────────────────────────────────────


def _jalali(value: date) -> str:
    """Model-facing Jalali date; the prompt turns it into Persian digits."""
    jalali = jdatetime.date.fromgregorian(date=value)  # type: ignore[reportUnknownMemberType]
    return f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}"


def _money(value: Decimal | float | None, currency: str | None = None) -> int | None:
    """Machine amount → integer Toman; only competitor IRR values are divided."""
    if value is None:
        return None
    amount = Decimal(str(value))
    if currency == "IRR":
        amount /= 10
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _quantity(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _margin_percent(price: int, buy_price: int | None) -> float | None:
    if buy_price is None or buy_price <= 0 or price <= 0:
        return None
    return round((price - buy_price) / price * 100, 1)


def _window() -> tuple[date, date]:
    today = (datetime.now(UTC) + TEHRAN_OFFSET).date()
    return today - timedelta(days=ANALYSIS_WINDOW_DAYS - 1), today


# ── SALES ─────────────────────────────────────────────────────────────


def _sale_entries(cardex: ProductCardexOut) -> list[CardexEntryOut]:
    return [entry for entry in cardex.entries if entry.kind == "sale" and not entry.is_cancelled]


def _window_totals(
    entries: Sequence[CardexEntryOut], *, since: date | None
) -> tuple[float, int, int]:
    quantity = 0.0
    amount = 0
    invoices: set[int] = set()
    for entry in entries:
        if since is not None and (entry.invoice_date is None or entry.invoice_date < since):
            continue
        quantity += entry.quantity
        amount += entry.net_price
        invoices.add(entry.invoice_id)
    return quantity, amount, len(invoices)


def _top_days(entries: Sequence[CardexEntryOut]) -> list[dict[str, object]]:
    by_day: dict[date, float] = {}
    for entry in entries:
        if entry.invoice_date is None:
            continue
        by_day[entry.invoice_date] = by_day.get(entry.invoice_date, 0.0) + entry.quantity
    ranked = sorted(by_day.items(), key=lambda item: (-item[1], item[0]))
    return [
        {"date": _jalali(day), "quantity": round(quantity, 3)}
        for day, quantity in ranked[:TOP_DAYS_LIMIT]
    ]


# ── INVENTORY + REORDER ───────────────────────────────────────────────


def _inventory(stock: float, average_daily: float) -> dict[str, object]:
    if average_daily <= 0:
        cover: float | None = None
        risk = "low" if stock > 0 else "unknown"
        overstock = stock > 0
    else:
        raw_cover = stock / average_daily
        cover = round(raw_cover, 1)
        if stock <= 0:
            risk = "high"
            overstock = False
        elif raw_cover < STOCKOUT_HIGH_DAYS:
            risk = "high"
            overstock = False
        elif raw_cover < STOCKOUT_MEDIUM_DAYS:
            risk = "medium"
            overstock = False
        elif raw_cover <= OVERSTOCK_DAYS:
            risk = "low"
            overstock = False
        else:
            risk = "low"
            overstock = True
    return {
        "stock": stock,
        "cover_days": cover,
        "stockout_risk": risk,
        "overstock": overstock,
    }


def _unit_cost(product: Product, cardex: ProductCardexOut) -> int | None:
    """Cost per unit: the stored buy price, else the 30-day purchase average."""
    if product.buy_price is not None and product.buy_price > 0:
        return _money(product.buy_price)
    purchase_quantity = cardex.summary.purchase_quantity
    if purchase_quantity > 0 and cardex.summary.purchase_amount > 0:
        return _money(Decimal(cardex.summary.purchase_amount) / Decimal(str(purchase_quantity)))
    return None


def _reorder(
    *,
    stock: float,
    average_daily: float,
    unit_cost: int | None,
    window_end: date,
) -> dict[str, object]:
    assumptions = [
        f"زمان تأمین {LEAD_TIME_DAYS} روز",
        f"ذخیرهٔ ایمنی {SAFETY_DAYS} روز",
        f"پوشش هدف {TARGET_COVER_DAYS} روز پس از تحویل",
    ]
    if average_daily <= 0:
        return {
            "needed": False,
            "suggested_quantity": 0,
            "order_by": None,
            "capital_toman": 0,
            "assumptions": assumptions,
        }

    cover = stock / average_daily
    if cover >= TARGET_COVER_DAYS:
        return {
            "needed": False,
            "suggested_quantity": 0,
            "order_by": None,
            "capital_toman": 0,
            "assumptions": assumptions,
        }

    days_until_order = max(0, math.floor(cover - LEAD_TIME_DAYS - SAFETY_DAYS))
    target_stock = average_daily * (
        days_until_order + LEAD_TIME_DAYS + SAFETY_DAYS + TARGET_COVER_DAYS
    )
    suggested_quantity = max(0, math.ceil(target_stock - stock))
    capital = suggested_quantity * unit_cost if unit_cost is not None else None
    return {
        "needed": suggested_quantity > 0,
        "suggested_quantity": suggested_quantity,
        "order_by": _jalali(window_end + timedelta(days=days_until_order)),
        "capital_toman": capital,
        "assumptions": assumptions,
    }


# ── MARKET ────────────────────────────────────────────────────────────


def _market(price: int, listings: Sequence[CompetitorListingOut]) -> tuple[dict[str, object], int]:
    competitors: list[dict[str, object]] = []
    prices: list[int] = []
    stale_prices = 0
    for listing in listings:
        if not listing.is_active:
            continue
        amount = _money(listing.effective_price, listing.effective_currency)
        if amount is None or not listing.price_is_fresh:
            # Keep the stale link out of the analysis but report that it exists.
            if listing.fetched_price is not None or listing.manual_price is not None:
                stale_prices += 1
            continue
        prices.append(amount)
        competitors.append(
            {
                "store": listing.store,
                "store_label": STORE_LABELS.get(listing.store, listing.store),
                "price_toman": amount,
                "in_stock": listing.effective_in_stock,
                "fresh": True,
                "change_percent": listing.price_change_percent,
            }
        )

    average = round(sum(prices) / len(prices)) if prices else None
    diff = (
        round((price - average) / average * 100, 1)
        if average is not None and average > 0 and price > 0
        else None
    )
    return (
        {
            "competitors": competitors,
            "avg_price_toman": average,
            "min_price_toman": min(prices) if prices else None,
            "max_price_toman": max(prices) if prices else None,
            "our_diff_percent": diff,
            "sample_size": len(prices),
        },
        stale_prices,
    )


def _price_bounds(
    price: int, *, allowed_decrease: Decimal | None, allowed_increase: Decimal | None
) -> dict[str, int | None]:
    floor = (
        _money(Decimal(price) * (1 - allowed_decrease / 100))
        if allowed_decrease is not None
        else None
    )
    ceiling = (
        _money(Decimal(price) * (1 + allowed_increase / 100))
        if allowed_increase is not None
        else None
    )
    return {"floor_toman": floor, "ceiling_toman": ceiling}


# ── PAYLOAD ───────────────────────────────────────────────────────────


def build_analysis_payload(
    *,
    product: Product,
    cardex: ProductCardexOut,
    listings: Sequence[CompetitorListingOut],
    app_env: str,
) -> dict[str, Any]:
    """One JSON-safe context for the model; every value is precomputed."""
    window = next((period for period in cardex.periods if period.key == ANALYSIS_PERIOD), None)
    from_date, to_date = (window.from_date, window.to_date) if window else _window()

    sales = _sale_entries(cardex)
    quantity_30, amount_30, invoices_30 = _window_totals(sales, since=None)
    recent_start = to_date - timedelta(days=RECENT_WINDOW_DAYS - 1)
    quantity_7, amount_7, invoices_7 = _window_totals(sales, since=recent_start)

    stock = _quantity(product.stock) or 0.0
    average_daily = round(quantity_30 / ANALYSIS_WINDOW_DAYS, 3)
    inventory = _inventory(stock, average_daily)

    price = _money(product.price) or 0
    buy_price = _money(product.buy_price) if product.buy_price and product.buy_price > 0 else None
    unit_cost = _unit_cost(product, cardex)
    margin = _margin_percent(price, buy_price)
    market, stale_prices = _market(price, listings)
    market["price_bounds"] = _price_bounds(
        price,
        allowed_decrease=product.allowed_decrease_percent,
        allowed_increase=product.allowed_increase_percent,
    )
    reorder = _reorder(
        stock=stock,
        average_daily=average_daily,
        unit_cost=unit_cost,
        window_end=to_date,
    )

    notes: list[str] = []
    if not cardex.configured:
        notes.append("اتصال پارسینا تنظیم نشده است؛ داده فروش در دسترس نیست.")
    elif not sales:
        notes.append("در ۳۰ روز گذشته فروشی برای این کالا ثبت نشده است.")
    if app_env == "development" or get_settings().resolved_fixture_dir is not None:
        notes.append("داده فروش شبیه‌سازی‌شده است و ممکن است نمایشی باشد.")
    notes.append("داده فروش ۳۰ روز قبل در دسترس نیست؛ مقایسه با دورهٔ قبل ممکن نیست.")
    notes.append("میانگین فروش دسته در دسترس نیست.")
    if unit_cost is None:
        notes.append("قیمت خرید ثبت نشده است؛ سرمایهٔ لازم برای خرید قابل برآورد نیست.")
    if stale_prices:
        notes.append(f"{stale_prices} قیمت رقیب کهنه است و در تحلیل بازار لحاظ نشد.")

    return {
        "context_version": 1,
        "period": {
            "days": ANALYSIS_WINDOW_DAYS,
            "from": _jalali(from_date),
            "to": _jalali(to_date),
        },
        "product": {
            "name": product.name,
            "sku": product.sku,
            "section": product.top_group,
            "group": product.main_group_name,
            "unit": product.unit_name,
            "price_toman": price,
            "buy_price_toman": buy_price,
            "margin_percent": margin,
            "stock": stock,
            "warehouse_stock": _quantity(product.ware_remain),
            "is_active": product.is_active,
        },
        "sales": {
            "available": cardex.configured,
            "source": "parsina_cardex",
            "last_7_days": {
                "quantity": round(quantity_7, 3),
                "amount_toman": amount_7,
                "invoice_count": invoices_7,
            },
            "last_30_days": {
                "quantity": round(quantity_30, 3),
                "amount_toman": amount_30,
                "invoice_count": invoices_30,
            },
            "previous_30_days": None,
            "change_30d_percent": None,
            "avg_daily_30d": average_daily,
            "top_days": _top_days(sales),
            "category_avg_30d": None,
        },
        "inventory": inventory,
        "reorder": reorder,
        "market": market,
        "data_quality": {
            "sales_configured": cardex.configured,
            "stale_prices": stale_prices,
            "notes": notes,
        },
    }


class ProductAnalysisService:
    """Fetches the facts for one product; the route only streams the model."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def build(self, product_id: int) -> dict[str, Any]:
        product = ProductRepository(self._session).get(product_id)
        if product is None:
            raise ProductAnalysisProductNotFoundError("کالا یافت نشد")

        try:
            listings = CompetitorService(self._session).list_product_listings(product_id)
        except CompetitorNotFoundError:
            # The product exists, so this is only a stale lookup edge case.
            listings = []

        cardex = ProductCardexService(self._session).get(
            product_id=product_id, period=ANALYSIS_PERIOD
        )
        return build_analysis_payload(
            product=product,
            cardex=cardex,
            listings=listings,
            app_env=get_settings().app_env,
        )


class ProductAnalysisReportService:
    """Reads and writes the latest saved report for one product.

    The caller owns the transaction: request handlers commit through their
    dependency, and the streaming callback commits its own short session.
    """

    def __init__(self, session: Session) -> None:
        self._repo = ProductAnalysisReportRepository(session)

    def get(self, product_id: int) -> ProductAnalysisReportOut | None:
        row = self._repo.get(product_id)
        return ProductAnalysisReportOut.model_validate(row) if row is not None else None

    def save(self, product_id: int, *, content: str, model_id: str) -> ProductAnalysisReportOut:
        row = self._repo.upsert(
            product_id,
            content=content,
            model_id=model_id,
            generated_at=utcnow(),
        )
        return ProductAnalysisReportOut.model_validate(row)

    def delete(self, product_id: int) -> bool:
        return self._repo.delete(product_id)
