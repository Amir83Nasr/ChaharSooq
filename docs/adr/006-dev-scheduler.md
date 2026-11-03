# ADR 006 — Scheduler runs in development from the CSV fixture

## Status

Accepted.

## Context

The scheduler only ticked in production, so dev never exercised the
interval gating, the DB lock from a background thread, or the automatic
status updates — dev behaved differently from prod in exactly the area
being simulated.

## Decision

- `SyncScheduler.start()` also starts with `APP_ENV=development` when the
  CSV fixture is configured (still never in `test`).
- `run_scheduled_sync()` ticks from the CSV in development through the same
  `_due` interval check and `ProductSyncService` path as production.
- Consequence: clearing the dev catalog (`make db-clear-products`) is
  temporary — the next due tick re-imports the CSV. That is the point:
  dev now behaves like prod.

## Consequences

- Dev mirrors prod timing, locking, and status reporting without Parsina
  credentials or network access.
- The CSV file (`data/parsina.csv`, gitignored) is the dev catalog source
  of truth; deleting it disables both the button and the scheduler in dev
  with a Persian "not configured" message.
