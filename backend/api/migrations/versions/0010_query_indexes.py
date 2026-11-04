"""Product + competitor query indexes (filter/sort paths)."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010_query_indexes"
down_revision: str | None = "0009_technolife_currency_fix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_products_is_active", "products", ["is_active"])
    op.create_index("ix_products_price", "products", ["price"])
    op.create_index("ix_products_stock", "products", ["stock"])
    op.create_index(
        "ix_competitor_listings_last_success", "competitor_listings", ["last_success_at"]
    )
    # App-level duplicate guard becomes a real constraint (races otherwise).
    # Existing duplicates (if any) keep the oldest row per (product, store).
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else ""
    if dialect == "postgresql":
        conn.execute(
            sa.text(
                """
                DELETE FROM competitor_listings a USING competitor_listings b
                WHERE a.id > b.id
                  AND a.product_id = b.product_id
                  AND a.store = b.store
                """
            )
        )
    op.create_unique_constraint(
        "uq_competitor_listings_product_store",
        "competitor_listings",
        ["product_id", "store"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_competitor_listings_product_store", "competitor_listings", type_="unique"
    )
    op.drop_index("ix_competitor_listings_last_success", table_name="competitor_listings")
    op.drop_index("ix_products_stock", table_name="products")
    op.drop_index("ix_products_price", table_name="products")
    op.drop_index("ix_products_is_active", table_name="products")
