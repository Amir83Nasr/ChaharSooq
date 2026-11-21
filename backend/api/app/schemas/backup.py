"""Backup settings and metadata boundary schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Interval bounds mirror app.services.settings (backend is the source of truth).
MIN_BACKUP_INTERVAL_MINUTES = 60
MAX_BACKUP_INTERVAL_MINUTES = 10080


class BackupSettingsOut(BaseModel):
    enabled: bool = Field(description="Automatic host-side backups are enabled.")
    interval_minutes: int = Field(description="Minimum interval between scheduled backups.")
    retention_days: int = Field(description="Fixed retention policy; not editable in the panel.")
    verification_method: str = Field(description="How an archive is verified before trust.")
    tools_available: bool = Field(
        description="pg_dump, pg_restore, and psql are present in this runtime."
    )
    storage_ready: bool = Field(description="The archive directory is writable.")


class BackupSettingsUpdateIn(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"enabled": True, "interval_minutes": 10080}]},
    )

    enabled: bool | None = Field(default=None, description="Enable or pause automatic backups.")
    interval_minutes: int | None = Field(
        default=None,
        ge=MIN_BACKUP_INTERVAL_MINUTES,
        le=MAX_BACKUP_INTERVAL_MINUTES,
        description="Automatic backup interval, in minutes.",
    )


class BackupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    finished_at: datetime | None
    status: str
    kind: str
    size_bytes: int | None
    sha256: str | None
    verification: str
    verification_method: str | None
    source_revision: str | None
    storage_ref: str | None
    retention_expires_at: datetime | None
    pruned_at: datetime | None
    error_code: str | None
    restore_status: str | None
    restore_started_at: datetime | None
    restore_finished_at: datetime | None
    restore_error_code: str | None
    restored_at: datetime | None
    downloadable: bool = Field(description="The archive file still exists in local storage.")
