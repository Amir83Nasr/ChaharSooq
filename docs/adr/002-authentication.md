# ADR 002 — Admin password authentication (Argon2id + server sessions)

Date: 2026-10-04 · Status: accepted

## Context

Admin panel needs a simple, secure login without public registration or OAuth.

## Decision

- Argon2id password hashing; opaque server-side sessions in `admin_sessions`.
- `HttpOnly` cookie (`Secure` in production, `SameSite=Lax`), 12h TTL.
- 10/min IP login rate limit; non-sensitive Persian error messages; no secret logging.

## Alternatives

- JWT in `localStorage`: rejected — XSS token theft, spec forbids without documented reason.
- OAuth/public signup: rejected — out of scope for v1.

## Consequences

- Requires DB-backed session cleanup story later; CSRF risk accepted via `SameSite=Lax` + narrow methods, revisit with mutations growth.
