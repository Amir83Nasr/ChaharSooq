"""Make competitor links survive accidental product deletes.

Deleting a product used to cascade into `competitor_listings`, which silently
erased manually curated links during dev catalog reseeds and dev→prod copies.
The foreign key now restricts deletes: removal must be explicit (delete the
links first) instead of happening as a side effect.

Revision ID: 0014_competitor_link_restrict
Revises: 0013_suggested_price_weights
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_competitor_link_restrict"
down_revision: str | None = "0013_suggested_price_weights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "competitor_listings_product_id_fkey"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "competitor_listings", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT,
        "competitor_listings",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "competitor_listings", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT,
        "competitor_listings",
        "products",
        ["product_id"],
        ["id"],
        ondelete="CASCADE",
    )
