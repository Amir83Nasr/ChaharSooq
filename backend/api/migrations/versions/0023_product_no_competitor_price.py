"""Mark products that genuinely have no competitor price.

The owner can flag a product as having no comparable competitor price (for
example a unique or custom item). This is distinct from a missing or stale
competitor link, which only means price data has not been collected yet.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0023_product_no_competitor_price"
down_revision: str | None = "0022_remove_restore_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "no_competitor_price",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("products", "no_competitor_price", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "no_competitor_price")
