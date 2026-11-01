"""Add per-category suggested price formulas."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_suggested_price_formulas"
down_revision: str | None = "0006_competitor_prices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suggested_price_formulas",
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("expression", sa.String(256), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_id"),
    )


def downgrade() -> None:
    op.drop_table("suggested_price_formulas")
