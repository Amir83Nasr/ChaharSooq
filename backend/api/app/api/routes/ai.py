"""AI settings and connection-test handlers — owner only.

The owner enters the OpenAI-compatible endpoint, model, API key, and shared
system prompt from the panel. The key is write-only: it is accepted by PUT and
never returned; only `api_key_set` leaves the API.
"""

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_db_readonly, require_owner
from app.api.openapi import (
    BAD_GATEWAY,
    FORBIDDEN,
    SERVICE_UNAVAILABLE,
    UNAUTHORIZED,
    VALIDATION_ERROR,
)
from app.models import Admin
from app.schemas import AISettingsIn, AISettingsOut, AITestIn, AITestOut
from app.services import AINotConfiguredError, AIProviderError, AIService, AIStream

router = APIRouter(prefix="/ai", tags=["AI"], responses={401: UNAUTHORIZED})


def _sse(event: str, data: dict[str, object]) -> str:
    """One SSE frame. JSON data keeps newlines and Persian text intact."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_events(stream: AIStream) -> Iterator[str]:
    """Translate service chunks into delta/done/error SSE events.

    Headers are already sent by the time the first provider error appears, so
    a failure after the stream opens is a terminal `error` event rather than a
    non-2xx status. The UI renders its Persian message.
    """
    started = time.perf_counter()
    yield ": connected\n\n"
    try:
        for chunk in stream.chunks:
            yield _sse("delta", {"text": chunk})
        yield _sse(
            "done",
            {
                "model": stream.model,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            },
        )
    except AIProviderError as exc:
        yield _sse("error", {"message": str(exc)})


@router.get(
    "/settings",
    response_model=AISettingsOut,
    summary="Read AI settings",
    description=(
        "Effective OpenAI-compatible base URL, model id, shared system prompt, "
        "and whether an API key is stored. The key itself is never returned."
    ),
    responses={403: FORBIDDEN},
)
def get_ai_settings(
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> AISettingsOut:
    return AISettingsOut.model_validate(AIService(session).get_view())


@router.put(
    "/settings",
    response_model=AISettingsOut,
    summary="Update AI settings",
    description=(
        "Partial update of the AI connection. Omitted fields keep their value; "
        "an empty `api_key` keeps the stored key, an empty `system_prompt` "
        "clears it. Owner only."
    ),
    responses={403: FORBIDDEN, 422: VALIDATION_ERROR},
)
def update_ai_settings(
    payload: AISettingsIn,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> AISettingsOut:
    view = AIService(session).update(
        base_url=payload.base_url,
        api_key=payload.api_key,
        model_id=payload.model_id,
        system_prompt=payload.system_prompt,
    )
    return AISettingsOut.model_validate(view)


@router.post(
    "/test",
    response_model=AITestOut,
    summary="Test the AI connection",
    description=(
        "Sends one prompt through the configured model and returns its reply. "
        "Returns `503` when the connection is not configured and `502` when the "
        "provider rejects or cannot answer the request. Owner only."
    ),
    responses={
        403: FORBIDDEN,
        422: VALIDATION_ERROR,
        502: BAD_GATEWAY,
        503: SERVICE_UNAVAILABLE,
    },
)
def test_ai_connection(
    payload: AITestIn,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> AITestOut:
    try:
        result = AIService(session).test_connection(payload.prompt)
    except AINotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from None
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from None
    return AITestOut.model_validate(result)


@router.post(
    "/stream",
    response_class=StreamingResponse,
    response_model=None,
    summary="Stream an AI reply",
    description=(
        "Sends one prompt and streams the model reply as Server-Sent Events: "
        '`delta` frames carry `{"text": ...}`, the terminal `done` frame '
        "carries `model` and `latency_ms`, and a post-open provider failure is "
        "reported as a terminal `error` frame with a Persian message. Returns "
        "`503` before the stream when the connection is not configured. Owner only."
    ),
    responses={
        200: {
            "description": "SSE stream of delta/done/error events.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        403: FORBIDDEN,
        422: VALIDATION_ERROR,
        503: SERVICE_UNAVAILABLE,
    },
)
def stream_ai_connection(
    payload: AITestIn,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> StreamingResponse:
    try:
        stream = AIService(session).stream([{"role": "user", "content": payload.prompt}])
    except AINotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from None
    return StreamingResponse(
        _stream_events(stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
