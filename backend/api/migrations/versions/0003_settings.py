"""Add key/value settings table (admin display thresholds)."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_settings"
down_revision: str | None = "0002_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.String(256), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
