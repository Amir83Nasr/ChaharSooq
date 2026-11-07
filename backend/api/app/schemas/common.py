"""Shared API envelopes."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "validation_error",
                    "message": "خطای اعتبارسنجی",
                    "details": {"price": ["قیمت کمتر از حد مجاز است"]},
                }
            ]
        }
    )

    code: str = Field(
        description="Stable machine-readable code, e.g. `unauthorized`, `not_found`.",
        examples=["validation_error"],
    )
    message: str = Field(
        description="User-facing Persian message, ready to display.",
        examples=["خطای اعتبارسنجی"],
    )
    details: dict[str, list[str]] | None = Field(
        default=None,
        description="Field path → Persian validation messages. Present on `validation_error`.",
    )


class ErrorEnvelope(BaseModel):
    """Single error shape for every non-2xx response."""

    error: ErrorBody
