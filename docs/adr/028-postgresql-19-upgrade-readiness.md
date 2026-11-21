# ADR 028 — PostgreSQL 19 upgrade readiness

Date: 2026-11-21 · Status: accepted

## Context

PostgreSQL 19.0 was released on 2026-11-19 and is the latest stable major. Charsooq runs
PostgreSQL 18: Production pins `postgres:18.6-trixie`, Development and CI use the floating
`postgres:18` tag, and the API image installs `postgresql-client-18`. Production holds real data
in the named `pgdata` volume.

A major upgrade is not an image-tag change. Each PostgreSQL major initialises its own cluster
below `/var/lib/postgresql` (`/var/lib/postgresql/18/docker` today); starting a 19 image on the
current volume would create an empty 19 cluster beside the 18 one, and the application would
silently see an empty database. `pg_dump` also refuses a newer server major, and the in-app
backup archive excludes state tables (`alembic_version`, sessions, backup records), so it cannot
serve as a full-upgrade dump.

This decision supersedes the version statements in [ADR 003](003-database.md) (17),
[ADR 008](008-perf-security-hardening.md) (pinned minor only),
[ADR 014](014-production-backup-and-recovery.md) and [ADR 023](023-in-app-backup-and-data-restore.md)
(18). Those ADRs are append-only and are not edited; this ADR is authoritative for the version
policy and the upgrade procedure.

## Decision

- **Production pins the exact image `postgres:19.0-trixie`.** Development and CI follow the same
  major (`postgres:19`); they may track a newer minor, but a production minor bump is one
  coordinated PR. The Production Compose file is the single source of truth, guarded by
  `backend/api/tests/test_postgres_version_consistency.py` (run by `make check` and CI).
- **CI's PostgreSQL 19 leg is blocking.** The `backend` job runs only on 19. The `migrations`
  job keeps one non-blocking PostgreSQL 18 leg (`continue-on-error`) while a rollback to the old
  major remains possible. Remove that leg once the upgrade is verified and the rollback window
  closes, or when 19.1 ships, whichever comes first.
- **Staging (Neon) is an explicit exception.** Its server major is not controlled by this repo;
  verify it before relying on Staging as an upgrade rehearsal.
- **The upgrade is a data migration with a verified dump and a scratch rehearsal.** Logical
  `pg_dump`/`pg_restore` is the default method (small single-host database, existing tooling,
  clean rollback). `pg_upgrade --copy` is an alternative with both major binaries present and
  matching locale/extensions. Never start the 19 image against the 18 cluster.
- **The deploy script fails closed on a major mismatch.** `deploy/scripts/deploy.sh` compares the
  image major from the Compose file with the on-disk `PG_VERSION` before resolving a release, so
  no pull, provision, migration or service start happens against the wrong cluster.

## Upgrade runbook (Production, real data)

### 1. Preflight

1. Record the current `SELECT version()`, `SHOW data_directory`, `alembic_version`, installed
   extensions, row counts and image digests.
2. Build the API image with `postgresql-client-19` and verify `pg_dump --version`; confirm in a
   scratch container that the 19 client can dump the 18 server. Ship this image before the server
   cutover so the backup window stays as small as possible (a 18 client cannot dump a 19 server).
3. Take a **full administrative-role** dump: `pg_dump -Fc --no-owner --no-privileges` for the
   database plus `pg_dumpall --globals-only --no-role-passwords`. Verify with
   `pg_restore --list` and SHA-256, and copy it off-host. The same-host, unencrypted in-app archive
   is not sufficient on its own ([ADR 023](023-in-app-backup-and-data-restore.md)).
4. Pause scheduled backups for the maintenance window.

### 2. Rehearsal

Run `deploy/scripts/pg_upgrade_drill.sh` against **scratch containers and volumes only**: restore
the dump into 18, rehearse the chosen upgrade to 19, run `provision`, `migrate.py`, the opt-in
`test_role_grants_postgres.py`, `alembic current`, row-count and `version()` checks. Remove only
the drill resources. If considering `pg_upgrade`, run `pg_upgrade --check` here first.

### 3. Cutover

1. Stop writes: `docker compose -f compose.production.yml stop web api`; take the final dump.
2. Migrate the data into the 19 cluster using the rehearsed method; keep the 18 datadir intact.
3. Switch the Compose pin to `postgres:19.0-trixie`, then `make prod-config`.
4. Run `provision` → `migrate.py --check` → `migrate` → `compose up -d --no-build --remove-orphans`
   → Caddy `SIGUSR1`, following the existing health-gated deploy order.
5. Verify `version()`, `SHOW data_directory`, `alembic current`, `/api/v1/health`,
   `/api/v1/ready`, `/login`, and a fresh in-app backup. Then resume scheduled backups.

### 4. Rollback

A code-only rollback is the previous release tag. A data rollback is not a binary downgrade:
stop the 19 stack, restore the pre-upgrade dump into a fresh 18 cluster with the 18-client API
image, re-run `provision`/`migrate` and the health probes. Never delete or overwrite existing
volumes; keep the abandoned 19 cluster as evidence.

## Alternatives

- **Floating `postgres:19` in Production.** Rejected: minors would drift silently between
  environments and break the parity this decision establishes.
- **Switching the image and reusing the old volume without a data migration.** Rejected: creates
  an empty cluster and loses the visible database with no error at startup.
- **`pg_upgrade --link`.** Rejected: the old cluster cannot be preserved for rollback.
- **Waiting for 19.1.** Considered; 19.0 is two days old, but pinning an exact minor plus the
  rehearsal keeps the risk explicit, and 19.1 is the documented trigger to drop the 18 CI leg.

## Consequences

- `Dockerfile.api` must build with `postgresql-client-19` from PGDG; that build is the hard gate
  before merging the pin changes.
- Development keeps the default volume name `chaharsooq_pgdata`, now holding the restored
  PostgreSQL 19 cluster. The old 18 contents were removed only after the restore was verified
  (same revision and row counts); Production keeps its 18 datadir until its own cutover is verified.
- The deploy CLI output gains one step (`[n/10]`); its offline tests cover matching, mismatched
  and missing clusters.
- Existing backups remain restorable into an 18 cluster only. Fresh 19 backups are needed after
  cutover, and off-host transfer/encryption remain open from ADR 014.
