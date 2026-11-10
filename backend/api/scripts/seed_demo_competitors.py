"""Fill a development or staging database with demo competitor prices.

Never run against production. Every active product gets the competitor links
its group uses in the table — Digikala/Technolife for appliances, Sofa for
furniture, DigiFresh for carpets — plus a fresh price and two daily
observations, so the products table shows competitor price, price difference,
suggested price and daily change instead of empty cells.

Products rotate through four suggested-price scenarios (stable per product
`external_id`, falling back to SKU) so the demo covers every clamp branch: a
price below the floor, one above the ceiling, one that stays inside the
bounds, and one with no bounds at all. Keying on the synced product identity
instead of the database primary key keeps dev and staging showing the same
demo prices even though the two databases assign different ids. The
floor/ceiling rows use a tight demo clamp so the competitor price really lands
outside it; the no-bounds row keeps an out-of-range suggestion unclamped.
Bounds this script wrote earlier are refreshed to the new scenario, while an
admin's own clamp (any other value) is kept.

Rows created here carry a `demo-` URL path, which is what makes the script
idempotent and safe to re-run: demo rows (and their observations) are
refreshed, while real/manual links and their observations are never touched
(products that already have a real link are skipped). Run via
`make db-seed-demo` (which imports `data/parsina.csv` first) or, against a
staging database explicitly, `make db-seed-demo-staging` (passes `--staging`).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.models import (
    CompetitorListing,
    CompetitorPriceObservation,
    Product,
    SuggestedPriceFormula,
)
from scripts.common import is_demo_competitor_url

STORE_URLS = {
    "digikala": "https://www.digikala.com/product/demo-{product_id}/",
    "technolife": "https://www.technolife.ir/product/demo-{product_id}/",
    "sofa": "https://www.sofamobl.com/product/demo-{product_id}/",
    "digifresh": "https://www.digifarsh.com/product/demo-{product_id}/",
}
APPLIANCE_STORES = ("digikala", "technolife")
TARGET_WEIGHTS = {
    "فرش": Decimal("0.4000"),
    "مبلمان": Decimal("0.5000"),
    "لوازم خانگی": Decimal("0.2000"),
}
TOMAN = Decimal("1")

# Suggested-price scenarios, picked from the synced product identity so a
# re-run keeps the same shape in every environment (dev and staging assign
# different database ids to the same catalog row).
SCENARIOS = ("floor", "ceiling", "inside", "no_bounds")
CLAMP_SCENARIOS = frozenset({"floor", "ceiling"})
NO_BOUNDS_SCENARIO = "no_bounds"
# Tight enough that a ±12% competitor move (or ±5% daily change) lands outside.
CLAMP_BOUND_PERCENT = Decimal("1.50")


@dataclass(frozen=True)
class SeedResult:
    created: int
    refreshed: int
    observations: int
    weights: int
    bounds: int


def stores_for(product: Product) -> tuple[str, ...]:
    """Stores the products table expects for this product's top group."""
    name = (product.main_group_name or "").strip()
    if name.startswith("فرش"):
        return ("digifresh",)
    if name.startswith("مبلمان"):
        return ("sofa",)
    return APPLIANCE_STORES


def _demo_url(store: str, product_id: int) -> str:
    return STORE_URLS[store].format(product_id=product_id)


def _offset(seed: str) -> Decimal:
    """Deterministic value in [-1, 1] so re-runs keep the same demo prices."""
    value = int.from_bytes(sha256(seed.encode()).digest()[:4], "big")
    return Decimal(value % 2001 - 1000) / Decimal(1000)


def stable_seed(product: Product) -> str:
    """Identity that is identical in every environment for the same catalog row.

    Database ids are assigned by insert order, so dev and staging hold the same
    product under different ids. `external_id` is the synced Parsina key; manual
    rows are matched by SKU (see `sync_dev_to_prod`), so both are stable keys.
    """
    if product.external_id is not None:
        return f"ext:{product.external_id}"
    return f"sku:{product.sku}"


def _seed_bucket(product: Product) -> int:
    """Stable integer for scenario rotation."""
    digest = sha256(stable_seed(product).encode()).digest()
    return int.from_bytes(digest[:4], "big")


def demo_scenario(product: Product) -> str:
    """Stable clamp scenario for this product (see SCENARIOS)."""
    return SCENARIOS[_seed_bucket(product) % len(SCENARIOS)]


def demo_prices(product: Product, store: str) -> tuple[Decimal, Decimal]:
    """Today's competitor price and its daily change percent (IRR-free toman)."""
    base = Decimal(product.price)
    url_seed = f"{stable_seed(product)}:{store}"
    scenario = demo_scenario(product)
    if scenario == "inside":
        # Competitor prices sit within ±12% of our price, so the diff column has
        # both "cheaper" and "more expensive" rows (and a few "no difference").
        factor = _offset(f"price:{url_seed}") * Decimal("0.12")
        # Furniture/carpet suggestions follow the linked product's daily change;
        # keep it between -5% and +5%, never exactly zero, so the demo differs.
        change = _offset(f"change:{url_seed}") * Decimal("5")
        if change.copy_abs() < Decimal("0.5"):
            change = Decimal("0.5") if change >= 0 else Decimal("-0.5")
    else:
        # Push the competitor to a clear edge so the suggested price really
        # crosses the tight demo clamp (floor/ceiling) or visibly stays
        # unclamped when the product has no bounds.
        direction = Decimal(1) if scenario == "ceiling" else Decimal(-1)
        factor = direction * Decimal("0.12")
        change = direction * Decimal("5")
    price = (base * (Decimal(1) + factor)).quantize(TOMAN, rounding=ROUND_HALF_UP)
    return max(price, Decimal(1)), change.quantize(Decimal("0.1"))


def _previous_price(today: Decimal, change_percent: Decimal) -> Decimal:
    previous = today / (Decimal(1) + change_percent / Decimal(100))
    return max(previous.quantize(TOMAN, rounding=ROUND_HALF_UP), Decimal(1))


def _half_percent(low: Decimal, high: Decimal, seed: str) -> Decimal:
    """Deterministic bound in `[low, high]`, rounded to 0.5%."""
    raw = (_offset(seed) + 1) / 2
    return ((low + raw * (high - low)) * 2).quantize(Decimal(1)) / 2


def demo_bounds(product: Product) -> tuple[Decimal, Decimal]:
    """Floor/ceiling percentages for the demo rows with an "inside" outcome."""
    seed = stable_seed(product)
    decrease = _half_percent(Decimal(5), Decimal(15), f"floor:{seed}")
    increase = _half_percent(Decimal(8), Decimal("18"), f"ceiling:{seed}")
    return decrease.quantize(Decimal("0.01")), increase.quantize(Decimal("0.01"))


def _legacy_scenario_bounds(product: Product) -> tuple[Decimal | None, Decimal | None]:
    """Bounds the previous id-keyed seed may have written for this row.

    Used once to recognise (and refresh) demo clamps written before the switch
    to `stable_seed`, so re-seeding converges instead of mistaking them for an
    admin's own clamp.
    """
    scenario = SCENARIOS[(product.id - 1) % len(SCENARIOS)]
    if scenario in CLAMP_SCENARIOS:
        return CLAMP_BOUND_PERCENT, CLAMP_BOUND_PERCENT
    if scenario == NO_BOUNDS_SCENARIO:
        return None, None
    decrease = _half_percent(Decimal(5), Decimal(15), f"floor:{product.id}")
    increase = _half_percent(Decimal(8), Decimal("18"), f"ceiling:{product.id}")
    return decrease.quantize(Decimal("0.01")), increase.quantize(Decimal("0.01"))


def scenario_bounds(product: Product, scenario: str) -> tuple[Decimal | None, Decimal | None]:
    """Target clamp for a product's scenario.

    Floor/ceiling rows get a tight clamp so the demo competitor price lands
    outside it; "inside" keeps the looser random clamp; "no_bounds" stays
    unlimited so the unclamped price is visible.
    """
    if scenario in CLAMP_SCENARIOS:
        return CLAMP_BOUND_PERCENT, CLAMP_BOUND_PERCENT
    if scenario == NO_BOUNDS_SCENARIO:
        return None, None
    return demo_bounds(product)


def _seed_owns_bound(
    current: Decimal | None,
    demo_default: Decimal,
    target: Decimal | None,
    legacy: Decimal | None,
) -> bool:
    """True when an unset bound or one this seed wrote can be refreshed."""
    if current is None or current == demo_default or current == target:
        return True
    # One-time migration from the old id-keyed seed.
    return current == legacy


def seed_demo_competitors(session: Session, *, now: datetime | None = None) -> SeedResult:
    now = now or datetime.now(UTC)
    yesterday = now - timedelta(days=1)

    products = session.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.id)
    ).all()

    existing = {
        (listing.product_id, listing.store): listing
        for listing in session.scalars(select(CompetitorListing))
    }
    # Products with real/manual links are somebody's actual work: never mix
    # fake demo prices into them.
    real_product_ids = {
        product_id
        for (product_id, _), listing in existing.items()
        if not is_demo_competitor_url(listing.url)
    }
    seedable = [
        (product, store)
        for product in products
        if product.id not in real_product_ids
        for store in stores_for(product)
    ]
    created = 0
    for product, store in seedable:
        if (product.id, store) in existing:
            continue
        listing = CompetitorListing(
            product_id=product.id,
            store=store,
            url=_demo_url(store, product.id),
            is_active=True,
            fetched_currency="IRT",
            manual_currency=None,
        )
        session.add(listing)
        existing[(product.id, store)] = listing
        created += 1
    session.flush()

    demo_rows = [
        (product, existing[(product.id, store)])
        for product, store in seedable
        if is_demo_competitor_url(existing[(product.id, store)].url)
    ]
    # Demo history is regenerated, not accumulated: the two observations below
    # are deterministic from the product identity, so every environment shows
    # the same competitor price and daily change after a re-seed.
    if demo_rows:
        session.execute(
            delete(CompetitorPriceObservation).where(
                CompetitorPriceObservation.listing_id.in_([listing.id for _, listing in demo_rows])
            )
        )

    refreshed = 0
    observations_added = 0
    bounds_added = 0
    for product, listing in demo_rows:
        price, change = demo_prices(product, listing.store)
        listing.status = "success"
        listing.fetched_price = price
        listing.fetched_currency = "IRT"
        listing.fetched_in_stock = True
        listing.manual_price = None
        listing.manual_currency = None
        listing.manual_in_stock = None
        listing.manual_updated_at = None
        listing.last_checked_at = now
        listing.last_success_at = now
        listing.last_error = None
        listing.is_active = True
        refreshed += 1

        # Suggested-price clamp: refresh blanks and values this seed wrote
        # earlier (including the old id-keyed defaults) to the product's
        # scenario, but never replace an admin's own clamp.
        scenario = demo_scenario(product)
        decrease, increase = scenario_bounds(product, scenario)
        default_decrease, default_increase = demo_bounds(product)
        legacy_decrease, legacy_increase = _legacy_scenario_bounds(product)
        if _seed_owns_bound(
            product.allowed_decrease_percent, default_decrease, decrease, legacy_decrease
        ):
            if product.allowed_decrease_percent != decrease:
                product.allowed_decrease_percent = decrease
                bounds_added += 1
        if _seed_owns_bound(
            product.allowed_increase_percent, default_increase, increase, legacy_increase
        ):
            if product.allowed_increase_percent != increase:
                product.allowed_increase_percent = increase
                bounds_added += 1

        session.add(
            CompetitorPriceObservation(
                listing_id=listing.id,
                price=price,
                currency="IRT",
                in_stock=True,
                observed_at=now,
            )
        )
        session.add(
            CompetitorPriceObservation(
                listing_id=listing.id,
                price=_previous_price(price, change),
                currency="IRT",
                in_stock=True,
                observed_at=yesterday,
            )
        )
        observations_added += 2

    weights = {row.top_group for row in session.scalars(select(SuggestedPriceFormula))}
    weights_added = 0
    for top_group, weight in TARGET_WEIGHTS.items():
        if top_group in weights:
            continue
        session.add(SuggestedPriceFormula(top_group=top_group, weight=weight))
        weights_added += 1

    session.commit()
    return SeedResult(
        created=created,
        refreshed=refreshed,
        observations=observations_added,
        weights=weights_added,
        bounds=bounds_added,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill a development or staging database with demo competitor prices."
    )
    parser.add_argument(
        "--staging",
        action="store_true",
        help=(
            "Allow writing demo data to a database flagged APP_ENV=production. "
            "Only use this against a staging database, never production."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.is_production and not args.staging:
        print(
            "refusing to seed demo competitor prices into a production database",
            file=sys.stderr,
        )
        return 1
    if settings.is_production:
        print("staging mode: writing demo competitor prices to the staging database")

    with Session(get_engine()) as session:
        if session.scalar(select(Product.id).limit(1)) is None:
            print(
                "no products found; run `make db-seed-parsina` first",
                file=sys.stderr,
            )
            return 1
        result = seed_demo_competitors(session)

    print(
        f"demo competitor prices seeded: {result.created} links created, "
        f"{result.refreshed} refreshed, {result.observations} observations added, "
        f"{result.weights} suggested-price weights added, "
        f"{result.bounds} price bounds written"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
