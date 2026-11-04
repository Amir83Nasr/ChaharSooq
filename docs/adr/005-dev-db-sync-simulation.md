# ADR 005 — Production sync simulation from the dev database

## Status

Accepted.

## Context

The "به‌روزرسانی از پارسینا" button and the 15-minute scheduler sync products
from the live Parsina API in production. Until Parsina credentials are
available in the deployed environment, the button must still work end to end
— same locking, background run, status polling, counters, and validation —
but read its catalog from the dev database instead of the vendor API.

## Decision

- New `DEV_DATABASE_URL` setting (`Settings.dev_database_url`, empty by default).
- New `DevDatabaseCommoditySource` (`app/integrations/dev_db.py`, label `"dev"`):
  reads active rows from the dev `products` mirror and returns them in the
  Parsina `/Commodity` field shape, plus unit titles from stored unit names.
- `build_commodity_source`: development → CSV fixture (unchanged);
  production with `DEV_DATABASE_URL` set → dev database; production without
  it → live Parsina (unchanged fallback).
- `ProductSyncService`, the manual button, the scheduler tick, and
  `SyncStatusOut.source` (`"parsina" | "csv" | "dev"`) all treat the dev
  source like Parsina: complete listing, deactivates missing rows, Persian
  `"dev"` messages, same interval and DB lock.
- Dev catalog maintenance: `make db-clear-products` (new
  `scripts/clear_products.py`) empties dev products + competitor listings and
  resets sync counters; refuses to run in production.

## Consequences

- Deploying with `DEV_DATABASE_URL` pointed at a reachable dev database gives
  a fully working sync button without Parsina credentials or network access.
- Clearing the variable restores the live Parsina path with no code change.
- The dev database must be reachable from the API process (local prod-like
  runs, or a hosted dev branch for cloud prod); connection failures surface
  as Persian sync errors without leaking the URL.
