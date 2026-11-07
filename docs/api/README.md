# API contract — چهارسوق

The FastAPI service is the source of truth for the HTTP contract. Base path: `/api/v1`.

| Location                                                   | Purpose                                           |
| ---------------------------------------------------------- | ------------------------------------------------- |
| `/docs`                                                    | Swagger UI: browse, inspect schemas, try requests |
| `/redoc`                                                   | Read-only reference                               |
| `/openapi.json`                                            | Live OpenAPI document generated from the app      |
| [backend/api/openapi.json](../../backend/api/openapi.json) | Committed snapshot — CI fails when it is stale    |

Endpoint behavior lives in [architecture/api.md](../architecture/api.md). Layer boundaries live in
[architecture/backend.md](../architecture/backend.md).

## Using Swagger

1. Start the API: `make dev-api` (or `make dev-all`), then open <http://localhost:8000/docs>.
2. Call `POST /api/v1/auth/login` with the dev admin (`ADMIN_USER`, `ADMIN_PASSWORD`; the
   local seed defaults to `admin` / `secret123`).
3. The server sets the HttpOnly `charsooq_session` cookie. Because Swagger UI and the API share
   an origin, the browser sends it with every following request — no token to paste.
4. Operations are grouped by tag: Health, Auth, Dashboard, Products, Categories, Competitors,
   Integrations, Settings. Protected operations show a lock icon and list `401` in their
   responses.

The **Authorize** dialog documents the cookie scheme for non-browser clients. Such clients should
call `login`, keep the returned `Set-Cookie` value, and forward it as a `Cookie` header.

> Never enter production credentials into a shared or deployed Swagger page. Use the login
> endpoint there, not the Authorize dialog.

## Conventions

- **Auth:** one session per admin. A new login rotates the server-side session, so older cookies
  stop working. Missing or expired sessions return `401 unauthorized`.
- **Errors:** every failure uses `{"error": {"code", "message", "details?"}}`. `message` and
  `details` are Persian, ready for the UI; `code` is stable and machine-readable.
- **Machine values:** Toman amounts without symbols, UTC timestamps, ISO dates. The frontend
  applies Persian digits, `٬` grouping, and the Jalali calendar only at render time.
- **Pagination:** `page` starts at 1. `page_size=0` means “show all” without an offset; an explicit
  size is clamped to 500.
- **Caching:** `GET /categories` and `GET /products/groups` return a weak `ETag` plus
  `Cache-Control: private, max-age=60`.
- **Background jobs:** sync triggers return `202` immediately. Counters and errors arrive through
  the matching `GET …/status` endpoint.

## Regenerating the snapshot

Run after any route or schema change, from the repository root:

```bash
uv run --project backend/api python backend/api/scripts/export_openapi.py
```

`make openapi-check` (also part of `make check`, CI, and the pre-commit hook) fails when the
committed snapshot differs from the app. Never edit `backend/api/openapi.json` by hand.

The frontend client (`apps/web/lib/api.ts` and `apps/web/lib/api-types.ts`) mirrors these shapes
manually until codegen lands: update both sides in the same change and run `make typecheck`.
