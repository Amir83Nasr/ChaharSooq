"""Product search/sort composite indexes + trigram support (PostgreSQL only)."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0012_search_indexes"
down_revision: str | None = "0011_competitor_sync_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else ""
    if dialect == "postgresql":
        # Faster %q% Persian search on the product list; GIN trigram works
        # for both prefix and infix LIKE/ILIKE patterns.
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_products_name_trgm "
            "ON products USING gin (name gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_products_sku_trgm "
            "ON products USING gin (sku gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_products_main_group_trgm "
            "ON products USING gin (main_group_name gin_trgm_ops)"
        )
    # Composite B-tree paths (all dialects): active-first filter + sort key.
    # Covers top_group/category + price/stock sorting without extra sorting.
    op.create_index("ix_products_active_main_group", "products", ["is_active", "main_group_name"])
    op.create_index("ix_products_active_category", "products", ["is_active", "category_id"])
    op.create_index("ix_products_active_price_id", "products", ["is_active", "price", "id"])
    op.create_index("ix_products_active_stock", "products", ["is_active", "stock"])
    op.create_index(
        "ix_competitor_listings_product_active",
        "competitor_listings",
        ["product_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_competitor_listings_product_active", table_name="competitor_listings")
    op.drop_index("ix_products_active_stock", table_name="products")
    op.drop_index("ix_products_active_price_id", table_name="products")
    op.drop_index("ix_products_active_category", table_name="products")
    op.drop_index("ix_products_active_main_group", table_name="products")
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else ""
    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_products_name_trgm")
        op.execute("DROP INDEX IF EXISTS ix_products_sku_trgm")
        op.execute("DROP INDEX IF EXISTS ix_products_main_group_trgm")
