"""AI settings, completion service, and chat-completions client (mocked HTTP)."""

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations.openai_compatible import (
    AIAuthError,
    AICompletion,
    AIError,
    AINetworkError,
    AIResponseError,
    OpenAICompatibleClient,
)
from tests.helpers import login, login_as, login_owner

SETTINGS_URL = "/api/v1/ai/settings"
TEST_URL = "/api/v1/ai/test"
STREAM_URL = "/api/v1/ai/stream"
DEFAULT_BASE_URL = "https://api.gapgpt.ir/v1"
DEFAULT_MODEL_ID = "gapgpt-deepseek-v4.1-flash"


def _client(handler: Any) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="https://ai.test/v1/",
        api_key="sk-test",
        model_id="test-model",
        transport=httpx.MockTransport(handler),
    )


def _completion(content: Any) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "test-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
    }


# ── Client contract ─────────────────────────────────────────


def test_client_posts_chat_completions_with_system_prompt() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.read().decode()
        return httpx.Response(200, json=_completion("سلام"))

    completion = _client(handler).complete(
        [{"role": "user", "content": "سلام!"}],
        system_prompt="دستیار فروشگاه باش.",
    )

    assert completion == AICompletion(text="سلام", model="test-model")
    assert captured["url"] == "https://ai.test/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert '"role":"system"' in str(captured["body"])
    assert '"role":"user"' in str(captured["body"])
    assert "دستیار فروشگاه باش." in str(captured["body"])


def test_client_accepts_typed_content_parts() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "سلام "},
                                {"type": "text", "text": "دنیا"},
                            ]
                        }
                    }
                ]
            },
        )

    assert _client(handler).complete([]).text == "سلام دنیا"


def test_client_rejects_bad_credentials() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(AIAuthError):
        _client(handler).complete([])


def test_client_maps_provider_errors_without_leaking_the_key() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"message": "model not found"}})

    with pytest.raises(AIResponseError) as excinfo:
        _client(handler).complete([])
    assert excinfo.value.status_code == 404
    assert "model not found" in str(excinfo.value)
    assert "sk-test" not in str(excinfo.value)


def test_client_maps_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(AINetworkError):
        _client(handler).complete([])


def test_client_rejects_non_json_and_empty_responses() -> None:
    def non_json(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>oops</html>")

    with pytest.raises(AIResponseError):
        _client(non_json).complete([])

    def empty(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion("   "))

    with pytest.raises(AIResponseError):
        _client(empty).complete([])


def test_client_requires_complete_configuration() -> None:
    client = OpenAICompatibleClient(base_url="", api_key="", model_id="")
    with pytest.raises(AIError):
        client.complete([])


def test_client_streams_sse_deltas_and_skips_reasoning() -> None:
    frames = [
        {"choices": [{"delta": {"reasoning_content": "فکر"}}]},
        {"choices": [{"delta": {"content": "سلام"}}]},
        {"choices": [{"delta": {"content": " دنیا"}}]},
    ]
    body = (
        "".join(f"data: {json.dumps(frame, ensure_ascii=False)}\n\n" for frame in frames)
        + "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.read())["stream"] is True
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body.encode(),
        )

    chunks = list(
        _client(handler).stream(
            [{"role": "user", "content": "سلام"}],
            system_prompt="فارسی پاسخ بده.",
        )
    )
    assert chunks == ["سلام", " دنیا"]


def test_client_stream_falls_back_to_a_full_json_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=_completion("سلام"),
        )

    assert list(_client(handler).stream([])) == ["سلام"]


def test_client_stream_maps_auth_and_provider_errors() -> None:
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(AIAuthError):
        list(_client(unauthorized).stream([]))

    def server_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "boom"}})

    with pytest.raises(AIResponseError) as excinfo:
        list(_client(server_error).stream([]))
    assert excinfo.value.status_code == 500


def test_client_stream_rejects_empty_streams_and_error_frames() -> None:
    def empty(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b"data: [DONE]\n\n",
        )

    with pytest.raises(AIResponseError):
        list(_client(empty).stream([]))

    def stream_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"error": {"message": "quota exceeded"}}\n\n',
        )

    with pytest.raises(AIResponseError) as excinfo:
        list(_client(stream_error).stream([]))
    assert "quota exceeded" in str(excinfo.value)


# ── Management-only settings ────────────────────────────────


def test_ai_settings_require_a_management_account(client: TestClient) -> None:
    assert client.get(SETTINGS_URL).status_code == 401
    assert client.put(SETTINGS_URL, json={"model_id": "x"}).status_code == 401
    assert client.post(TEST_URL, json={"prompt": "سلام"}).status_code == 401

    # Admins can read, save, and test the shared connection.
    login(client)
    assert client.get(SETTINGS_URL).status_code == 200
    assert client.put(SETTINGS_URL, json={"model_id": "admin-model"}).status_code == 200
    assert client.post(TEST_URL, json={"prompt": "سلام"}).status_code == 503

    # Viewers stay read-only.
    created = client.post(
        "/api/v1/users",
        json={"username": "ai-viewer", "password": "viewer-pass-123", "role": "viewer"},
    )
    assert created.status_code == 201, created.text
    login_as(client, "ai-viewer", "viewer-pass-123")
    assert client.get(SETTINGS_URL).status_code == 403
    assert client.put(SETTINGS_URL, json={"model_id": "x"}).status_code == 403
    assert client.post(TEST_URL, json={"prompt": "سلام"}).status_code == 403


def test_ai_stream_remains_owner_only(client: TestClient) -> None:
    assert client.post(STREAM_URL, json={"prompt": "سلام"}).status_code == 401
    login(client)
    assert client.post(STREAM_URL, json={"prompt": "سلام"}).status_code == 403


def test_ai_settings_defaults(client: TestClient) -> None:
    login_owner(client)
    r = client.get(SETTINGS_URL)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "base_url": DEFAULT_BASE_URL,
        "model_id": DEFAULT_MODEL_ID,
        "system_prompt": "",
        "api_key_set": False,
        "configured": False,
    }


def test_ai_settings_update_never_returns_the_key(client: TestClient) -> None:
    login_owner(client)
    r = client.put(
        SETTINGS_URL,
        json={
            "base_url": "https://ai.example/v1/",
            "api_key": "sk-owner-secret",
            "model_id": "own-model",
            "system_prompt": "تو دستیار چهارسوق هستی.",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["base_url"] == "https://ai.example/v1"
    assert data["model_id"] == "own-model"
    assert data["system_prompt"] == "تو دستیار چهارسوق هستی."
    assert data["api_key_set"] is True
    assert data["configured"] is True
    assert "api_key" not in data
    assert "sk-owner-secret" not in r.text

    # A GET exposes the same state, never the secret.
    fetched = client.get(SETTINGS_URL)
    assert fetched.json()["api_key_set"] is True
    assert "sk-owner-secret" not in fetched.text

    # An empty key keeps the stored one; an empty prompt clears only the prompt.
    kept = client.put(SETTINGS_URL, json={"api_key": "", "system_prompt": ""})
    assert kept.status_code == 200, kept.text
    assert kept.json()["api_key_set"] is True
    assert kept.json()["system_prompt"] == ""
    assert kept.json()["configured"] is True


def test_ai_settings_empty_endpoint_fields_fall_back_to_defaults(client: TestClient) -> None:
    login_owner(client)
    client.put(
        SETTINGS_URL,
        json={
            "base_url": "https://ai.example/v1",
            "api_key": "sk-test",
            "model_id": "own-model",
        },
    )
    cleared = client.put(
        SETTINGS_URL,
        json={"base_url": "", "model_id": "", "api_key": ""},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["base_url"] == DEFAULT_BASE_URL
    assert cleared.json()["model_id"] == DEFAULT_MODEL_ID
    assert cleared.json()["api_key_set"] is True


def test_ai_settings_reject_invalid_values(client: TestClient) -> None:
    login_owner(client)
    assert client.put(SETTINGS_URL, json={"base_url": "not-a-url"}).status_code == 422
    assert client.put(SETTINGS_URL, json={"base_url": "ftp://ai.test/v1"}).status_code == 422
    assert client.put(SETTINGS_URL, json={"system_prompt": "x" * 20_001}).status_code == 422


# ── Connection test ─────────────────────────────────────────


def test_ai_test_requires_configuration(client: TestClient) -> None:
    login_owner(client)
    r = client.post(TEST_URL, json={"prompt": "سلام"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "service_unavailable"
    assert "تنظیم نشده" in r.json()["error"]["message"]


def test_ai_test_rejects_blank_prompt(client: TestClient) -> None:
    login_owner(client)
    assert client.post(TEST_URL, json={"prompt": "   "}).status_code == 422
    assert client.post(TEST_URL, json={}).status_code == 422


def test_ai_test_returns_model_reply_and_uses_the_system_prompt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    login_owner(client)
    client.put(
        SETTINGS_URL,
        json={
            "base_url": "https://ai.example/v1",
            "api_key": "sk-test",
            "model_id": "test-model",
            "system_prompt": "فقط فارسی پاسخ بده.",
        },
    )
    captured: dict[str, Any] = {}

    def fake_complete(
        self: OpenAICompatibleClient,
        messages: Any,
        *,
        system_prompt: str = "",
    ) -> AICompletion:
        captured["messages"] = messages
        captured["system_prompt"] = system_prompt
        return AICompletion(text="سلام، آماده‌ام.", model="test-model")

    monkeypatch.setattr(OpenAICompatibleClient, "complete", fake_complete)

    r = client.post(TEST_URL, json={"prompt": "سلام"})
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "سلام، آماده‌ام."
    assert r.json()["model"] == "test-model"
    assert r.json()["latency_ms"] >= 0
    assert captured["system_prompt"] == "فقط فارسی پاسخ بده."
    assert captured["messages"] == [{"role": "user", "content": "سلام"}]


def test_ai_test_maps_provider_failures_to_bad_gateway(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    login_owner(client)
    client.put(
        SETTINGS_URL,
        json={"base_url": "https://ai.example/v1", "api_key": "sk-test", "model_id": "m"},
    )

    def fake_complete(
        self: OpenAICompatibleClient,
        messages: Any,
        *,
        system_prompt: str = "",
    ) -> AICompletion:
        raise AIAuthError("rejected")

    monkeypatch.setattr(OpenAICompatibleClient, "complete", fake_complete)

    r = client.post(TEST_URL, json={"prompt": "سلام"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "bad_gateway"
    assert "کلید API" in r.json()["error"]["message"]


# ── Streaming endpoint ──────────────────────────────────────


def test_ai_stream_requires_configuration(client: TestClient) -> None:
    login_owner(client)
    r = client.post(STREAM_URL, json={"prompt": "سلام"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "service_unavailable"
    assert "تنظیم نشده" in r.json()["error"]["message"]


def test_ai_stream_rejects_blank_prompt(client: TestClient) -> None:
    login_owner(client)
    assert client.post(STREAM_URL, json={"prompt": "   "}).status_code == 422


def test_ai_stream_emits_delta_and_done_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    login_owner(client)
    client.put(
        SETTINGS_URL,
        json={
            "base_url": "https://ai.example/v1",
            "api_key": "sk-test",
            "model_id": "test-model",
            "system_prompt": "فقط فارسی پاسخ بده.",
        },
    )
    captured: dict[str, Any] = {}

    def fake_stream(
        self: OpenAICompatibleClient,
        messages: Any,
        *,
        system_prompt: str = "",
    ) -> Any:
        captured["messages"] = messages
        captured["system_prompt"] = system_prompt
        yield "سلام"
        yield "، آماده‌ام."

    monkeypatch.setattr(OpenAICompatibleClient, "stream", fake_stream)

    r = client.post(STREAM_URL, json={"prompt": "سلام"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in r.text
    assert 'data: {"text": "سلام"}' in r.text
    assert 'data: {"text": "، آماده‌ام."}' in r.text
    assert "event: done" in r.text
    assert '"model": "test-model"' in r.text
    assert '"latency_ms"' in r.text
    assert captured["system_prompt"] == "فقط فارسی پاسخ بده."
    assert captured["messages"] == [{"role": "user", "content": "سلام"}]


def test_ai_stream_reports_provider_failure_as_an_error_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    login_owner(client)
    client.put(
        SETTINGS_URL,
        json={"base_url": "https://ai.example/v1", "api_key": "sk-test", "model_id": "m"},
    )

    def failing_stream(
        self: OpenAICompatibleClient,
        messages: Any,
        *,
        system_prompt: str = "",
    ) -> Any:
        yield "نیمه"
        raise AIAuthError("rejected")

    monkeypatch.setattr(OpenAICompatibleClient, "stream", failing_stream)

    r = client.post(STREAM_URL, json={"prompt": "سلام"})
    assert r.status_code == 200, r.text
    assert 'data: {"text": "نیمه"}' in r.text
    assert "event: error" in r.text
    assert "کلید API" in r.text


# ── SSE keepalive ─────────────────────────────────────────────────────


def test_stream_events_emits_keepalives_while_the_model_is_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    from app.api.routes.ai import _stream_events
    from app.services.ai import AIStream

    monkeypatch.setattr("app.api.routes.ai.SSE_HEARTBEAT_SECONDS", 0.01)

    def chunks() -> Any:
        time.sleep(0.05)
        yield "سلام"

    frames = list(_stream_events(AIStream(model="test-model", chunks=chunks())))
    assert ": ping\n\n" in frames
    assert frames[-1].startswith("event: done")


def test_stream_events_turns_an_unexpected_failure_into_a_terminal_error() -> None:
    from app.api.routes.ai import _stream_events
    from app.services.ai import AIStream

    def chunks() -> Any:
        yield "یک"
        raise RuntimeError("provider pipe broke")

    frames = list(_stream_events(AIStream(model="test-model", chunks=chunks())))
    assert any(frame.startswith("event: error") for frame in frames)
    assert not any(frame.startswith("event: done") for frame in frames)
