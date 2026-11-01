"""Store manually managed competitor links and separate price observations."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_competitor_prices"
down_revision: str | None = "0005_parsina_products"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competitor_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("store", sa.String(30), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("fetched_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("fetched_currency", sa.String(3), nullable=True),
        sa.Column("fetched_in_stock", sa.Boolean(), nullable=True),
        sa.Column("manual_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("manual_currency", sa.String(3), nullable=True),
        sa.Column("manual_in_stock", sa.Boolean(), nullable=True),
        sa.Column("manual_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_competitor_listings_product_id", "competitor_listings", ["product_id"])
    op.create_index("ix_competitor_listings_store", "competitor_listings", ["store"])


def downgrade() -> None:
    op.drop_index("ix_competitor_listings_store", table_name="competitor_listings")
    op.drop_index("ix_competitor_listings_product_id", table_name="competitor_listings")
    op.drop_table("competitor_listings")
