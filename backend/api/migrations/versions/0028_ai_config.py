"""Add the owner-managed AI configuration singleton.

A dedicated table keeps the write-only API key and the potentially long system
prompt out of the generic display-preferences table. No row is seeded; the
service applies documented defaults until the owner saves a configuration.

Revision ID: 0028_ai_config
Revises: 0027_pinned_and_two_modes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_ai_config"
down_revision: str | None = "0027_pinned_and_two_modes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("api_key", sa.String(length=512), nullable=True),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_config")
