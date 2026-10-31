"""Copy data from the local dev Postgres into the production (Neon) database.

Usage (from repo root):
    make db-sync-dev-to-prod            # prompts for confirmation
    make db-sync-dev-to-prod YES=1      # non-interactive

Or directly:
    uv run --project backend/api --env-file .env.production \\
        python backend/api/scripts/sync_dev_to_prod.py [--dev-url ...] [--prod-url ...] [--yes]

Defaults:
    dev  = postgresql://charsooq:charsooq@localhost:5433/charsooq
    prod = DATABASE_URL from the loaded env file

What it copies (data only; schema must already be migrated on prod):
    categories, settings, parsina_sync_state, products
It never touches admins / admin_sessions / alembic_version on prod.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg
from psycopg import sql

DEFAULT_DEV_URL = "postgresql://charsooq:charsooq@localhost:5433/charsooq"


def _reset_sequences(cur: psycopg.Cursor) -> None:
    cur.execute(
        "SELECT setval('categories_id_seq', (SELECT COALESCE(MAX(id), 1) FROM categories), true)"
    )
    cur.execute(
        "SELECT setval('products_id_seq', (SELECT COALESCE(MAX(id), 1) FROM products), true)"
    )
    cur.execute(
        "SELECT setval('parsina_sync_state_id_seq', "
        "(SELECT COALESCE(MAX(id), 1) FROM parsina_sync_state), true)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync dev DB data into prod DB.")
    parser.add_argument("--dev-url", default=os.environ.get("DEV_DATABASE_URL", DEFAULT_DEV_URL))
    parser.add_argument("--prod-url", default=None)
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    if args.prod_url is None:
        from app.core.config import get_settings

        args.prod_url = get_settings().database_url
    if not args.prod_url:
        print("prod DATABASE_URL is empty", file=sys.stderr)
        return 1

    if not args.yes:
        print(f"DEV : {args.dev_url}")
        print(f"PROD: {args.prod_url}")
        answer = input(
            "This will REPLACE data in prod (categories/settings/products/sync_state). "
            "Continue? [y/N] "
        )
        if answer.strip().lower() not in {"y", "yes"}:
            print("aborted")
            return 1

    with psycopg.connect(args.dev_url) as dev, psycopg.connect(args.prod_url) as prod:
        dcur = dev.cursor()
        pcur = prod.cursor()

        for t in ["products", "parsina_sync_state", "settings", "categories"]:
            pcur.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(sql.Identifier(t))
            )
        prod.commit()

        # categories
        dcur.execute("SELECT id, name, created_at FROM categories")
        with pcur.copy("COPY categories (id, name, created_at) FROM STDIN") as cp:
            for row in dcur:
                cp.write_row(row)
        print("categories: synced")

        # settings
        dcur.execute("SELECT key, value FROM settings")
        with pcur.copy("COPY settings (key, value) FROM STDIN") as cp:
            for row in dcur:
                cp.write_row(row)
        print("settings: synced")

        # parsina_sync_state
        dcur.execute(
            """SELECT id, lock_until, running_since, last_attempt_at, last_success_at,
                      last_error, last_processed, last_created, last_updated,
                      last_deactivated, last_skipped
               FROM parsina_sync_state"""
        )
        cols = [
            "id",
            "lock_until",
            "running_since",
            "last_attempt_at",
            "last_success_at",
            "last_error",
            "last_processed",
            "last_created",
            "last_updated",
            "last_deactivated",
            "last_skipped",
        ]
        with pcur.copy(
            sql.SQL("COPY parsina_sync_state ({}) FROM STDIN").format(
                sql.SQL(", ").join(sql.Identifier(c) for c in cols)
            )
        ) as cp:
            for row in dcur:
                cp.write_row(row)
        print("parsina_sync_state: synced")

        # products (columns resolved from dev schema)
        dcur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'products' ORDER BY ordinal_position"
        )
        prod_cols = [r[0] for r in dcur.fetchall()]
        dcur.execute(
            sql.SQL("SELECT {} FROM products").format(
                sql.SQL(", ").join(sql.Identifier(c) for c in prod_cols)
            )
        )
        n = 0
        with pcur.copy(
            sql.SQL("COPY products ({}) FROM STDIN").format(
                sql.SQL(", ").join(sql.Identifier(c) for c in prod_cols)
            )
        ) as cp:
            for row in dcur:
                cp.write_row(row)
                n += 1
        print(f"products: synced {n}")

        _reset_sequences(pcur)
        prod.commit()
        print("done: sequences reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
