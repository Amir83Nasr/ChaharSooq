"""Add categories table + products.category_id FK."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_categories"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("products", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_products_category_id", "products", "categories", ["category_id"], ["id"]
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_constraint("fk_products_category_id", "products", type_="foreignkey")
    op.drop_column("products", "category_id")
    op.drop_table("categories")
