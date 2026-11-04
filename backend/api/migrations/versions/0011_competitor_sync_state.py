"""Competitor bulk-refresh state (single-row lock + counters)."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0011_competitor_sync_state"
down_revision: str | None = "0010_query_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competitor_sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("running_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("last_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_skipped", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("competitor_sync_state")
