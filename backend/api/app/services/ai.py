"""AI service — owner-managed config plus the shared completion entry point.

Every AI feature should call ``AIService.complete`` rather than building a
provider request itself: the system prompt, credentials, error mapping, and
timeout stay in one place.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.integrations.openai_compatible import (
    AIAuthError,
    AICompletion,
    AIError,
    AIMessage,
    AINetworkError,
    AIResponseError,
    OpenAICompatibleClient,
)
from app.models.ai import AIConfig
from app.repositories import AIConfigRepository

log = logging.getLogger("charsooq.ai")

DEFAULT_AI_BASE_URL = "https://api.gapgpt.ir/v1"
DEFAULT_AI_MODEL_ID = "gapgpt-deepseek-v4.1-flash"
# Reports favour speed and token-by-token output over deep reasoning.
DEFAULT_ANALYSIS_MODEL_ID = "gpt-4.1-mini"
AI_TIMEOUT_SECONDS = 90.0

AI_NOT_CONFIGURED_MESSAGE = (
    "اتصال هوش مصنوعی تنظیم نشده است؛ آدرس پایه، کلید API و شناسه مدل را در تنظیمات وارد کنید."
)


class AINotConfiguredError(Exception):
    """Base URL, model id, or API key is missing."""


class AIProviderError(Exception):
    """The configured provider could not answer; message is user-facing Persian."""


@dataclass(frozen=True)
class AIStream:
    """Configured model name plus the provider's visible answer chunks."""

    model: str
    chunks: Iterator[str]


@dataclass(frozen=True)
class EffectiveAIConfig:
    base_url: str
    api_key: str
    model_id: str
    analysis_model_id: str
    system_prompt: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model_id)


def _provider_message(exc: AIError) -> str:
    if isinstance(exc, AIAuthError):
        return "کلید API هوش مصنوعی پذیرفته نشد؛ کلید را در تنظیمات بررسی کنید."
    if isinstance(exc, AINetworkError):
        return "ارتباط با سرویس هوش مصنوعی برقرار نشد؛ آدرس پایه و اتصال شبکه را بررسی کنید."
    if isinstance(exc, AIResponseError):
        if exc.status_code in (400, 404, 422):
            return "مدل یا مسیر سرویس هوش مصنوعی پیدا نشد؛ آدرس پایه و شناسه مدل را بررسی کنید."
        if exc.status_code == 429:
            return "سرویس هوش مصنوعی محدودیت تعداد درخواست اعمال کرد؛ کمی بعد دوباره تلاش کنید."
    return "سرویس هوش مصنوعی پاسخ معتبری نداد؛ دوباره تلاش کنید."


class AIService:
    def __init__(self, session: Session) -> None:
        self._config = AIConfigRepository(session)

    def _effective(self, row: AIConfig | None) -> EffectiveAIConfig:
        return EffectiveAIConfig(
            base_url=(row.base_url if row is not None else "").strip() or DEFAULT_AI_BASE_URL,
            api_key=(row.api_key if row is not None else None) or "",
            model_id=(row.model_id if row is not None else "").strip() or DEFAULT_AI_MODEL_ID,
            analysis_model_id=(
                (row.analysis_model_id if row is not None else "").strip()
                or DEFAULT_ANALYSIS_MODEL_ID
            ),
            system_prompt=row.system_prompt if row is not None else "",
        )

    def get_view(self) -> dict[str, object]:
        row = self._config.get()
        effective = self._effective(row)
        return {
            "base_url": effective.base_url,
            "model_id": effective.model_id,
            "analysis_model_id": effective.analysis_model_id,
            "system_prompt": effective.system_prompt,
            "api_key_set": bool(effective.api_key),
            "configured": effective.configured,
        }

    def update(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model_id: str | None = None,
        analysis_model_id: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, object]:
        row = self._config.ensure()
        if base_url is not None:
            row.base_url = base_url.rstrip("/")
        if model_id is not None:
            row.model_id = model_id
        if analysis_model_id is not None:
            row.analysis_model_id = analysis_model_id
        if system_prompt is not None:
            row.system_prompt = system_prompt
        # An empty key means "keep the stored one", matching Parsina's password.
        if api_key is not None and api_key != "":
            row.api_key = api_key
        return self.get_view()

    def _client(
        self, effective: EffectiveAIConfig, *, model_id: str | None = None
    ) -> OpenAICompatibleClient:
        return OpenAICompatibleClient(
            base_url=effective.base_url,
            api_key=effective.api_key,
            model_id=model_id or effective.model_id,
            timeout_seconds=AI_TIMEOUT_SECONDS,
        )

    def _effective_or_raise(self) -> EffectiveAIConfig:
        effective = self._effective(self._config.get())
        if not effective.configured:
            raise AINotConfiguredError(AI_NOT_CONFIGURED_MESSAGE)
        return effective

    def complete(self, messages: Sequence[AIMessage]) -> AICompletion:
        """Send one buffered completion with the configured model and prompt."""
        effective = self._effective_or_raise()
        try:
            return self._client(effective).complete(messages, system_prompt=effective.system_prompt)
        except AIError as exc:
            log.warning("AI completion failed: %s", exc)
            raise AIProviderError(_provider_message(exc)) from exc

    def analysis_model(self) -> str:
        """Model used for product analysis (fast by default)."""
        return self._effective(self._config.get()).analysis_model_id

    def stream(self, messages: Sequence[AIMessage], *, model_id: str | None = None) -> AIStream:
        """Start a streaming completion.

        Configuration is resolved eagerly so the route can return a proper
        error before opening the event stream; provider failures happen while
        the returned iterator is consumed and are mapped to Persian messages.
        ``model_id`` overrides the shared model for one call (product analysis).
        """
        effective = self._effective_or_raise()
        model = (model_id or "").strip() or effective.model_id
        client = self._client(effective, model_id=model)

        def chunks() -> Iterator[str]:
            try:
                yield from client.stream(messages, system_prompt=effective.system_prompt)
            except AIError as exc:
                log.warning("AI streaming failed: %s", exc)
                raise AIProviderError(_provider_message(exc)) from exc

        return AIStream(model=model, chunks=chunks())

    def test_connection(self, prompt: str) -> dict[str, object]:
        started = time.perf_counter()
        completion = self.complete([{"role": "user", "content": prompt}])
        return {
            "model": completion.model,
            "reply": completion.text,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
