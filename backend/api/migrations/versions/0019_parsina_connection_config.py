"""Store Parsina connection config in the sync-state row.

Super admins can enter and update the Parsina API connection details from
settings. The fields mirror the Parsina auth contract (base URL, username,
password, organization id, fiscal year). All columns are nullable so existing
env/secret configuration remains the fallback.

Revision ID: 0019_parsina_connection_config
Revises: 0018_owner_role
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_parsina_connection_config"
down_revision: str | None = "0018_owner_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parsina_sync_state", sa.Column("base_url", sa.String(length=512), nullable=True))
    op.add_column("parsina_sync_state", sa.Column("username", sa.String(length=255), nullable=True))
    op.add_column("parsina_sync_state", sa.Column("password", sa.String(length=512), nullable=True))
    op.add_column("parsina_sync_state", sa.Column("org_id", sa.Integer(), nullable=True))
    op.add_column("parsina_sync_state", sa.Column("fiscal_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("parsina_sync_state", "fiscal_year")
    op.drop_column("parsina_sync_state", "org_id")
    op.drop_column("parsina_sync_state", "password")
    op.drop_column("parsina_sync_state", "username")
    op.drop_column("parsina_sync_state", "base_url")
