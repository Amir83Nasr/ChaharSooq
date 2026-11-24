"""Select the suggested-price formula per product instead of per category.

Every product now carries a ``pricing_mode``: ``exact_competitor`` uses the
weighted blend with a direct competitor price, ``similar_product`` uses the
linked product's daily price change. Existing rows get their mode from their
catalog section (carpet/furniture become ``similar_product``).

Formula weights stay keyed by top group — one weight per catalog section,
shared by both formulas — so ``suggested_price_formulas`` is left untouched.
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


def downgrade() -> None:
    op.drop_column("products", "pricing_mode")
