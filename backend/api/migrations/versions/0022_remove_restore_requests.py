"""Remove the restore-request table left behind by earlier backup builds.

ADR 026 moved restore state onto ``backup_records`` and removed the request
workflow. Databases that ran an earlier build still carry
``backup_restore_requests``; its ON DELETE RESTRICT foreign key pins archives
that were restored before the switch, so the owner cannot delete them.
Fresh databases created from revisions 0020/0021 never had the table, hence
the conditional drop. The old request rows are history only — ADR 026 accepts
that they cannot be shown after the switch.

Revision ID: 0022_remove_restore_requests
Revises: 0021_backup_execution
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_remove_restore_requests"
down_revision: str | None = "0021_backup_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS backup_restore_requests")


def downgrade() -> None:
    # Schema parity for a rollback to the superseded restore-request flow;
    # the rows dropped by upgrade() cannot be recovered.
    op.create_table(
        "backup_restore_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "backup_record_id",
            sa.Integer(),
            sa.ForeignKey("backup_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(16), server_default="requested"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("drill_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
    )
    op.create_check_constraint(
        "ck_backup_restore_requests_status",
        "backup_restore_requests",
        "status IN ('requested', 'in_progress', 'completed', 'failed', 'cancelled')",
    )
