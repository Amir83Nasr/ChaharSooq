# API — چهارسوق

Base: `/api/v1`. OpenAPI served by FastAPI (`/openapi.json`, `/docs`); committed snapshot via `backend/api/scripts/export_openapi.py` → `backend/openapi.json`.

| Method & path | Auth | Description |
| --- | --- | --- |
| `GET /api/v1/health` | no | liveness |
| `POST /api/v1/auth/login` | no (rate-limited) | `{username, password}` → `{ok}` + session cookie; wrong credentials → `401 unauthorized` (`نام کاربری یا گذرواژه نادرست است`), missing/short fields → `422 validation_error` with Persian field messages in `details` |
| `POST /api/v1/auth/logout` | cookie if present | clears session → 204 |
| `GET /api/v1/auth/me` | yes | `{username}` |
| `GET /api/v1/products?q=&page=&page_size=` | yes | paginated products (server-side, max 100/page). Filters: `q`, `category_id`, `min_price`/`max_price`, `in_stock`, `min_stock`/`max_stock` |
| `POST /api/v1/products` | yes | create product (toman integer) → 201 |
| `GET /api/v1/settings` | yes | `{low_stock_threshold, default_page_size}` — below-or-equal means «کم» |
| `PUT /api/v1/settings` | yes | partial `{low_stock_threshold?: int ≥ 0, default_page_size?: 10\|20\|50}` → updated settings |

Errors: `{ error: { code, message, details? } }` with codes `unauthorized`, `validation_error`, `rate_limited`. All user-facing `message` and `details` strings are Persian — the frontend never surfaces raw fetch/network/English errors and maps missing-body cases to per-status Persian fallbacks (`ApiRequestError` carries `status`, `code`, `details`).

Frontend client: `apps/web/lib/api.ts` (fetch, `credentials: include`, Persian error surfacing).
