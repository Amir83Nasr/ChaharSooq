"""Track backup archives and their restore execution state.

Metadata only: archives stay on the host under ADR 014. The owner can enable
backups, inspect verified archives, and trigger a direct restore (ADR 026) that
the API worker executes transactionally.

Revision ID: 0020_backup_records
Revises: 0019_parsina_connection_config
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_backup_records"
down_revision: str | None = "0019_parsina_connection_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backup_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="scheduled"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("verification", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("verification_method", sa.String(length=32), nullable=True),
        sa.Column("source_revision", sa.String(length=64), nullable=True),
        sa.Column("storage_ref", sa.String(length=512), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("restore_status", sa.String(length=16), nullable=True),
        sa.Column("restore_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restore_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restore_error_code", sa.String(length=64), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="ck_backup_records_status"
        ),
        sa.CheckConstraint(
            "verification IN ('pending', 'verified', 'failed')",
            name="ck_backup_records_verification",
        ),
        sa.CheckConstraint(
            "restore_status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_backup_records_restore_status",
        ),
    )
    op.create_index("ix_backup_records_created_at", "backup_records", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backup_records_created_at", table_name="backup_records")
    # 0022's downgrade recreates the restore-request table with a RESTRICT FK to
    # backup_records. Drop it first so backup_records can be removed on a full
    # round-trip; a rollback from 0021 simply has no such table.
    op.execute("DROP TABLE IF EXISTS backup_restore_requests")
    op.drop_table("backup_records")
