# ADR 017 — Blue-Green deployment for Production

Date: 2026-11-16 · Status: superseded by [ADR 018](018-simple-production-deploy.md)

> Kept as a record of the rejected Blue-Green design; it was never executed on
> `market-linux`. Do not implement from this document.

## Context

[ADR 016](016-ci-cd-deploy-job.md) introduced an event-driven deploy job and a
health-gated replace script. It explicitly left a full blue-green pair for
later because it required a Compose, Caddy, and network redesign.

The Production stack must now deploy with blue-green behavior under these
constraints:

- The host is inside the company network with outbound-only connectivity to
  GitHub/GHCR; no inbound port, webhook, port forwarding, or public IP.
- Deployments are triggered by the existing `release.published` workflow on a
  self-hosted runner.
- The database is shared and must not be duplicated.
- The previous active version must remain available for rollback.
- No Production data, volume, or image may be removed; no production host may
  be modified by this change.

## Decision

- **Shared base, swappable slots.** `compose.production.yml` keeps `db`,
  `provision`, `migrate`, `caddy`, `pgdata`, and certificate volumes in the
  `charsooq-production` project. The deployable pair runs as two slots:
  `api-blue`/`web-blue` (profile `blue`) and `api-green`/`web-green` (profile
  `green`).
- **Per-slot edge networks.** Each slot has its own conflict-checked edge
  network and fixed web address: `CHARSOOQ_EDGE_BLUE_SUBNET` /
  `CHARSOOQ_WEB_BLUE_EDGE_IP` and `CHARSOOQ_EDGE_GREEN_SUBNET` /
  `CHARSOOQ_WEB_GREEN_EDGE_IP`. Each slot API trusts only its own web address.
  The web image's baked `API_URL_INTERNAL=http://api:8000` is satisfied by the
  `api` network alias on the slot edge network.
- **Single active upstream.** Caddy imports `deploy/caddy/active-upstream.caddy` (removed by
  ADR 018). The deploy script rewrites that file atomically and reloads Caddy with
  `SIGUSR1` (admin API is off; `caddy reload` is unavailable). The file is part
  of the mounted `deploy/caddy` directory so the switch is visible without a
  container restart.
- **Deploy flow.** For each digest-identified release: detect the active slot,
  choose the inactive slot, start the shared base, run `provision` and
  `migrate` once, pull/start the inactive slot, run revision/health/smoke checks
  against the inactive slot, switch Caddy, run external verification, persist
  state to `/etc/charsooq/state/deploy-state.env`, and keep the previous slot
  running.
- **Failure handling.** A failure before the traffic switch leaves the active
  slot unchanged. A failure after the switch attempts to return traffic to the
  previously active slot. No automatic data rollback is performed.
- **Migrations.** Because the database is shared and old/new slots may overlap,
  every production migration must be additive or expand-compatible with the code
  already serving traffic. Contracting changes require the expand/contract
  process or a maintenance window ([ADR 014](014-production-backup-and-recovery.md)).
- **Sessions and cookies.** Sessions remain database-backed and the cookie
  contract is unchanged, so a user session remains valid across a traffic
  switch when both slots share the same database and session secret.

## Consequences

- `deploy/scripts/deploy.sh` is the only automated Blue-Green path. It accepts
  only `repository@sha256:<digest>` references and never removes volumes,
  databases, or images.
- Existing host `production.env` files must be extended with the green slot
  edge variables. For compatibility the script maps legacy
  `CHARSOOQ_EDGE_SUBNET` / `CHARSOOQ_WEB_EDGE_IP` to the blue slot when the new
  blue variables are absent.
- The active slot after a host restart is recovered from the persisted state
  file and the `active-upstream.caddy` file. Operators must start the recorded
  active slot profile; `deploy/scripts/deploy.sh` reconciles on the next deploy.
- `make prod-up`/`prod-pull`/`prod-ps`/`prod-logs` take `PROD_SLOT` (default
  `blue`) as helpers for manual operation; they are not a replacement for the
  deploy script.

## Zero-downtime limitations (explicit)

This implementation is **traffic-gated and rollback-safe**, but it is **not a
guarantee of zero dropped requests** in all cases:

- The Caddy upstream switch uses a graceful in-process reload (`SIGUSR1`), which
  is the approved non-restarting path with `admin off`; a brief connection error
  is still possible during reload depending on in-flight requests and client
  behavior.
- Web images bake `API_URL_INTERNAL=http://api:8000` at build time, so per-slot
  API isolation relies on edge-network aliases rather than independently
  configurable upstreams. Changing that contract requires a web image/build
  change.
- Database migrations run against the shared database before the new slot serves
  traffic. A non-additive migration can make the still-active slot fail or make
  rollback unsafe.
- `SESSION_COOKIE_SECURE` is currently `false` for the temporary HTTP-only
  internal deployment; switching it to `true` is a separate, coordinated change
  and not performed here.
- The design is implemented and contract-tested in the repository but has not
  been executed on `market-linux`.
