# ADR 038 — SSE keepalives for long AI streams

Date: 2026-11-26

## Status

Accepted.

## Context

The product-analysis report (ADR 037) made the AI stream long enough to expose
a transport limit that the short connection test never hit. A reasoning model
can spend well over 30 seconds before its first visible token: the report
measured here took about 80 seconds to start and 92–136 seconds in total.

The panel calls the API through the Next.js dev rewrite proxy. Next limits that
proxy to a 30-second socket timeout by default
(`proxy-request.js`: `proxyTimeout || 30_000`). With no bytes after the initial
`: connected` comment, the proxy destroys the upstream request; the browser
then sees a body-stream failure and the panel reports an incomplete response.
Direct requests to FastAPI completed normally, and the Next source confirms the
default.

## Decision

1. `_stream_events` consumes the provider on a worker thread and emits an SSE
   comment frame (`: ping`) every 10 seconds whenever the provider is silent.
   Comment frames are ignored by the browser parser, so they add no visible
   text; they keep idle-timeout proxies (Next dev, Vercel edge, Caddy) alive
   during reasoning and between slow deltas.
2. An unexpected exception while consuming the provider is logged and turned
   into a terminal `error` frame with a Persian message. The HTTP response must
   never end mid-stream with no terminal event; the client can then show a
   retryable error instead of a generic cutoff.
3. Raise the Next dev rewrite `experimental.proxyTimeout` to five minutes. The
   heartbeat handles idle gaps after headers; the higher proxy timeout also
   covers a slow upstream (for example a slow cardex fetch before headers) and
   removes the 30-second ceiling from the whole report.
4. Keep the existing SSE contract (`delta` / `done` / `error`) and the
   client-side timeout. The new frames are comments, not events, so the
   frontend parser needs no change.

## Alternatives

- **Disable the rewrite for streaming and call the API origin directly**:
  rejected. It would break the first-party cookie and CORS model that the
  same-origin proxy deliberately maintains.
- **Buffer the whole completion and return one JSON response**: rejected. It
  loses progressive output, keeps the connection idle for longer, and makes
  the panel feel hung.
- **Shorten the prompt or model output**: rejected. The report length is a
  product decision; the transport must tolerate it.
- **Only raise `proxyTimeout`**: insufficient. The timeout is per dev proxy;
  other proxies still close idle streams. The keepalive is the portable fix.

## Consequences

- Active streams hold one extra daemon thread while the provider is generating;
  the thread ends when the provider ends or its read timeout fires.
- Keepalive traffic is negligible (one short comment per 10 seconds).
- A client that disconnects leaves the worker to finish or time out (the
  provider read timeout bounds it); no request-scoped DB session is used inside
  the worker.
- Proxies with a total request limit rather than an idle timeout (some hosting
  platforms) can still cut very long reports; the terminal `error` frame and
  the panel retry remain the fallback.
- The dev proxy timeout applies to every rewritten API call, not only AI; five
  minutes is still a bounded request.
