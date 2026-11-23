"""Select the suggested-price formula per product instead of per category.

Every product now carries a ``pricing_mode``: ``exact_competitor`` uses the
weighted blend with a direct competitor price, ``similar_product`` uses the
linked product's daily price change. Existing rows get their mode from their
catalog section (carpet/furniture become ``similar_product``).

The formula weights are keyed by mode instead of top group. Old rows are
collapsed to two modes; when several old weights map to the same mode the
lexicographically first original top_group wins, making the result
deterministic on both SQLite and PostgreSQL.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0024_per_product_pricing_mode"
down_revision: str | None = "0023_product_no_competitor_price"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "pricing_mode",
            sa.String(32),
            nullable=False,
            server_default="exact_competitor",
        ),
    )
    op.execute(
        "UPDATE products SET pricing_mode = 'similar_product' "
        "WHERE main_group_name LIKE 'فرش%' OR main_group_name LIKE 'مبلمان%'"
    )
    # SQLite cannot drop a column default with ALTER; keeping the harmless
    # server default there preserves the same behaviour for future rows.
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("products", "pricing_mode", server_default=None)

    op.alter_column(
        "suggested_price_formulas",
        "top_group",
        new_column_name="mode",
        existing_type=sa.String(32),
    )
    # Collapse the four old top-group keys to two modes. Where both keys of a
    # group exist, keep the lexicographically first one (by Unicode code point:
    # «فرش» before «مبلمان», «لوازم خانگی» before «کالای دیجیتال»); a lone key
    # is always kept. Explicit keys keep offline SQL generation dialect-neutral.
    op.execute(
        "DELETE FROM suggested_price_formulas WHERE "
        "(mode = 'مبلمان' AND EXISTS (SELECT 1 FROM suggested_price_formulas WHERE mode = 'فرش')) "
        "OR (mode = 'کالای دیجیتال' AND EXISTS "
        "(SELECT 1 FROM suggested_price_formulas WHERE mode = 'لوازم خانگی'))"
    )
    op.execute(
        "UPDATE suggested_price_formulas SET mode = 'similar_product' "
        "WHERE mode IN ('فرش', 'مبلمان')"
    )
    op.execute(
        "UPDATE suggested_price_formulas SET mode = 'exact_competitor' "
        "WHERE mode IN ('لوازم خانگی', 'کالای دیجیتال')"
    )


def downgrade() -> None:
    op.alter_column(
        "suggested_price_formulas",
        "mode",
        new_column_name="top_group",
        existing_type=sa.String(32),
    )
    op.execute(
        "UPDATE suggested_price_formulas SET top_group = 'فرش' WHERE top_group = 'similar_product'"
    )
    op.execute(
        "UPDATE suggested_price_formulas SET top_group = 'لوازم خانگی' "
        "WHERE top_group = 'exact_competitor'"
    )
    op.drop_column("products", "pricing_mode")
