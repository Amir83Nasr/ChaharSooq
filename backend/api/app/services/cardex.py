"""Product cardex — purchase/sale history from Parsina invoices.

Parsina has no per-product report endpoint: the invoice list only returns
headers, so the product lines live in each invoice's `Details[]`. This service
loads that list for the four supported windows, then reads details only for
invoices whose lines mention the product's `goodId` (or its SKU).

Parsina dates are Jalali strings (`1404/01/01`); dates crossing the API boundary
stay ISO/UTC machine values, and per-line rial amounts become integer toman
exactly like the catalog sync (ADR 003).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, cast

import jdatetime  # type: ignore[import-untyped]

from app.core.config import ParsinaSettings, get_parsina_settings, get_settings
from app.integrations.cardex_fixture import CardexFixtureSource
from app.integrations.parsina import (
    ParsinaClient,
    ParsinaError,
    field,
    integer,
)
from app.models import Product
from app.repositories import ProductRepository
from app.schemas import (
    CardexEntryOut,
    CardexPeriod,
    CardexSummaryOut,
    PricingMode,
    ProductCardexOut,
)
from app.services.parsina_connection import resolve_parsina_settings

if TYPE_CHECKING:
    from httpx import BaseTransport
    from sqlalchemy.orm import Session

RIALS_PER_TOMAN = 10
TEHRAN_OFFSET = timedelta(hours=3, minutes=30)
log = logging.getLogger("charsooq.cardex")
PERIOD_DAYS = (
    ("today", "امروز", 1),
    ("3_days", "۳ روز گذشته", 3),
    ("7_days", "۷ روز گذشته", 7),
    ("30_days", "۳۰ روز گذشته", 30),
)


class CardexProductNotFoundError(LookupError):
    """No local product with the requested id."""


def _decimal(raw: Any) -> Decimal:
    if raw is None or raw == "":
        return Decimal("0")
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _toman(raw: Any) -> int:
    """Parsina rial amount → integer toman; round to the nearest toman."""
    return int((_decimal(raw) / RIALS_PER_TOMAN).quantize(Decimal("1")))


def _invoice_date(raw: Any) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()
    for sep in ("/", "-"):
        parts = text.split(sep)
        if len(parts) == 3:
            try:
                return jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2])).togregorian()
            except ValueError:
                return None
    return None


def _jalali(date_value: date) -> str:
    jalali = jdatetime.date.fromgregorian(date=date_value)  # type: ignore[reportUnknownMemberType]
    return f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}"


def available_periods(*, today: date) -> list[CardexPeriod]:
    """The four selectable windows, with inclusive ISO bounds in Tehran time."""
    return [
        CardexPeriod(
            key=key,
            label=label,
            from_date=today - timedelta(days=days - 1),
            to_date=today,
        )
        for key, label, days in PERIOD_DAYS
    ]


class ProductCardexService:
    def __init__(
        self,
        session: Session,
        *,
        settings: ParsinaSettings | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._settings = settings
        self._transport = transport

    def get(self, *, product_id: int, period: str) -> ProductCardexOut:
        product = self._products.get(product_id)
        if product is None:
            raise CardexProductNotFoundError("کالا یافت نشد")

        # Cardex is read-only: configuration stays the same as for catalog sync.
        # An unconfigured connection is a valid empty report — the default tab
        # must open cleanly and explain the state instead of showing an error.
        if self._settings is not None or self._transport is not None:
            settings = self._settings or get_parsina_settings()
        else:
            settings = resolve_parsina_settings(self._session).settings

        today = (datetime.now(UTC) + TEHRAN_OFFSET).date()
        periods = available_periods(today=today)
        window = next((p for p in periods if p.key == period), None)
        if window is None:
            raise ValueError("بازه کارتکس نامعتبر است")

        entries: list[CardexEntryOut] = []
        # Development reads the saved Parsina dumps so the default tab shows a
        # realistic cardex without credentials; production uses the live API.
        if get_settings().app_env == "development":
            fixture = CardexFixtureSource()
            if fixture.is_configured:
                for kind in ("sale", "purchase"):
                    entries.extend(
                        self._fixture_entries(
                            fixture,
                            product,
                            kind=kind,
                            from_date=window.from_date,
                            to_date=window.to_date,
                        )
                    )
        elif settings.is_configured:
            with ParsinaClient(settings, transport=self._transport) as client:
                for kind in ("sale", "purchase"):
                    entries.extend(
                        self._entries(
                            client,
                            product,
                            kind=kind,
                            from_date=_jalali(window.from_date),
                            to_date=_jalali(window.to_date),
                        )
                    )
        entries.sort(key=lambda entry: (entry.invoice_date or date.min, entry.invoice_id))

        # Cancelled invoices stay visible in the table but never count toward
        # the real purchase/sale totals — that is what a cardex is for.
        active = [entry for entry in entries if not entry.is_cancelled]
        summary = CardexSummaryOut(
            purchase_quantity=sum(e.quantity for e in active if e.kind == "purchase"),
            purchase_amount=sum(e.net_price for e in active if e.kind == "purchase"),
            sale_quantity=sum(e.quantity for e in active if e.kind == "sale"),
            sale_amount=sum(e.net_price for e in active if e.kind == "sale"),
        )
        return ProductCardexOut(
            product_id=product.id,
            sku=product.sku,
            period=window.key,
            periods=periods,
            summary=summary,
            entries=entries,
            configured=settings.is_configured
            or (get_settings().app_env == "development" and CardexFixtureSource().is_configured),
            pricing_mode=cast("PricingMode | None", product.pricing_mode),
        )

    def _fixture_entries(
        self,
        fixture: CardexFixtureSource,
        product: Product,
        *,
        kind: str,
        from_date: date,
        to_date: date,
    ) -> list[CardexEntryOut]:
        entries: list[CardexEntryOut] = []
        for invoice in fixture.invoices(kind=kind, from_date=from_date, to_date=to_date):
            invoice_id = integer(field(invoice, "id"))
            if invoice_id is None:
                continue
            details = fixture.details(kind=kind, invoice_id=invoice_id)
            entries.extend(self._build_entries(product, invoice, details, kind=kind))
        return entries

    def _entries(
        self,
        client: ParsinaClient,
        product: Product,
        *,
        kind: str,
        from_date: str,
        to_date: str,
    ) -> list[CardexEntryOut]:
        entries: list[CardexEntryOut] = []
        try:
            invoices = client.invoices(kind=kind, from_date=from_date, to_date=to_date)
        except ParsinaError:
            # One direction failing must not hide the other; the UI still shows
            # a partial report instead of an empty error page.
            log.warning("cardex %s invoice list unavailable", kind)
            return entries

        for invoice in invoices:
            invoice_id = integer(field(invoice, "id"))
            if invoice_id is None:
                continue
            try:
                details = client.invoice_details(kind=kind, invoice_id=invoice_id)
            except ParsinaError:
                log.warning("cardex %s invoice %s details unavailable", kind, invoice_id)
                continue
            entries.extend(self._build_entries(product, invoice, details, kind=kind))
        return entries

    def _build_entries(
        self,
        product: Product,
        invoice: dict[str, Any],
        details: list[dict[str, Any]],
        *,
        kind: str,
    ) -> list[CardexEntryOut]:
        good_id = product.external_id
        sku = (product.sku or "").strip()
        matched = [line for line in details if self._matches(line, good_id=good_id, sku=sku)]
        if not matched:
            return []

        # The list endpoints differ from the detail endpoints: `buyFactor`
        # carries BuyerName while `BuyFactor/{id}` carries SellerName.
        counterparty_value = (
            field(invoice, "BuyerName", "SellerName")
            if kind == "purchase"
            else field(invoice, "BuyerName")
        )
        counterparty = str(counterparty_value).strip() if counterparty_value else None
        cancelled = field(invoice, "IsCancel") is True
        confirmed = field(invoice, "isConfirm") is True
        checkedout = field(invoice, "IsCheckedout") is True
        return [
            CardexEntryOut(
                kind=kind,
                invoice_id=integer(field(invoice, "id")) or 0,
                invoice_number=integer(field(invoice, "Number")),
                invoice_date=_invoice_date(field(invoice, "Date")),
                counterparty=counterparty,
                quantity=float(_decimal(field(line, "TotalCount", "Count"))),
                net_price=_toman(field(line, "NetPrice", "PriceAfterOff", "TotalPrice")),
                is_cancelled=cancelled,
                is_confirmed=confirmed,
                is_checkedout=checkedout if kind == "sale" else False,
            )
            for line in matched
        ]

    @staticmethod
    def _matches(line: dict[str, Any], *, good_id: int | None, sku: str) -> bool:
        line_id = integer(field(line, "goodid", "goodId"))
        if good_id is not None and line_id == good_id:
            return True
        code = field(line, "goodcode", "goodCode")
        return bool(sku and code is not None and str(code).strip() == sku)
