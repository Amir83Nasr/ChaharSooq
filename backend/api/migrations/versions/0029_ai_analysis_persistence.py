"""Persist the latest product AI report and allow a separate analysis model.

The report is derived, owner-facing data: one row per product holding the last
complete analysis. A new generation replaces it and the owner can delete it.
Keeping it in PostgreSQL (instead of browser storage) makes it survive the
dialog, a reload, and a different device.

``analysis_model_id`` is separate from the shared ``model_id`` so the report can
use a fast model while the connection test keeps the owner's chosen model.

Revision ID: 0029_ai_analysis_persistence
Revises: 0028_ai_config
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_ai_analysis_persistence"
down_revision: str | None = "0028_ai_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_config",
        sa.Column(
            "analysis_model_id",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.create_table(
        "product_analysis_reports",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_id"),
    )


def downgrade() -> None:
    op.drop_table("product_analysis_reports")
    op.drop_column("ai_config", "analysis_model_id")
