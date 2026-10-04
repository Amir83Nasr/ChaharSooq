"""Link admin_sessions to admins (multi-admin-safe auth)."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_session_admin"
down_revision: str | None = "0003_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("admin_sessions", sa.Column("admin_id", sa.Integer(), nullable=True))
    op.execute("UPDATE admin_sessions SET admin_id = (SELECT MIN(id) FROM admins)")
    op.alter_column("admin_sessions", "admin_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_admin_sessions_admin_id", "admin_sessions", "admins", ["admin_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_admin_sessions_admin_id", "admin_sessions", type_="foreignkey")
    op.drop_column("admin_sessions", "admin_id")
