"""Copy data from the local dev Postgres into a Staging database.

The historical name is kept because `make db-sync-dev-to-staging` and the
existing runbook still call this module. It no longer targets Production:
the CLI requires `DEPLOYMENT_ENV=staging` and refuses Production and unknown
identities before it opens a connection or reads a destination URL.

Usage (from repo root):
    make db-sync-dev-to-staging                # prompts for confirmation
    make db-sync-dev-to-staging YES=1          # non-interactive
    make db-sync-dev-to-staging YES=1 FULL=1   # also deactivate extra rows

Or directly:
    DEPLOYMENT_ENV=staging uv run --project backend/api \\
        --env-file backend/api/.env.staging \\
        python backend/api/scripts/sync_dev_to_prod.py \\
        [--dev-url ...] [--prod-url ...] [--yes] [--mirror]

`--prod-url` is the legacy flag name for the destination database URL. Only a
Staging destination is allowed.

The sync is non-destructive and upsert-based:

  * categories are matched by name and their dev ids are remapped;
  * settings, suggested-price weights, and the Parsina sync-state row are
    updated in place;
  * products are matched by `external_id` (manual rows by SKU), so destination
    primary keys never change and rows are never deleted; admin markers
    (`pinned`, `pricing_mode`) are copied with the catalog;
  * competitor listings are copied for products that do not have that
    `(product, store)` link on the destination yet. Existing destination links
    are left untouched, so a local copy can never erase staging work;
  * the observation history of those real links is mirrored;
  * demo links from `make db-seed-demo` are skipped, so fake dev prices never
    reach staging;
  * per-product suggested-price bounds are admin settings and stay
    environment-local (copied fields never include them).

`--mirror` additionally soft-deactivates destination products that do not
exist in the dev catalog, so Staging ends up with exactly the dev product set.

It never touches admins / admin_sessions / ai_config / backups /
alembic_version and never deletes products, categories, links, or reports.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_, create_engine, select, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.deployment import STAGING, enforce_deployment_env
from app.models import (
    Category,
    CompetitorListing,
    CompetitorPriceObservation,
    ParsinaSyncState,
    Product,
    Setting,
    SuggestedPriceFormula,
)
from app.models.parsina import SYNC_STATE_ID
from scripts.common import is_demo_competitor_url

DEFAULT_DEV_URL = "postgresql+psycopg://charsooq:charsooq@localhost:5433/charsooq"


def _sqlalchemy_url(url: str) -> str:
    """Accept psycopg-style URLs from the environment and pin the driver."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url


def _safe_url(url: str) -> str:
    """Render a database URL for terminal output with its password masked."""
    try:
        return make_url(_sqlalchemy_url(url)).render_as_string(hide_password=True)
    except Exception:  # noqa: BLE001 — an unparsable URL must not echo secrets either
        return "<invalid database url>"


def _engine(url: str) -> Engine:
    return create_engine(_sqlalchemy_url(url), pool_pre_ping=True)


def _sync_categories(dev: Session, prod: Session) -> dict[int, int]:
    """Upsert categories by unique name; return dev id → prod id."""
    mapping: dict[int, int] = {}
    for source in dev.scalars(select(Category).order_by(Category.id)):
        target = prod.scalar(select(Category).where(Category.name == source.name))
        if target is None:
            target = Category(name=source.name, created_at=source.created_at)
            prod.add(target)
            prod.flush()
        mapping[source.id] = target.id
    return mapping


def _sync_settings(dev: Session, prod: Session) -> int:
    count = 0
    for source in dev.scalars(select(Setting).order_by(Setting.key)):
        target = prod.get(Setting, source.key)
        if target is None:
            prod.add(Setting(key=source.key, value=source.value))
        else:
            target.value = source.value
        count += 1
    return count


def _sync_suggested_price_formulas(dev: Session, prod: Session) -> int:
    """Copy the per-section weights both pricing formulas share."""
    count = 0
    for source in dev.scalars(
        select(SuggestedPriceFormula).order_by(SuggestedPriceFormula.top_group)
    ):
        target = prod.get(SuggestedPriceFormula, source.top_group)
        if target is None:
            prod.add(SuggestedPriceFormula(top_group=source.top_group, weight=source.weight))
        else:
            target.weight = source.weight
        count += 1
    return count


def _sync_parsina_state(dev: Session, prod: Session) -> None:
    """Copy counters/timestamps but never the lock fields of a running job."""
    source = dev.get(ParsinaSyncState, SYNC_STATE_ID)
    if source is None:
        return
    target = prod.get(ParsinaSyncState, SYNC_STATE_ID)
    if target is None:
        target = ParsinaSyncState(id=SYNC_STATE_ID)
        prod.add(target)
    target.last_attempt_at = source.last_attempt_at
    target.last_success_at = source.last_success_at
    target.last_error = source.last_error
    target.last_processed = source.last_processed
    target.last_created = source.last_created
    target.last_updated = source.last_updated
    target.last_deactivated = source.last_deactivated
    target.last_skipped = source.last_skipped


def _destination_products(
    prod: Session,
) -> tuple[dict[int, Product], dict[str, Product]]:
    """Load the destination catalog once: external ids plus manual rows by SKU.

    A per-source-row SELECT would round-trip to the remote database for every
    row (and autoflush pending inserts between them); the sync materializes the
    destination set instead and lets one flush batch the writes.
    """
    by_external_id: dict[int, Product] = {}
    manual_by_sku: dict[str, Product] = {}
    for product in prod.scalars(select(Product)):
        if product.external_id is not None:
            by_external_id[product.external_id] = product
        else:
            manual_by_sku[product.sku] = product
    return by_external_id, manual_by_sku


def _assign_product(target: Product, source: Product, category_id: int | None) -> None:
    target.external_id = source.external_id
    target.name = source.name
    target.sku = source.sku
    target.price = source.price
    target.stock = source.stock
    target.category_id = category_id
    target.main_group_id = source.main_group_id
    target.sub_group_id = source.sub_group_id
    target.main_group_name = source.main_group_name
    target.sub_group_name = source.sub_group_name
    target.unit_id = source.unit_id
    target.unit_name = source.unit_name
    target.weight = source.weight
    target.is_special = source.is_special
    target.is_active = source.is_active
    target.pinned = source.pinned
    target.pricing_mode = source.pricing_mode
    target.buy_price = source.buy_price
    target.sale_pack_price = source.sale_pack_price
    target.sale_box_price = source.sale_box_price
    target.use_price = source.use_price
    target.discount = source.discount
    target.extra = source.extra
    target.number_in_box = source.number_in_box
    target.number_in_pack = source.number_in_pack
    target.ware_remain = source.ware_remain
    target.synced_at = source.synced_at


def _sync_products(dev: Session, prod: Session, category_map: dict[int, int]) -> dict[int, int]:
    """Upsert products without changing destination ids; return dev id → prod id."""
    by_external_id, manual_by_sku = _destination_products(prod)
    pairs: list[tuple[int, Product]] = []
    for source in dev.scalars(select(Product).order_by(Product.id)):
        if source.external_id is not None:
            target = by_external_id.get(source.external_id)
        else:
            target = manual_by_sku.get(source.sku)
        if target is None:
            target = Product(created_at=source.created_at)
            prod.add(target)
            if source.external_id is not None:
                by_external_id[source.external_id] = target
            else:
                manual_by_sku[source.sku] = target
        _assign_product(
            target,
            source,
            category_map.get(source.category_id) if source.category_id is not None else None,
        )
        pairs.append((source.id, target))
    # One flush assigns ids to new rows; existing rows keep their ids.
    prod.flush()
    return {source_id: target.id for source_id, target in pairs}


def _sync_competitor_listings(dev: Session, prod: Session, product_map: dict[int, int]) -> int:
    """Add missing links only; never overwrite or delete a destination link.

    Demo links from `make db-seed-demo` stay local — they are fake prices and
    must never reach staging.
    """
    existing = {
        (listing.product_id, listing.store): listing
        for listing in prod.scalars(select(CompetitorListing))
    }
    added = 0
    for source in dev.scalars(select(CompetitorListing).order_by(CompetitorListing.id)):
        if is_demo_competitor_url(source.url):
            continue
        product_id = product_map.get(source.product_id)
        if product_id is None:
            continue
        if (product_id, source.store) in existing:
            continue
        listing = CompetitorListing(
            product_id=product_id,
            store=source.store,
            url=source.url,
            is_active=source.is_active,
            status=source.status,
            fetched_price=source.fetched_price,
            fetched_currency=source.fetched_currency,
            fetched_in_stock=source.fetched_in_stock,
            manual_price=source.manual_price,
            manual_currency=source.manual_currency,
            manual_in_stock=source.manual_in_stock,
            manual_updated_at=source.manual_updated_at,
            last_checked_at=source.last_checked_at,
            last_success_at=source.last_success_at,
            last_error=source.last_error,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )
        prod.add(listing)
        existing[(product_id, source.store)] = listing
        added += 1
    return added


def _sync_competitor_observations(dev: Session, prod: Session, product_map: dict[int, int]) -> int:
    """Mirror the observation history of copied real links; demo rows stay local."""
    # Flush the links created in the previous step so they carry their ids.
    prod.flush()
    listings = {
        (listing.product_id, listing.store): listing
        for listing in prod.scalars(select(CompetitorListing))
    }
    existing = {
        (observation.listing_id, observation.observed_at): observation
        for observation in prod.scalars(select(CompetitorPriceObservation))
    }
    added = 0
    for source_listing in dev.scalars(select(CompetitorListing).order_by(CompetitorListing.id)):
        if is_demo_competitor_url(source_listing.url):
            continue
        product_id = product_map.get(source_listing.product_id)
        if product_id is None:
            continue
        target_listing = listings.get((product_id, source_listing.store))
        if target_listing is None:
            continue
        for source in dev.scalars(
            select(CompetitorPriceObservation).where(
                CompetitorPriceObservation.listing_id == source_listing.id
            )
        ):
            target = existing.get((target_listing.id, source.observed_at))
            if target is None:
                prod.add(
                    CompetitorPriceObservation(
                        listing_id=target_listing.id,
                        price=source.price,
                        currency=source.currency,
                        in_stock=source.in_stock,
                        observed_at=source.observed_at,
                    )
                )
                added += 1
            else:
                target.price = source.price
                target.currency = source.currency
                target.in_stock = source.in_stock
    return added


def _deactivate_missing_products(dev: Session, prod: Session) -> int:
    """Soft-deactivate synced destination rows absent from the dev catalog.

    ``--mirror`` only: no row is deleted, so links and ids survive a later sync
    that brings the product back. Manual products (``external_id`` NULL) are
    staging-side admin work and are never touched; a dev row with
    ``is_active=False`` is deactivated by the product upsert itself.
    """
    external_ids = {
        product.external_id
        for product in dev.scalars(select(Product))
        if product.external_id is not None
    }
    if external_ids:
        condition = and_(Product.external_id.is_not(None), Product.external_id.not_in(external_ids))
    else:
        condition = Product.external_id.is_not(None)

    result = prod.execute(
        update(Product).where(Product.is_active.is_(True), condition).values(is_active=False)
    )
    # ORM typing exposes the cursor's rowcount only on CursorResult.
    return int(getattr(result, "rowcount", 0) or 0)


def sync(dev_url: str, prod_url: str, *, mirror: bool = False) -> dict[str, int]:
    """Run one non-destructive sync and return per-table counters."""
    dev_engine = _engine(dev_url)
    prod_engine = _engine(prod_url)
    try:
        with Session(dev_engine) as dev, Session(prod_engine) as prod:
            category_map = _sync_categories(dev, prod)
            settings = _sync_settings(dev, prod)
            formulas = _sync_suggested_price_formulas(dev, prod)
            _sync_parsina_state(dev, prod)
            product_map = _sync_products(dev, prod, category_map)
            listings = _sync_competitor_listings(dev, prod, product_map)
            observations = _sync_competitor_observations(dev, prod, product_map)
            deactivated = _deactivate_missing_products(dev, prod) if mirror else 0
            prod.commit()
            return {
                "categories": len(category_map),
                "settings": settings,
                "suggested_price_formulas": formulas,
                "products": len(product_map),
                "products_deactivated": deactivated,
                "competitor_listings_added": listings,
                "competitor_observations_added": observations,
            }
    finally:
        dev_engine.dispose()
        prod_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sync dev DB data into a Staging database without deleting rows. "
            "Production destinations are refused."
        )
    )
    parser.add_argument("--dev-url", default=os.environ.get("DEV_DATABASE_URL", DEFAULT_DEV_URL))
    parser.add_argument(
        "--prod-url",
        default=None,
        help="Destination (Staging) database URL; the legacy flag name is kept.",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    parser.add_argument(
        "--mirror",
        action="store_true",
        help="Soft-deactivate destination products absent from the dev catalog.",
    )
    args = parser.parse_args()

    # Fail closed before reading a destination URL or opening a connection.
    enforce_deployment_env("sync_dev_to_prod", (STAGING,))

    if args.prod_url is None:
        from app.core.config import get_settings

        args.prod_url = get_settings().database_url
    if not args.prod_url:
        print("destination DATABASE_URL is empty", file=sys.stderr)
        return 1

    if not args.yes:
        # Never echo credentials: the destination URL usually contains a Neon
        # password, and this confirmation runs in shared terminals/CI logs.
        print(f"DEV : {_safe_url(args.dev_url)}")
        print(f"DEST: {_safe_url(args.prod_url)}")
        answer = input(
            "This will UPSERT dev data into the destination, copy missing "
            "competitor links and observations"
            + (", and soft-deactivate products absent from dev" if args.mirror else "")
            + ". No products, categories, or links are deleted. Continue? [y/N] "
        )
        if answer.strip().lower() not in {"y", "yes"}:
            print("aborted")
            return 1

    counts = sync(args.dev_url, args.prod_url, mirror=args.mirror)
    print(
        "synced: "
        f"{counts['categories']} categories, {counts['settings']} settings, "
        f"{counts['suggested_price_formulas']} suggested-price weights, "
        f"{counts['products']} products "
        f"({counts['products_deactivated']} deactivated), "
        f"{counts['competitor_listings_added']} new competitor links, "
        f"{counts['competitor_observations_added']} new price observations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
