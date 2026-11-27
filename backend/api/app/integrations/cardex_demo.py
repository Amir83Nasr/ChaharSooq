"""Development/Staging demo cardex — deterministic invoices for every product.

The saved Parsina dumps in `data/` only cover a handful of products and a fixed
date range, so most products show an empty cardex in local development. This
module fabricates Parsina-shaped invoice envelopes for any product and window,
purely from a stable hash of the product and date: no network, no credentials,
and no writes.

It is only called from `ProductCardexService` for the Development and Staging
simulations (see `Settings.resolved_fixture_dir`); live Parsina data and real
Production stay untouched.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import jdatetime  # type: ignore[import-untyped]

from app.models import Product

SALE_CUSTOMERS = (
    "فروشگاه آریا",
    "دیجی‌کالا",
    "فروشگاه پارس",
    "هایپر مارکت مرکزی",
    "مشتری خرد",
)
PURCHASE_SUPPLIERS = (
    "شرکت دیپوینت",
    "بازرگانی آرمان",
    "تأمین‌کننده مرکزی",
    "واردات پرشیا",
)
EVENT_PROBABILITY = {"sale": 0.55, "purchase": 0.45}
BASE_PRICE_TOMAN = 100_000


def _rng(*parts: object) -> random.Random:
    """Stable random stream for one product/kind/day combination."""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))  # noqa: S311 — demo data


def _days(from_date: date, to_date: date) -> Iterator[date]:
    current = from_date
    while current <= to_date:
        yield current
        current += timedelta(days=1)


def _jalali(date_value: date) -> str:
    jalali = jdatetime.date.fromgregorian(date=date_value)  # type: ignore[reportUnknownMemberType]
    return f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}"


def _invoice_id(day: date, kind: str) -> int:
    """Unique per day and direction within a single product cardex."""
    return 900_000_000 + day.toordinal() * 2 + (0 if kind == "sale" else 1)


def _invoice(
    product: Product,
    *,
    kind: str,
    day: date,
    to_date: date,
    rng: random.Random,
) -> dict[str, Any]:
    sale = kind == "sale"
    quantity = rng.randint(1, 12) if sale else rng.randint(2, 20)
    base = max(float(product.price or 0), BASE_PRICE_TOMAN)
    # Sale lines sit at the shelf price; purchases come in below it.
    unit_toman = int(base * (rng.uniform(0.92, 1.08) if sale else rng.uniform(0.74, 0.9)))
    total_rial = unit_toman * quantity * 10
    # Today always produces valid rows so a fresh dialog is never empty.
    cancelled = day != to_date and rng.random() < 0.08
    counterparty = rng.choice(SALE_CUSTOMERS if sale else PURCHASE_SUPPLIERS)
    invoice_id = _invoice_id(day, kind)

    return {
        "id": invoice_id,
        "Number": 1_000 + invoice_id % 9_000,
        "Date": _jalali(day),
        "BuyerName": counterparty,
        "IsCancel": cancelled,
        "isConfirm": True,
        "IsCheckedout": sale,
        "Details": [
            {
                "goodid": product.external_id,
                "goodcode": product.sku,
                "TotalCount": quantity,
                "NetPrice": total_rial,
            }
        ],
    }


def demo_invoices(
    product: Product,
    *,
    kind: str,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    """Parsina-shaped invoices for one product, direction, and date window.

    The same product/day/kind always yields the same invoice, so switching
    between cardex periods shows a consistent history rather than new random
    rows on every request.
    """
    if kind not in ("sale", "purchase"):
        raise ValueError("نوع فاکتور کارتکس نامعتبر است")
    if from_date > to_date:
        return []

    invoices: list[dict[str, Any]] = []
    for day in _days(from_date, to_date):
        rng = _rng(product.id, product.external_id, product.sku, kind, day.isoformat())
        if day != to_date and rng.random() >= EVENT_PROBABILITY[kind]:
            continue
        invoices.append(_invoice(product, kind=kind, day=day, to_date=to_date, rng=rng))
    return invoices
