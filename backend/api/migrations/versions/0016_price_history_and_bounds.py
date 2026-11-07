"""Track daily competitor price observations and per-product price bounds.

Sofa/DigiFresh links are not used as a direct suggested-price input; the
suggested price follows the linked product's daily price change instead. That
needs every successful observation, not only the latest price. The two product
columns hold the maximum allowed decrease/increase around the base price so the
suggested price can be clamped per product.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0016_price_history_and_bounds"
down_revision: str | None = "0014_competitor_link_restrict"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competitor_price_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "listing_id",
            sa.Integer(),
            sa.ForeignKey("competitor_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_competitor_price_observations_listing_time",
        "competitor_price_observations",
        ["listing_id", "observed_at"],
    )

    op.add_column(
        "products",
        sa.Column("allowed_decrease_percent", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("allowed_increase_percent", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "allowed_increase_percent")
    op.drop_column("products", "allowed_decrease_percent")
    op.drop_index(
        "ix_competitor_price_observations_listing_time",
        table_name="competitor_price_observations",
    )
    op.drop_table("competitor_price_observations")
