# ADR 023 — In-app backup execution and transactional data restore

Date: 2026-11-21 · Status: accepted · Supersedes the execution-ban in
[ADR 022](022-owner-configured-backup-orchestration.md) and the encryption/off-host requirement in
[ADR 014](014-production-backup-and-recovery.md) for this iteration

## Context

ADR 022 gave the owner backup metadata, settings, and restore _requests_, while execution stayed
host-driven: no `pg_dump` in the API image, no in-process scheduler, no in-app restore. The panel
could therefore say "backups are enabled" without producing a single archive. That is the worst
failure mode for a shop admin panel: the owner believes a recoverable copy exists when it does not.

The organization still has not approved an encryption tool, key custody, an off-host destination, a
fixed RPO/RTO, or alerting. This ADR implements the execution that can be done safely now — a
same-host logical dump and a transactional, data-only restore — and records exactly what remains
blocked so the gap is explicit rather than implied.

## Decision

### Execution model

- **The API worker runs the dump, not the database container.** `pg_dump`, `pg_restore`, and `psql`
  come from the pinned PostgreSQL 18 client installed in `Dockerfile.api` (the server is 18.x and
  `pg_dump` refuses a newer server). The API uses **only** the application-role `DATABASE_URL`; it
  never receives the administrative or migration credential. Logical dump with `--no-owner
--no-privileges` needs no elevated role.
- **Work is queued and leased.** `backup_records.status` gains `queued`; a manual action and the
  schedule both insert a queued row and return `202`. A single-row `backup_state` lease (reclaimable
  when expired) guarantees that two uvicorn workers cannot dump or restore concurrently. The worker
  thread ticks every 5 seconds in the API process; tests never start it. On hosts without the API
  thread, `scripts/backup_cli.py run-once` and `prune` execute exactly one tick.
- **Schedule settings stay owner-only.** `backup_enabled` and `backup_interval_minutes` live in the
  existing `settings` table. Defaults change to **enabled, 720 minutes**; range 60–10080 minutes.
  Automatic runs are skipped (not recorded as failures) when the client tools or the archive
  directory are unavailable, which is the Staging case.
- **Archives are local files with safe names.** A named Docker volume at `/var/backups/charsooq`
  (Development: the gitignored `<repo>/data/backups`, overridable with `BACKUP_DIR`) holds custom
  format archives. The directory is `0700`, files `0600`, and the database stores only a validated
  basename — never a path. Writes go to a temporary name and are renamed after success; the SHA-256
  of the final file is recorded.
- **Verification is structural.** `pg_restore --list` must succeed and the archive must contain a
  `TABLE DATA` entry for `products` before a record becomes `verified` or is accepted for restore.
  This catches truncated and non-`pg_dump` files without a scratch database.

### Archive contents

The dump excludes **table data** for `admin_sessions`, `backup_records`,
`backup_restore_requests`, `backup_state`, and `alembic_version`. Sessions and backup history are
environment state, and the application role deliberately has no grant on `alembic_version`, so
dumping its rows would fail. `admins` data is included for disaster recovery; schemas of excluded
tables are still present.

### Restore semantics

- **Data-only, in place, atomic.** A restore from a chosen verified archive runs as one `psql`
  script with `ON_ERROR_STOP=1`, `BEGIN` … `COMMIT`: delete the shop tables in dependency order
  (`competitor_price_observations`, `competitor_listings`, `products`, `categories`,
  `suggested_price_formulas`, `parsina_sync_state`, `competitor_sync_state`, `settings`), append the
  archive's `COPY` blocks in parent-first order, resync owned sequences to `max(id) + 1`, re-apply
  the preserved backup settings, and commit. Any error rolls the whole transaction back; the live
  shop is never half-restored.
- **Authentication and backup state are preserved.** Accounts, sessions, backup history, and the
  migration revision are not deleted or loaded. The owner stays logged in and the archive that was
  restored remains in the list.
- **A verified pre-restore archive is mandatory.** The worker writes and verifies a
  `pre_restore` dump before touching data; if that dump fails, the request fails without a restore.
- **Schema compatibility is the operator's contract.** `COPY` lists the archive's columns, so an
  archive from a different revision can fail (and then rolls back) when the schema has drifted.
  Restores are supported between environments running the same `alembic_version`; migrate first or
  choose a matching archive. This ADR does not build a cross-revision data migration.
- **Owner-only, cancellable while queued.** `POST /backups/restore-requests` returns `202`; only a
  request that has not started can be cancelled. `failed` is a first-class status with a stable
  `error_code` (`pre_restore_failed`, `archive_missing`, `restore_failed`, `restore_timeout`,
  `interrupted`).

### Owner-facing surface

`GET/PUT /api/v1/settings/backup` (with `tools_available` and `storage_ready`), `GET/POST
/api/v1/backups`, `POST /api/v1/backups/upload` (custom format, 512 MiB cap, verified before it is
recorded), `GET /api/v1/backups/{id}/download`, `DELETE /api/v1/backups/{id}`, and the
restore-request list/create/cancel routes.
Every route uses `require_owner`; the UI additionally hides the page from other roles, but the API
is the boundary. The page polls only while a dump or restore is queued/running.

### Retention

Fixed 30 days. Pruning deletes expired files, keeps metadata with `pruned_at`, and skips an archive
that has a non-final restore request, so a queued restore can never lose its source. Pruning never
removes the pre-restore or most recent archive early; there is no off-host copy to fall back on.

Explicit owner deletion (`DELETE /api/v1/backups/{id}`) is separate from pruning: it removes both
the file and its metadata row. Queued/running archives and any archive referenced by a restore
request are refused, keeping in-flight work and restore history intact.

## Superseded / still blocked

Superseded parts of ADR 022: "the panel owns metadata and requests, not execution"; "no API-side
`pg_dump`"; "no in-process backup scheduler"; "a restore request is not a restore". ADR 022's
metadata, owner gating, and append-only role remain valid.

Still blocked and explicitly **not** implemented:

1. Encryption at rest and key custody — archives are plain custom-format dumps.
2. Off-host destination and transfer — a host loss loses every archive.
3. Fixed RPO/RTO, alerting, and a rehearsed restore drill on a scratch target.
4. A verified-backup gate for destructive migrations in the deploy path.
5. Cross-revision restore (older archive onto a newer schema).

## Consequences

Positive:

- Manual and scheduled backups actually produce verified, downloadable archives, and the owner can
  restore a chosen version from the panel with atomic rollback.
- No new service, secret, or elevated database credential: the same application role, one volume,
  and the existing owner-only settings page.
- Compose keeps its exact service/secret set; only the API mounts the new volume.

Negative / residual risks:

- **Unencrypted at rest.** Anyone with host root, the Docker volume, or the API user's filesystem
  access can read full shop data, including admin password hashes and Parsina connection settings.
  This is accepted only because the archive never leaves the host; it must be revisited before any
  off-host copy exists.
- **No off-host copy and no PITR.** A disk or host loss loses all backups; the recovery point is the
  last completed dump.
- Dumps run in the API container, so a compromised API process can read everything the application
  role can read. The role remains DML-only and cannot alter schema or roles.
- Staging keeps its Vercel/FastAPI Cloud/Neon stack; the client tools and volume do not exist there,
  so backup settings report `tools_available=false` and both manual and scheduled execution refuse.
- An upload is owner-supplied content: it is structurally verified, but restoring it is still a
  trusted-operator action.
