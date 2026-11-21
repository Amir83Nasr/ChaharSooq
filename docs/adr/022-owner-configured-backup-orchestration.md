# ADR 022 — Owner-configured backup metadata and restore requests

Date: 2026-11-20 · Status: accepted; execution items superseded by
[ADR 023](023-in-app-backup-and-data-restore.md)

## Context

[ADR 014](014-production-backup-and-recovery.md) defined a safe logical backup model for
Production but left scheduling, tooling, encryption key custody, off-host destination, retention,
and alerting unapproved. Its dump must run inside the `db` container as the administrative role;
the API image has neither `pg_dump` nor the admin secret, and ADR 014 rejects a backup sidecar or
any new stateful service.

The owner needs a place to see backups and to ask for a particular version to be restored. An
in-app scheduler or one-click restore would contradict ADR 014: the API cannot run `pg_dump`, a
restore must be followed by one-shot `provision` to converge ownership and grants, and verification
requires a scratch container or volume.

## Decision

- **The panel owns metadata and requests, not execution.** Two owner-only setting keys
  (`backup_enabled`, `backup_interval_minutes`) live in the existing `settings` key/value table via
  `SettingsService`. Defaults: disabled, 720 minutes; accepted interval: 60–10080 minutes. They are
  deliberately absent from `GET /settings` (which any signed-in user can read) and are served by
  `GET/PUT /api/v1/settings/backup` with `require_owner`.
- **Two metadata tables** (`backup_records`, `backup_restore_requests`) record archive metadata
  and restore requests. They contain no credentials, no archive bytes, and no raw stderr — only a
  basename, checksum, size, timestamps, source migration revision, statuses, and stable error
  codes. `GET /api/v1/backups` and `GET/POST /api/v1/backups/restore-requests` are owner-only.
- **A restore request is not a restore.** The owner may only request a verified archive. An
  operator performs the scratch-container/volume drill, the admin load, the one-shot `provision`
  and `migrate` steps, and the health checks, then advances the request via the host CLI. The UI
  says this explicitly in the confirmation dialog.
- **Execution remains host-driven.** A one-shot CLI (`scripts/backup_cli.py`) reads the owner
  settings with the application role and records state transitions; a host script and host
  scheduler will consume it under ADR 014's two-step restore model. No Compose service, no new
  secret, no service token, no API-side `pg_dump`, and no in-process backup scheduler are added.
- **Retention (30 days) and verification (`decrypt_list`) are fixed policy**, not owner-editable.
  Pruning is refused until off-host handoff is approved, so pruning can never delete the only copy.
- **The Settings → Backup page is owner-gated server-side** (`getSessionAdmin()` + `isOwner()`),
  hidden from other roles in the settings navigation, and enforced by `require_owner` on every
  route. UI gating is never the security boundary.
- **The ADR is append-only.** ADR 014 stays authoritative for dump/restore mechanics; this ADR
  covers the owner-facing metadata workflow only.

## Blocked items (need explicit approval before Phase 2)

1. Encryption tool and recipient/key custody, with the key held separately from archives.
2. Encrypted host staging directory, ownership, and permissions (root-only `0700` proposed).
3. Host scheduler mechanism and cadence (systemd timer proposed); ADR 014 leaves scheduling open.
4. Off-host destination and transfer mechanism — IT-owned; no destination is assumed.
5. Fixed RPO/RTO statement, failure alerting, and a rehearsed restore drill procedure.
6. The backup gate for destructive migrations in `deploy/scripts/deploy.sh` (a separate decision
   because it can block deploys).

Without these approvals the host script, timer, drill script, and production runbook are not
implemented; the panel can configure backups and request restores, but no archive is produced and
no request is executed.

## Consequences

Positive:

- The owner can enable/pause backups, adjust their interval, inspect archive metadata, and request
  a verified version without new credentials in the API.
- ADR 014's credential boundary, two-step restore, drill-only verification, and no-sidecar rule
  remain intact.
- Backup metadata is versioned through a normal Alembic migration; Production applies it before
  `provision` grants the application role DML on the new tables.

Negative / residual risks:

- Until Phase 2 is approved, enabling backups has no operational effect; the UI says so.
- RPO is undefined until a scheduler is approved; there is no PITR.
- Dumps contain password/session hashes and remain sensitive; archives stay on encrypted staging
  until an approved off-host destination exists.
- An owner restore request is a request only: the operator remains part of the critical path.
