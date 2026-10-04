"""Shared API envelopes."""

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, list[str]] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
