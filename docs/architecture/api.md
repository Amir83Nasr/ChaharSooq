# API — چهارسوق

Base: `/api/v1`. OpenAPI served by FastAPI (`/openapi.json`, `/docs`); committed snapshot via `backend/api/scripts/export_openapi.py` → `backend/openapi.json`.

| Method & path | Auth | Description |
| --- | --- | --- |
| `GET /api/v1/health` | no | liveness |
| `POST /api/v1/auth/login` | no (rate-limited) | `{username, password}` → `{ok}` + session cookie |
| `POST /api/v1/auth/logout` | cookie if present | clears session → 204 |
| `GET /api/v1/auth/me` | yes | `{username}` |
| `GET /api/v1/products?q=&page=&page_size=` | yes | paginated products (server-side, max 100/page) |
| `POST /api/v1/products` | yes | create product (toman integer) → 201 |

Errors: `{ error: { code, message, details? } }` with codes `unauthorized`, `validation_error`, `rate_limited`.

Frontend client: `apps/web/lib/api.ts` (fetch, `credentials: include`, Persian error surfacing).
