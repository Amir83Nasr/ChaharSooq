# ADR 036 — Streaming AI replies over Server-Sent Events

Date: 2026-11-26

## Status

Accepted. Extends [ADR 035](035-ai-provider-foundation.md).

## Context

The buffered completion endpoint returns the whole answer at once. With a
reasoning model the first visible character can take seconds, so the panel
feels idle even though the provider is working. The owner asked for
token-by-token output to make the answer feel immediate.

The provider already supports `stream: true` on the same chat-completions
endpoint. The browser needs a transport that can send a POST body, carry the
HttpOnly session cookie, surface provider errors, and be cancelled by the
user. The admin panel must stay same-origin through the Next.js proxy.

## Decision

1. `OpenAICompatibleClient.stream()` opens the same
   `POST {base_url}/chat/completions` request with `"stream": true` and parses
   the SSE `data:` frames incrementally. It yields only visible
   `choices[0].delta.content`; `reasoning_content`, `event:`/`id:` lines, and
   keepalives are ignored. `[DONE]` terminates the stream, and a provider that
   ignores `stream` and returns one `application/json` body is accepted as a
   single chunk.
2. Add owner-only `POST /api/v1/ai/stream`. The response is
   `text/event-stream` with `Cache-Control: no-cache` and
   `X-Accel-Buffering: no` (for a buffering reverse proxy). It starts with a
   `: connected` comment so the client receives headers before the first token.
3. The event contract is:
   - `event: delta`, `data: {"text": "..."}` for every visible chunk;
   - `event: done`, `data: {"model": "...", "latency_ms": 1234}` once;
   - `event: error`, `data: {"message": "..."}` as the terminal event when the
     provider fails after the stream has opened. The message is Persian.
4. Configuration is resolved before the `StreamingResponse` is created, so a
   missing base URL/key/model still returns the normal `503` JSON envelope.
   Provider failures after headers are sent cannot change the status, hence the
   terminal `error` event instead of a `502`.
5. The browser uses `fetch` + `ReadableStream`, not `EventSource`: it must send
   a JSON body and the same-origin cookie, and `EventSource` supports neither.
   `streamAIRequest` decodes chunks with `TextDecoder`, tolerates frames split
   across reads, supports `AbortSignal`, and enforces a 180-second total
   timeout. The settings test panel renders deltas as they arrive and offers a
   «توقف» button that aborts the request; a stopped stream keeps the partial
   text without an error toast.
6. `POST /api/v1/ai/test` remains as the buffered variant for non-interactive
   callers. Both paths share `AIService` configuration and error mapping.

## Alternatives

- **WebSocket**: rejected. Streaming is one-way here; WebSockets add a second
  auth path, connection lifecycle, and proxy configuration with no benefit.
- **Polling a job**: rejected. It adds server state and still cannot deliver
  sub-second chunks.
- **`EventSource`**: rejected. It cannot POST a prompt body or send custom
  headers, and it hides non-2xx bodies.
- **NDJSON**: workable, but SSE is the format the provider emits and the
  browser ecosystem documents; reusing it keeps the transport obvious.

## Consequences

- Clients must treat an SSE `error` event as a failure even though HTTP status
  is `200`; the web client maps it to `ApiRequestError` and shows the message.
- Partial replies are not persisted by the API. Any feature that needs a saved
  answer must collect the deltas client-side and submit it, so a dropped
  stream never looks like a completed response.
- Every proxy between the browser and FastAPI must pass chunks through. The
  Next rewrite streams, Caddy streams by default, and the explicit
  `X-Accel-Buffering: no` covers nginx-style buffering.
- The test panel no longer shows only the final answer; it is also the
  reference implementation for future streaming features.
