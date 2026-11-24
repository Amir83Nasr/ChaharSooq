"""Restore per-category suggested-price weights after the pricing-mode refactor.

Revision 0024 originally keyed ``suggested_price_formulas`` by pricing mode and
collapsed the four category weights into two. The concept was revised: the
per-product mode selects *which* formula applies, while the weight ``w`` stays
per catalog section and is shared by both formulas.

This migration repairs databases that applied the early 0024 (column ``mode``
with two collapsed rows). On a database that applied the corrected 0024
(column ``top_group``) it only backfills any missing default weights.
"""

from collections.abc import Sequence

from alembic import context, op
import sqlalchemy as sa

revision: str = "0025_restore_category_weights"
down_revision: str | None = "0024_per_product_pricing_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same defaults as scripts/seed_demo_competitors.py: one weight per section.
CATEGORY_WEIGHTS: dict[str, str] = {
    "فرش": "0.4000",
    "مبلمان": "0.5000",
    "لوازم خانگی": "0.2000",
    "کالای دیجیتال": "0.4000",
}


def upgrade() -> None:
    if not context.is_offline_mode():
        columns = {
            column["name"]
            for column in sa.inspect(op.get_bind()).get_columns("suggested_price_formulas")
        }
        if "mode" in columns:
            op.alter_column(
                "suggested_price_formulas",
                "mode",
                new_column_name="top_group",
                existing_type=sa.String(32),
            )
            # Map the two collapsed mode rows back to their original sections;
            # the two missing defaults are inserted below.
            op.execute(
                "UPDATE suggested_price_formulas SET top_group = 'فرش' "
                "WHERE top_group = 'similar_product'"
            )
            op.execute(
                "UPDATE suggested_price_formulas SET top_group = 'لوازم خانگی' "
                "WHERE top_group = 'exact_competitor'"
            )

        existing = {
            str(row[0])
            for row in op.get_bind().execute(
                sa.text("SELECT top_group FROM suggested_price_formulas")
            )
        }
        for top_group, value in CATEGORY_WEIGHTS.items():
            if top_group not in existing:
                op.get_bind().execute(
                    sa.text(
                        "INSERT INTO suggested_price_formulas (top_group, weight) "
                        "VALUES (:top_group, :weight)"
                    ),
                    parameters={"top_group": top_group, "weight": value},
                )
        return

    # Offline SQL chains always include the corrected 0024, so the column is
    # already `top_group`. Emit deterministic, idempotent statements only.
    op.execute(
        "DELETE FROM suggested_price_formulas WHERE top_group IN "
        "('similar_product', 'exact_competitor')"
    )
    dialect = op.get_bind().dialect.name
    for top_group, value in CATEGORY_WEIGHTS.items():
        statement = (
            "INSERT INTO suggested_price_formulas (top_group, weight) VALUES (:top_group, :weight)"
        )
        if dialect == "postgresql":
            statement += " ON CONFLICT (top_group) DO NOTHING"
        op.get_bind().execute(
            sa.text(statement),
            parameters={"top_group": top_group, "weight": value},
        )


def downgrade() -> None:
    """Re-collapse the four category weights into the two-mode layout."""
    op.execute(
        "DELETE FROM suggested_price_formulas WHERE top_group IN ('مبلمان', 'کالای دیجیتال')"
    )
    op.execute(
        "UPDATE suggested_price_formulas SET top_group = 'similar_product' WHERE top_group = 'فرش'"
    )
    op.execute(
        "UPDATE suggested_price_formulas SET top_group = 'exact_competitor' "
        "WHERE top_group = 'لوازم خانگی'"
    )
    op.alter_column(
        "suggested_price_formulas",
        "top_group",
        new_column_name="mode",
        existing_type=sa.String(32),
    )
