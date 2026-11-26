"""OpenAI-compatible chat completions client.

GapGPT (and most gateways) expose the OpenAI wire format at
``POST {base_url}/chat/completions``. This module is transport only: it knows
nothing about the stored settings, the system prompt, or which feature is
calling. ``AIService`` owns those decisions so every future AI feature shares
one request path.

Both the buffered response and the streaming SSE response are handled here.
Streaming yields only visible answer text; provider ``reasoning_content`` and
keepalive events are ignored.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal, TypedDict

import httpx

log = logging.getLogger("charsooq.ai")

DEFAULT_TIMEOUT_SECONDS = 90.0


class AIMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class AICompletion:
    """One non-streaming model reply plus the provider-reported model id."""

    text: str
    model: str


class AIError(Exception):
    """Base class — transport, auth, and contract failures stay distinguishable."""


class AINetworkError(AIError):
    """Connection failure, timeout, or another transport-level error."""


class AIAuthError(AIError):
    """The provider rejected the API key (HTTP 401/403)."""


class AIResponseError(AIError):
    """Non-2xx status, non-JSON body, or a response without usable text."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    # Some OpenAI-compatible providers return content as typed parts.
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _completion_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise AIResponseError("AI provider returned an unexpected body")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIResponseError("AI provider returned no choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise AIResponseError("AI provider returned a malformed choice")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise AIResponseError("AI provider returned no message")
    return _content_text(message.get("content")).strip()


def _delta_text(payload: object) -> str:
    """Visible answer text from one stream chunk (never reasoning text)."""
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0]
    if not isinstance(choice, dict):
        return ""
    delta = choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    return _content_text(delta.get("content"))


def _completion_model(payload: object, fallback: str) -> str:
    if isinstance(payload, dict):
        model = payload.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return fallback


def _error_detail(response: httpx.Response) -> str:
    """Provider message for diagnostics — never headers or credentials."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    message = error.get("message") if isinstance(error, dict) else body.get("message")
    if isinstance(message, str):
        return f": {message.strip()[:300]}"
    return ""


def _stream_error(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    message = error.get("message")
    return message.strip()[:300] if isinstance(message, str) else ""


class OpenAICompatibleClient:
    """Minimal chat-completions client for an owner-configured endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_id: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model_id = model_id
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def _payload(
        self,
        messages: Sequence[AIMessage],
        *,
        system_prompt: str,
        stream: bool,
    ) -> dict[str, object]:
        payload_messages: list[AIMessage] = []
        if system_prompt.strip():
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(messages)
        payload: dict[str, object] = {
            "model": self._model_id,
            "messages": payload_messages,
        }
        if stream:
            payload["stream"] = True
        return payload

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self._timeout_seconds,
            transport=self._transport,
        )

    @property
    def _endpoint(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _ensure_configured(self) -> None:
        if not self._base_url or not self._api_key or not self._model_id:
            raise AIError("AI provider is not configured")

    def complete(
        self,
        messages: Sequence[AIMessage],
        *,
        system_prompt: str = "",
    ) -> AICompletion:
        self._ensure_configured()
        payload = self._payload(messages, system_prompt=system_prompt, stream=False)

        try:
            with self._client() as client:
                response = client.post(
                    self._endpoint,
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise AINetworkError(f"AI request failed: {type(exc).__name__}") from exc

        if response.status_code in (401, 403):
            raise AIAuthError(f"AI provider rejected the credentials (HTTP {response.status_code})")
        if response.is_error:
            raise AIResponseError(
                f"AI provider returned HTTP {response.status_code}{_error_detail(response)}",
                status_code=response.status_code,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AIResponseError(
                "AI provider returned a non-JSON body",
                status_code=response.status_code,
            ) from exc

        text = _completion_text(body)
        if not text:
            raise AIResponseError(
                "AI provider returned an empty completion",
                status_code=response.status_code,
            )
        return AICompletion(text=text, model=_completion_model(body, self._model_id))

    def stream(
        self,
        messages: Sequence[AIMessage],
        *,
        system_prompt: str = "",
    ) -> Iterator[str]:
        """Yield visible answer text as the provider emits it.

        Errors are raised while the returned iterator is consumed, because the
        HTTP request itself is opened lazily.
        """
        self._ensure_configured()
        payload = self._payload(messages, system_prompt=system_prompt, stream=True)

        try:
            with (
                self._client() as client,
                client.stream(
                    "POST",
                    self._endpoint,
                    headers=self._headers(),
                    json=payload,
                ) as response,
            ):
                if response.status_code in (401, 403):
                    raise AIAuthError(
                        f"AI provider rejected the credentials (HTTP {response.status_code})"
                    )
                if response.is_error:
                    response.read()
                    raise AIResponseError(
                        f"AI provider returned HTTP {response.status_code}"
                        f"{_error_detail(response)}",
                        status_code=response.status_code,
                    )

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    # Some gateways ignore stream=true and send one full body.
                    response.read()
                    try:
                        body = response.json()
                    except ValueError as exc:
                        raise AIResponseError(
                            "AI provider returned a non-JSON body",
                            status_code=response.status_code,
                        ) from exc
                    text = _completion_text(body)
                    if not text:
                        raise AIResponseError("AI provider returned an empty completion")
                    yield text
                    return

                emitted = False
                for raw_line in response.iter_lines():
                    line = raw_line.rstrip("\r")
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError as exc:
                        raise AIResponseError("AI provider sent a malformed stream chunk") from exc
                    stream_error = _stream_error(chunk)
                    if stream_error:
                        raise AIResponseError(f"AI provider stream error: {stream_error}")
                    text = _delta_text(chunk)
                    if text:
                        emitted = True
                        yield text
                if not emitted:
                    raise AIResponseError("AI provider returned an empty stream")
        except httpx.HTTPError as exc:
            raise AINetworkError(f"AI request failed: {type(exc).__name__}") from exc


__all__ = [
    "AICompletion",
    "AIAuthError",
    "AIError",
    "AIMessage",
    "AINetworkError",
    "AIResponseError",
    "OpenAICompatibleClient",
]
