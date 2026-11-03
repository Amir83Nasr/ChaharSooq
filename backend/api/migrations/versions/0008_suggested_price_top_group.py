"""Key suggested price formulas by the store's top-level groups.

Replaces the category_id-keyed table from 0007: formulas belong to the
three fixed groups shown in the products table (فرش، مبلمان، لوازم خانگی),
not to the manually managed `categories` table."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_suggested_price_top_group"
down_revision: str | None = "0007_suggested_price_formulas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("suggested_price_formulas")
    op.create_table(
        "suggested_price_formulas",
        sa.Column("top_group", sa.String(32), nullable=False),
        sa.Column("expression", sa.String(256), nullable=False),
        sa.PrimaryKeyConstraint("top_group"),
    )


def downgrade() -> None:
    op.drop_table("suggested_price_formulas")
    op.create_table(
        "suggested_price_formulas",
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("expression", sa.String(256), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_id"),
    )
