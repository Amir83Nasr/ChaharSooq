# Performance baseline — چهارسوق

How to reproduce: start the stack (`compose.yml` or local dev), seed the
catalog, then run the stdlib-only benchmark:

```bash
ADMIN_PASSWORD=<admin> python backend/api/scripts/bench-api.py
# BENCH_BASE_URL=http://localhost:8000 BENCH_RUNS=5 (defaults)
```

## Measured (2026-11-06, local run — API + postgres:18 on one machine)

Seeded dev catalog: **1349 products** from `data/parsina.csv`.
`BENCH_BASE_URL=http://127.0.0.1:8000 BENCH_RUNS=5` via
`backend/api/scripts/bench-api.py`:

| Scenario                        | Mean (5 runs) |
| ------------------------------- | ------------- |
| `GET /products` (filter + page) | **17.5 ms**   |
| `GET /dashboard/overview`       | **11.1 ms**   |
| `GET /dashboard/summary`        | **14.5 ms**   |

Note: `summary` costs slightly more than `overview` alone on a small catalog
because it also folds gaps + catalog-breakdown into the same response — the
page as a whole still needs fewer round-trips (3 fetches after settings
instead of 4+).

## Structural wins (before → after)

| Scenario                              | Before                                                     | After                                                             | Why                          |
| ------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------- |
| `GET /products` (filter + page)       | 2 round-trips (`list` + `prices_for_products`)             | same count, but `list` is index-covered (composite `is_active/*`) | `0012_search_indexes`        |
| `GET /dashboard/overview`             | 4 sequential COUNT queries                                 | 3 (`summary` + `groups` + combined `coverage/appliance`)          | scalar-subquery merge        |
| Dashboard page load                   | settings → overview → (breakdown + 2 statuses) ≈ 4 fetches | settings → (summary + 2 statuses) ≈ 3 fetches                     | `GET /dashboard/summary`     |
| `page_size=0` ("show all")            | unbounded serialization                                    | capped at 2000 rows, windowed render + notice                     | `SHOW_ALL_MAX` both sides    |
| `GET /products/groups`, `/categories` | no cache headers                                           | `Cache-Control: private, max-age=60` + `ETag`                     | cheap refetch on nav         |
| Sync `deactivate_missing`             | N ORM loads + N updates                                    | 1 bulk `UPDATE`                                                   | `deactivate_missing` rewrite |

## What to watch

- `%q%` Persian search on large catalogs: check `EXPLAIN ANALYZE` uses the
  `pg_trgm` GIN indexes (`ix_products_*_trgm`) on PostgreSQL. SQLite has no
  trigram — dev-only fallback is the B-tree prefix path.
- `dashboard/summary` short-circuits gaps/catalog work when `total == 0`.
- Login is single-session: a fresh login invalidates older cookies (intended).
- Rate limiting is shared across workers only when `REDIS_URL` is set;
  without it each worker keeps its own memory bucket.
