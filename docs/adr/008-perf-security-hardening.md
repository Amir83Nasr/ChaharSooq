# ADR 008 — Performance + security hardening round (backend & frontend)

Date: 2026-11-06 · Status: accepted

## Context

Review of the Charsooq stack (FastAPI + PostgreSQL, Next.js proxy,
single-admin panel) found no architectural violation — layers
(`routes → services → repositories`), RTL/font rules, and the same-origin
API proxy were all sound — but several compounding costs and risks:

- `dashboard/overview` cost 4 round-trips per view; `deactivate_missing`
  loaded ORM objects in a loop; every GET ran through a committing session.
- Product search (`ilike %q%`) had no trigram/composite index coverage.
- Rate limiting was per-process memory (dead on multi-worker); login never
  rotated sessions; HSTS fired on plain-HTTP dev too.
- The frontend fetched overview → catalog → statuses sequentially where one
  aggregated call does; `lib/api.ts` was a 485-line mono-module; "show all"
  serialized an unbounded result set.
- `SESSION_SECRET` accepted short values in production; compose baked a
  placeholder secret into the image env.

## Decision

Harden in place, no migration of frameworks, no new component library:

- Backend: combined coverage/appliance scalar query (4→3 round-trips),
  bulk-update deactivate, read-only sessions for GET, `0012_search_indexes`
  (trigram GIN on PostgreSQL + composite B-tree), Redis-or-memory rate
  limiter, single-session rotation on login, prod-only HSTS,
  `Settings.source_mode` as the one scheduler/sync branch.
- API: `GET /dashboard/summary` (empty-catalog short-circuit), `SHOW_ALL_MAX`
  cap (2000) on `page_size=0` both sides, `Cache-Control: private, max-age=60`
  - `ETag` on groups/categories, OpenAPI snapshot refreshed in-repo.
- Frontend: `lib/api.ts` split into `api-types` / `api-params` /
  `api-cache` (same `api.*` surface), request timeout (15s) + cancellable
  status reads kept, dashboard via one summary + parallel statuses, capped
  "show all" notice, `getSessionAdmin` 5s timeout, CSP frame-ancestors +
  Permissions-Policy on Next headers, shared `scripts/load-env.mjs`.
- Deploy: uvicorn `--workers 2 --proxy-headers --no-server-header`,
  compose resource limits + secret-via-environment, postgres pinned minor.
- Observability: `scripts/bench-api.py` (stdlib-only) + `docs/perf-baseline.md`.

## Consequences

- Dashboard renders in ~2 fetches after settings (was 4 sequential-ish);
  "show all" can never OOM the API or the DOM past 2000 rows.
- Multi-worker rate limiting works when `REDIS_URL` is set (plus the optional
  `redis` library, intentionally not a hard dep — see the pyproject note);
  without it the previous memory behavior (and its single-replica limit) stays.
- A fresh login kills older sessions — re-login is required on other
  devices, intended for a single-admin panel.
- `turbo.json` needed no change (web build inputs already cover env);
  recorded here so the next review doesn't re-ask.
