"""Execute backups from the panel: queue, worker lease, and data restores.

Adds the queue state, the single-row worker lease, and archive pruning metadata.
Restore execution state lives on ``backup_records`` from revision 0020 (ADR 026).
No credential, archive byte, or filesystem path is stored here.

Revision ID: 0021_backup_execution
Revises: 0020_backup_records
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_backup_execution"
down_revision: str | None = "0020_backup_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backup_records",
        sa.Column("pruned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint("ck_backup_records_status", "backup_records", type_="check")
    op.create_check_constraint(
        "ck_backup_records_status",
        "backup_records",
        "status IN ('queued', 'running', 'completed', 'failed')",
    )

    op.create_table(
        "backup_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("INSERT INTO backup_state (id, lease_until) VALUES (1, NULL)")


def downgrade() -> None:
    # Fold the new state into the old vocabulary before restoring the check.
    op.execute("UPDATE backup_records SET status = 'failed' WHERE status = 'queued'")
    op.drop_table("backup_state")

    op.drop_constraint("ck_backup_records_status", "backup_records", type_="check")
    op.create_check_constraint(
        "ck_backup_records_status",
        "backup_records",
        "status IN ('running', 'completed', 'failed')",
    )
    op.drop_column("backup_records", "pruned_at")
