"""Add account roles: `admin` (full access) and `viewer` (read-only).

Existing accounts keep full access, so the column defaults to `admin`.

Revision ID: 0017_admin_roles
Revises: 0016_price_history_and_bounds
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0017_admin_roles"
down_revision: str | None = "0016_price_history_and_bounds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_admins_role"


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column("role", sa.String(16), nullable=False, server_default="admin"),
    )
    op.create_check_constraint(CONSTRAINT, "admins", "role IN ('admin', 'viewer')")


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "admins", type_="check")
    op.drop_column("admins", "role")
