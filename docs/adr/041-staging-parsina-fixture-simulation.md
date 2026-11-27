# ADR 041 — Staging Parsina simulation from bundled fixtures

Date: 2026-11-27 · Status: accepted

## Context

Staging must verify the same application behavior as Production, but it has no
Parsina credentials. Without a commodity source, the «به‌روزرسانی از پارسینا»
button, the scheduler, and the product cardex are all unconfigured there, so
catalog changes, unit titles, and invoice history cannot be exercised before a
release. Development already reads saved Parsina responses from the gitignored
`data/` directory; Staging cannot reach that local path.

## Decision

- The saved Parsina responses needed by the simulation are committed under
  `backend/api/app/fixtures/`: the catalog (`products.json`), counting units
  (`units.json`), and the sale/buy invoice headers and details.
- The explicit Staging identity (`DEPLOYMENT_ENV=staging`) selects that
  directory for catalog sync and cardex. Development keeps `data/`; Production
  never reads fixtures. `PARSINA_FIXTURE_DIR` can point at another directory in
  Development or Staging, but it is ignored in Production.
- Catalog sync uses the same `CsvCommoditySource` and `ProductSyncService`
  validation/apply path, so the manual button, the scheduler, and status
  reporting behave exactly as they do against Parsina.
- Cardex reads the saved invoice envelopes and falls back to the deterministic
  demo invoices for products the dumps do not cover, so every product dialog
  shows a history.
- Staging data is populated from Development with
  `make db-sync-dev-to-staging YES=1 FULL=1`: the sync copies products (with
  `pinned` and `pricing_mode`), categories, settings, suggested-price weights,
  real competitor links and their observations, and soft-deactivates synced
  products that no longer exist in Development. Auth, sessions, AI secrets,
  backups, and per-product suggested-price bounds stay environment-local.

## Alternatives

- **Configure live Parsina credentials in Staging:** rejected — it would mix
  real accounting data into a verification environment and does not provide a
  stable catalog for repeated tests.
- **Point Staging at the developer machine's database:** rejected — the cloud
  runtime cannot reach a laptop, and the tunnel would make Staging depend on a
  developer session.
- **Deploy `data/` with the API:** rejected — `data/` is gitignored local data;
  the API needs an explicit, reviewed fixture set.

## Consequences

- A push to `main` deploys the fixtures with the API; no extra Staging
  configuration is required.
- Staging is a simulation environment by definition. Adding real Parsina
  credentials there later requires disabling or replacing this selection.
- The committed fixtures are a snapshot. Refreshing them is an explicit commit,
  which keeps a deployment reproducible.
