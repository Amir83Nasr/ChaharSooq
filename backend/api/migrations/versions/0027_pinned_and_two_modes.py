"""Add a pinned marker to products and drop the no-competitor-price mode.

Pinned products can be revisited later through the پین list filter. The old
``no_competitor_price`` pricing mode is removed from the selector: rows still
carrying it become ``exact_competitor`` so every product keeps a usable
suggested-price formula. The downgrade restores the third mode as
``no_competitor_price`` for nothing (that state no longer exists), leaving the
column and index removed.
"""

from collections.abc import Sequence

from alembic import context, op
import sqlalchemy as sa

revision: str = "0027_pinned_and_two_modes"
down_revision: str | None = "0026_no_price_pricing_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NO_PRICE_MODE = "no_competitor_price"
EXACT_MODE = "exact_competitor"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE products SET pricing_mode = :exact_mode WHERE pricing_mode = :no_price_mode"
        ),
        parameters={"exact_mode": EXACT_MODE, "no_price_mode": NO_PRICE_MODE},
    )
    op.add_column(
        "products",
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_products_pinned", "products", ["pinned"])
    # Mirror 0024/0026: SQLite cannot alter a server default in place, and
    # offline SQL must stay dialect-neutral.
    if context.is_offline_mode() or op.get_bind().dialect.name != "sqlite":
        op.alter_column("products", "pinned", server_default=None)
    else:
        with op.batch_alter_table("products") as batch_op:
            batch_op.alter_column("pinned", server_default=None)


def downgrade() -> None:
    if context.is_offline_mode() or op.get_bind().dialect.name != "sqlite":
        op.drop_index("ix_products_pinned", table_name="products")
        op.drop_column("products", "pinned")
    else:
        with op.batch_alter_table("products") as batch_op:
            batch_op.drop_index("ix_products_pinned")
            batch_op.drop_column("pinned")
