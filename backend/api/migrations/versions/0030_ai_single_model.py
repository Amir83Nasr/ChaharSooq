"""Use the shared AI model for every feature.

ADR 039 added ``analysis_model_id`` so product reports could use a fast model.
The owner no longer wants a separate analysis model: the model configured in
the AI settings is the only one, including for product analysis (ADR 040).

Revision ID: 0030_ai_single_model
Revises: 0029_ai_analysis_persistence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_ai_single_model"
down_revision: str | None = "0029_ai_analysis_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("ai_config", "analysis_model_id")


def downgrade() -> None:
    op.add_column(
        "ai_config",
        sa.Column(
            "analysis_model_id",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
