"""Fold the no-competitor-price flag into the third pricing mode.

The owner marker ``products.no_competitor_price`` becomes the persisted value
``pricing_mode = 'no_competitor_price'``. Rows with the flag set are migrated
first, then the redundant boolean column is dropped. The downgrade restores the
column, backfills it from the mode, and resets those rows to
``exact_competitor`` so the earlier two-mode layout is intact again.
"""

from collections.abc import Sequence

from alembic import context, op
import sqlalchemy as sa

revision: str = "0026_no_price_pricing_mode"
down_revision: str | None = "0025_restore_category_weights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NO_PRICE_MODE = "no_competitor_price"
EXACT_MODE = "exact_competitor"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE products SET pricing_mode = :no_price_mode WHERE no_competitor_price = :flag"
        ),
        parameters={"no_price_mode": NO_PRICE_MODE, "flag": True},
    )
    # Offline SQL is rendered from the dialect in the URL; only an online
    # SQLite connection needs batch mode to rebuild the table for a drop.
    if context.is_offline_mode() or op.get_bind().dialect.name != "sqlite":
        op.drop_column("products", "no_competitor_price")
    else:
        with op.batch_alter_table("products") as batch_op:
            batch_op.drop_column("no_competitor_price")


def downgrade() -> None:
    column = sa.Column(
        "no_competitor_price",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )
    if context.is_offline_mode() or op.get_bind().dialect.name != "sqlite":
        op.add_column("products", column)
    else:
        with op.batch_alter_table("products") as batch_op:
            batch_op.add_column(column)

    op.get_bind().execute(
        sa.text(
            "UPDATE products SET no_competitor_price = :flag WHERE pricing_mode = :no_price_mode"
        ),
        parameters={"flag": True, "no_price_mode": NO_PRICE_MODE},
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE products SET pricing_mode = :exact_mode WHERE pricing_mode = :no_price_mode"
        ),
        parameters={"exact_mode": EXACT_MODE, "no_price_mode": NO_PRICE_MODE},
    )
