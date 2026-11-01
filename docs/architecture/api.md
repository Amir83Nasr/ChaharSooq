# API — چهارسوق

Base: `/api/v1`. OpenAPI served by FastAPI (`/openapi.json`, `/docs`); committed snapshot via `backend/api/scripts/export_openapi.py` → `backend/api/openapi.json`.

| Method & path | Auth | Description |
| --- | --- | --- |
| `GET /api/v1/health` | no | liveness |
| `POST /api/v1/auth/login` | no (rate-limited) | `{username, password}` → `{ok}` + session cookie; wrong credentials → `401 unauthorized` (`نام کاربری یا گذرواژه نادرست است`), missing/short fields → `422 validation_error` with Persian field messages in `details` |
| `POST /api/v1/auth/logout` | cookie if present | clears session → 204 |
| `GET /api/v1/auth/me` | yes | `{username}` |
| `GET /api/v1/products?q=&page=&page_size=` | yes | paginated products (server-side, max 100/page). Filters: `q`, `category_id`, `min_price`/`max_price`, `in_stock`, `min_stock`/`max_stock` |
| `POST /api/v1/products` | yes | create product (toman integer) → 201 |
| `GET /api/v1/integrations/parsina/status` | yes | sync state: `configured`, `source` (`parsina` \| `csv`), `running`, `running_since`, `last_attempt_at`, `last_success_at`, `last_error`, last-run counters, `interval_minutes` |
| `POST /api/v1/integrations/parsina/sync` | yes | starts a manual sync in the background → `202 {status: "running"}`; `409 conflict` when any run (manual or scheduled) already holds the lock; `503` when the source is not configured. Production syncs Parsina; development re-imports `data/parsina-products.csv` |
| `GET /api/v1/settings` | yes | `{low_stock_threshold, default_page_size, sync_interval_minutes, suggested_price_formulas}` — formulas are category-specific arithmetic expressions using `x` |
| `PUT /api/v1/settings` | yes | partial settings update; `suggested_price_formulas` replaces the saved `{category_id, expression}` list. Expressions allow numeric constants, `x`, and arithmetic operators |

Errors: `{ error: { code, message, details? } }` with codes `unauthorized`, `validation_error`, `rate_limited`. All user-facing `message` and `details` strings are Persian — the frontend never surfaces raw fetch/network/English errors and maps missing-body cases to per-status Persian fallbacks (`ApiRequestError` carries `status`, `code`, `details`).

Frontend client: `apps/web/lib/api.ts` (fetch, `credentials: include`, Persian error surfacing).
