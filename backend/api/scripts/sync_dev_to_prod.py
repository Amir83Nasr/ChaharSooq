"""Copy data from the local dev Postgres into the production (Neon) database.

Usage (from repo root):
    make db-sync-dev-to-prod            # prompts for confirmation
    make db-sync-dev-to-prod YES=1      # non-interactive

Or directly:
    uv run --project backend/api --env-file .env.production \\
        python backend/api/scripts/sync_dev_to_prod.py [--dev-url ...] [--prod-url ...] [--yes]

The sync is non-destructive and upsert-based:

  * categories are matched by name and their dev ids are remapped;
  * settings and the Parsina sync-state row are updated in place;
  * products are matched by `external_id` (manual rows by SKU), so destination
    primary keys never change and rows are never deleted;
  * competitor listings are copied for products that do not have that
    `(product, store)` link on the destination yet. Existing destination links
    are left untouched, so a local copy can never erase production work.
  * demo links from `make db-seed-demo` are skipped, so fake dev prices never
    reach production;
  * per-product suggested-price bounds are admin settings and stay
    environment-local (copied fields never include them).

It never touches admins / admin_sessions / alembic_version and never deletes
products, categories, or competitor listings.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.models import Category, CompetitorListing, ParsinaSyncState, Product, Setting
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


def _find_destination_product(prod: Session, source: Product) -> Product | None:
    if source.external_id is not None:
        return prod.scalar(select(Product).where(Product.external_id == source.external_id))
    return prod.scalar(
        select(Product).where(
            Product.external_id.is_(None),
            Product.sku == source.sku,
        )
    )


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
    pairs: list[tuple[int, Product]] = []
    for source in dev.scalars(select(Product).order_by(Product.id)):
        target = _find_destination_product(prod, source)
        if target is None:
            target = Product(created_at=source.created_at)
            prod.add(target)
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
    must never reach production.
    """
    added = 0
    for source in dev.scalars(select(CompetitorListing).order_by(CompetitorListing.id)):
        if is_demo_competitor_url(source.url):
            continue
        product_id = product_map.get(source.product_id)
        if product_id is None:
            continue
        target = prod.scalar(
            select(CompetitorListing).where(
                CompetitorListing.product_id == product_id,
                CompetitorListing.store == source.store,
            )
        )
        if target is not None:
            continue
        prod.add(
            CompetitorListing(
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
        )
        added += 1
    return added


def sync(dev_url: str, prod_url: str) -> dict[str, int]:
    """Run one non-destructive sync and return per-table counters."""
    dev_engine = _engine(dev_url)
    prod_engine = _engine(prod_url)
    try:
        with Session(dev_engine) as dev, Session(prod_engine) as prod:
            category_map = _sync_categories(dev, prod)
            settings = _sync_settings(dev, prod)
            _sync_parsina_state(dev, prod)
            product_map = _sync_products(dev, prod, category_map)
            listings = _sync_competitor_listings(dev, prod, product_map)
            prod.commit()
            return {
                "categories": len(category_map),
                "settings": settings,
                "products": len(product_map),
                "competitor_listings_added": listings,
            }
    finally:
        dev_engine.dispose()
        prod_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync dev DB data into a destination DB (staging/prod) without deleting rows."
    )
    parser.add_argument("--dev-url", default=os.environ.get("DEV_DATABASE_URL", DEFAULT_DEV_URL))
    parser.add_argument("--prod-url", default=None, help="Destination database URL.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

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
            "This will UPSERT dev data into the destination and copy missing "
            "competitor links. No products, categories, or links are deleted. "
            "Continue? [y/N] "
        )
        if answer.strip().lower() not in {"y", "yes"}:
            print("aborted")
            return 1

    counts = sync(args.dev_url, args.prod_url)
    print(
        "synced: "
        f"{counts['categories']} categories, {counts['settings']} settings, "
        f"{counts['products']} products, "
        f"{counts['competitor_listings_added']} new competitor links"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
