"""User management boundary schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["owner", "admin", "viewer"]
# The owner is env-managed and never assignable from the panel.
AssignableRole = Literal["admin", "viewer"]


class UserCreateIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "operator",
                    "password": "••••••••",
                    "role": "viewer",
                }
            ]
        }
    )

    username: str = Field(
        min_length=3,
        max_length=64,
        description="Login username, unique across accounts.",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Plain password, hashed with Argon2id; never logged or returned.",
    )
    role: AssignableRole = Field(
        default="viewer",
        description=(
            "`admin` manages shop data and viewers (owner only); `viewer` has read-only access."
        ),
    )


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Account id.")
    username: str = Field(description="Login username.")
    role: UserRole = Field(description="Access level: `owner`, `admin`, or `viewer`.")
    created_at: datetime = Field(description="UTC creation timestamp.")
