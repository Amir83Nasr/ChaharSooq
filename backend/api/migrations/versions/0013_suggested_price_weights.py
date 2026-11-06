"""Replace free-form suggested price expressions with per-group weights.

The suggested price is now one fixed weighted blend of the Parsina base
price and the competitor price, so the only per-group setting left is the
competitor weight (0..1)."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0013_suggested_price_weights"
down_revision: str | None = "0012_search_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("suggested_price_formulas")
    op.create_table(
        "suggested_price_formulas",
        sa.Column("top_group", sa.String(32), nullable=False),
        sa.Column("weight", sa.Numeric(5, 4), nullable=False),
        sa.PrimaryKeyConstraint("top_group"),
    )


def downgrade() -> None:
    op.drop_table("suggested_price_formulas")
    op.create_table(
        "suggested_price_formulas",
        sa.Column("top_group", sa.String(32), nullable=False),
        sa.Column("expression", sa.String(256), nullable=False),
        sa.PrimaryKeyConstraint("top_group"),
    )
