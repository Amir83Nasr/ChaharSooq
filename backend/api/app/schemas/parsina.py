"""Parsina integration connection schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ParsinaConnectionOut(BaseModel):
    """Current Parsina connection as visible to the super admin.

    The password is never returned; `password_set` indicates whether one is
    stored (in the database or provided via env/secrets).
    """

    base_url: str = Field(default="", description="Parsina API base URL.")
    username: str = Field(default="", description="Parsina username.")
    org_id: int | None = Field(default=None, description="Organization id (org).")
    fiscal_year: int | None = Field(default=None, description="Fiscal year.")
    password_set: bool = Field(default=False, description="True when a password is configured.")
    configured: bool = Field(
        default=False, description="True when the effective connection is usable."
    )
    source: str = Field(
        default="none",
        description="Where the effective config comes from: db, env, or none.",
    )


class ParsinaConnectionIn(BaseModel):
    """Update Parsina connection fields. Omitted fields keep their current value."""

    model_config = ConfigDict(extra="ignore")

    base_url: str | None = Field(default=None, max_length=512)
    username: str | None = Field(default=None, max_length=255)
    # Empty string or null keeps the existing stored password.
    password: str | None = Field(default=None, max_length=512)
    org_id: int | None = Field(default=None, ge=1)
    fiscal_year: int | None = Field(default=None, ge=1, le=9999)
