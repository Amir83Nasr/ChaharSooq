"""Fix legacy Technolife currency label (IRR -> IRT).

Technolife labels its JSON-LD offer with ``priceCurrency: IRR`` while the
numeric value matches the Toman price shown on the page. Fetches before the
parser fix stored that value as IRR, so the generic IRR->toman (/10)
conversion dropped one zero in the products table. New fetches normalise to
IRT at the source; this migration fixes rows already stored.
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0009_technolife_currency_fix"
down_revision: str | None = "0008_suggested_price_top_group"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE competitor_listings "
        "SET fetched_currency = 'IRT' "
        "WHERE store = 'technolife' AND fetched_currency = 'IRR'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE competitor_listings "
        "SET fetched_currency = 'IRR' "
        "WHERE store = 'technolife' AND fetched_currency = 'IRT'"
    )
