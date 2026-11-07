# API — چهارسوق

FastAPI service, base path `/api/v1`. Routes, schemas, the live OpenAPI document (`/openapi.json`),
Swagger UI (`/docs`), and the committed snapshot (`backend/api/openapi.json`) all come from one app.
For the Swagger workflow and snapshot rules see [API contract](../api/README.md).

## Conventions

| Topic      | Rule                                                                                                                                                      |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Auth       | `POST /auth/login` sets an HttpOnly session cookie. Every operation except health and the auth entry points requires it. A new login rotates the session. |
| Errors     | `{"error": {"code", "message", "details?"}}`. Persian `message`/`details`; stable `code`. See [errors](#error-envelope).                                  |
| Pagination | `page` is 1-based. `page_size=0` returns every match without an offset; an explicit size is clamped to 500.                                               |
| Caching    | `GET /categories` and `GET /products/groups` set a weak `ETag` and `Cache-Control: private, max-age=60`.                                                  |
| Values     | Toman amounts (no symbols), UTC timestamps, ISO dates. Display formatting (Persian digits, `٬`, Jalali `٫`) happens only in the UI.                       |
| Background | Sync triggers return `202` immediately; counters and errors are exposed by the matching `GET …/status` endpoint.                                          |

## Health

| Method | Path      | Purpose                                                      |
| ------ | --------- | ------------------------------------------------------------ |
| `GET`  | `/health` | Liveness. Does not touch the database.                       |
| `GET`  | `/ready`  | Readiness. Runs `SELECT 1`; fails when the database is down. |

## Auth

| Method | Path           | Purpose                                                                |
| ------ | -------------- | ---------------------------------------------------------------------- |
| `POST` | `/auth/login`  | `{username, password}` → `{ok}` plus the session cookie. Rate-limited. |
| `POST` | `/auth/logout` | Deletes the server-side session and clears the cookie → `204`.         |
| `GET`  | `/auth/me`     | `{username}` for the current session.                                  |

Wrong credentials return `401 unauthorized`; missing or out-of-range fields return
`422 validation_error` with Persian messages in `details`. Login is limited to 10 attempts per
minute per IP and username (`429 rate_limited`).

## Dashboard

| Method | Path                           | Purpose                                                                  |
| ------ | ------------------------------ | ------------------------------------------------------------------------ |
| `GET`  | `/dashboard/overview`          | Totals, stock buckets, stock value, competitor coverage, top groups.     |
| `GET`  | `/dashboard/competitor-gaps`   | Products ranked by absolute price gap vs. the cheapest fresh competitor. |
| `GET`  | `/dashboard/catalog-breakdown` | Per-section totals: items, groups, brands, stock value.                  |
| `GET`  | `/dashboard/summary`           | One-call payload combining overview + gaps + breakdown.                  |

`threshold` (default 10) is the low-stock cutoff. Positive `diff_percent` means our price is higher
than the competitor. The UI uses `/dashboard/summary`; the individual endpoints stay for
compatibility and smaller consumers.

## Products

| Method | Path                | Purpose                                                      |
| ------ | ------------------- | ------------------------------------------------------------ |
| `GET`  | `/products`         | Search, filter, sort, and paginate the local catalog mirror. |
| `POST` | `/products`         | Create a manual row (integer Toman) → `201`.                 |
| `GET`  | `/products/summary` | Server-side inventory totals: total/in/low/out/stock value.  |
| `GET`  | `/products/groups`  | Distinct raw `main_group_name` values for the filters.       |

`GET /products` accepts `q`, `category_id`, `top_group`, `main_group`, `min_price`,
`max_price`, `competitor_store`, `min_competitor_price`, `max_competitor_price`, `min_stock`,
`max_stock`, `in_stock`, `sort` (`newest`, `cheapest`, `most_expensive`), `page`, and `page_size`.
Competitor filters only consider prices inside the configured TTL. An unknown `category_id` on
create returns `422`.

## Categories

| Method   | Path               | Purpose                                                                    |
| -------- | ------------------ | -------------------------------------------------------------------------- |
| `GET`    | `/categories`      | All categories ordered by name.                                            |
| `POST`   | `/categories`      | Create; duplicate names → `409 conflict`.                                  |
| `DELETE` | `/categories/{id}` | Delete an empty category; unknown → `404`; in use → `409 category_in_use`. |

## Competitor prices

| Method   | Path                                       | Purpose                                                                 |
| -------- | ------------------------------------------ | ----------------------------------------------------------------------- |
| `GET`    | `/products/{product_id}/competitors`       | Links for one product, with fetched and manual values.                  |
| `POST`   | `/products/{product_id}/competitors`       | Add a link → `201`. Unknown product → `404`; bad URL → `422`.           |
| `PATCH`  | `/competitors/{listing_id}`                | Update URL, active flag, or a manual price/currency/stock override.     |
| `DELETE` | `/competitors/{listing_id}`                | Remove a link → `204`.                                                  |
| `POST`   | `/products/{product_id}/competitors/check` | Re-check every active link of one product (synchronous).                |
| `POST`   | `/competitors/{listing_id}/check`          | Re-check one link (synchronous); too soon after the last check → `429`. |

`effective_price`, `effective_currency`, and `effective_in_stock` prefer a manual override and
otherwise use a fetched value that is still within the TTL. `status` reports the last fetch
result (`success`, `not_found`, `unavailable`, `blocked`, `failed`, `pending`, `manual`).
Automatic extraction only supports Digikala and Technolife public product pages; `other` links are
manual-only. Links are limited to لوازم خانگی products, at most one per store. Unknown or stale
prices are excluded from tables and competitor-price filters.

## Integrations

| Method | Path                               | Purpose                                                                |
| ------ | ---------------------------------- | ---------------------------------------------------------------------- |
| `GET`  | `/integrations/parsina/status`     | Product-sync state, last-run counters, configured interval.            |
| `POST` | `/integrations/parsina/sync`       | Start a product sync → `202`. `409` if running; `503` if unconfigured. |
| `GET`  | `/integrations/competitors/status` | Bulk-refresh state and last-run counters.                              |
| `POST` | `/integrations/competitors/sync`   | Start a bulk competitor refresh → `202`; `409` if running.             |

Both sync jobs take their own database lock across manual and scheduled runs, so two runs of the
same job never overlap. Manual runs return immediately; poll the status endpoint until `running`
is false, then refresh the table. Production syncs Parsina (or the dev mirror when
`DEV_DATABASE_URL` is set); development re-imports `data/parsina.csv`. A complete listing is
authoritative: rows missing from it are deactivated, never hard-deleted. A failed or partial fetch
leaves the last successful data untouched.

## Settings

| Method | Path        | Purpose                                      |
| ------ | ----------- | -------------------------------------------- |
| `GET`  | `/settings` | Current admin preferences.                   |
| `PUT`  | `/settings` | Partial update; only supplied fields change. |

`GET` returns `low_stock_threshold`, `default_page_size`, `sync_interval_minutes`,
`competitor_sync_interval_minutes`, `default_competitor_store`, `suggested_price_formulas`, and
`product_table_columns`.

- Each formula is `{top_group, weight}` and drives
  `weight × competitor + (1 − weight) × Parsina`; `weight` is the competitor share (0–1).
- `suggested_price_formulas` replaces the saved list; each `top_group` may appear once.
- `product_table_columns` replaces the visible column list (`row`, `name`, `sku`, `category`,
  `brand`, `unit`, `price`, `competitor_price`, `price_diff`, `suggested_price`, `stock`); at least
  one column, no duplicates.

## Error envelope

```json
{
  "error": {
    "code": "validation_error",
    "message": "خطای اعتبارسنجی",
    "details": { "price": ["قیمت کمتر از حد مجاز است"] }
  }
}
```

| Status | Code               | When                                                     |
| ------ | ------------------ | -------------------------------------------------------- |
| `400`  | `bad_request`      | Malformed request.                                       |
| `401`  | `unauthorized`     | Missing, expired, or invalid session; wrong credentials. |
| `403`  | `forbidden`        | Access denied.                                           |
| `404`  | `not_found`        | Resource does not exist.                                 |
| `409`  | `conflict`         | Duplicate value or a run already holds the lock.         |
| `409`  | `category_in_use`  | Category still has products.                             |
| `422`  | `validation_error` | Schema, query, or business validation failed.            |
| `429`  | `rate_limited`     | Login attempts or a competitor link checked too soon.    |

The frontend never surfaces raw fetch/network/English errors: `ApiRequestError` carries `status`,
`code`, and `details`, and maps missing bodies to per-status Persian fallbacks.
