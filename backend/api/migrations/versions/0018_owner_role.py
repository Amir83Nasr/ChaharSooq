"""Add the `owner` (super admin) role and promote the oldest admin to it.

`owner` is the highest level: it manages shop data, admins, and viewers. The
environment-managed owner account is ensured on API boot (see
`app/services/owner.py`). Existing installs keep access by promoting their
oldest admin; every other account stays `admin`.

Revision ID: 0018_owner_role
Revises: 0017_admin_roles
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0018_owner_role"
down_revision: str | None = "0017_admin_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_admins_role"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "admins", type_="check")
    op.execute(
        "UPDATE admins SET role = 'owner' "
        "WHERE id = (SELECT MIN(id) FROM admins WHERE role = 'admin')"
    )
    op.create_check_constraint(CONSTRAINT, "admins", "role IN ('owner', 'admin', 'viewer')")


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "admins", type_="check")
    op.execute("UPDATE admins SET role = 'admin' WHERE role = 'owner'")
    op.create_check_constraint(CONSTRAINT, "admins", "role IN ('admin', 'viewer')")
