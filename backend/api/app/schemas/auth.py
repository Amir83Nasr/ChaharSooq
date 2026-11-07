"""Auth boundary schemas."""

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"username": "admin", "password": "••••••••"}]}
    )

    username: str = Field(min_length=1, max_length=64, description="Admin username.")
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Plain password; never logged or stored. Use HTTPS in production.",
    )


class LoginOut(BaseModel):
    ok: bool = Field(default=True, description="Always `true`; failures return an error envelope.")


class MeOut(BaseModel):
    username: str = Field(description="Username behind the current session.")
