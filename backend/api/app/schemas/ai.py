"""AI integration boundary schemas.

The API key is write-only: `AISettingsOut` only reports whether one is stored.
"""

from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

AI_SYSTEM_PROMPT_MAX_LENGTH = 20_000


class AISettingsOut(BaseModel):
    base_url: str = Field(description="Effective OpenAI-compatible API base URL.")
    model_id: str = Field(description="Effective model id sent with every request.")
    analysis_model_id: str = Field(
        description="Effective model id used only for product analysis reports."
    )
    system_prompt: str = Field(description="Shared system prompt prepended to requests.")
    api_key_set: bool = Field(description="True when an API key is stored.")
    configured: bool = Field(
        description="True when base URL, model id, and API key are all available."
    )


class AISettingsIn(BaseModel):
    """Partial update. Omitted fields keep their stored value."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "base_url": "https://api.gapgpt.ir/v1",
                    "api_key": "sk-...",
                    "model_id": "gapgpt-deepseek-v4.1-flash",
                    "analysis_model_id": "gpt-4.1-mini",
                    "system_prompt": "تو دستیار فروشگاه چهارسوق هستی.",
                }
            ]
        },
    )

    base_url: str | None = Field(
        default=None,
        max_length=512,
        description="OpenAI-compatible base URL, e.g. https://api.gapgpt.ir/v1.",
    )
    api_key: str | None = Field(
        default=None,
        max_length=512,
        description="Write-only API key. Empty or omitted keeps the stored key.",
        json_schema_extra={"writeOnly": True},
    )
    model_id: str | None = Field(
        default=None,
        max_length=255,
        description="Model id, e.g. gapgpt-deepseek-v4.1-flash.",
    )
    analysis_model_id: str | None = Field(
        default=None,
        max_length=255,
        description=(
            "Model id for product analysis reports; empty uses the fast default (gpt-4.1-mini)."
        ),
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=AI_SYSTEM_PROMPT_MAX_LENGTH,
        description="Shared system prompt; an empty string clears it.",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().rstrip("/")
        if not text:
            return ""
        parsed = urlsplit(text)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("آدرس پایه باید یک URL معتبر با http یا https باشد")
        return text

    @field_validator("api_key")
    @classmethod
    def strip_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("model_id")
    @classmethod
    def strip_model_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class AITestIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: str = Field(
        min_length=1,
        max_length=4_000,
        description="User prompt used for the connection check.",
    )

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("متن آزمایش نمی‌تواند خالی باشد")
        return text


class AITestOut(BaseModel):
    model: str = Field(description="Model reported by the provider.")
    reply: str = Field(description="Model reply text.")
    latency_ms: int = Field(description="Round-trip time in milliseconds.")


class ProductAnalysisReportOut(BaseModel):
    """The last complete AI report saved for one product."""

    product_id: int
    content: str
    model_id: str
    generated_at: datetime = Field(description="UTC timestamp of the saved report.")

    model_config = ConfigDict(from_attributes=True)
