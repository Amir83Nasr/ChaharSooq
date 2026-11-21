# ADR 026 — Direct owner restore from the archive table

Date: 2026-11-21 · Status: accepted · Supersedes the restore-request flow in
[ADR 023](023-in-app-backup-and-data-restore.md)

## Context

ADR 023 made backup execution real and transactional, but put a restore-request
workflow in front of it: the owner created a request, watched a separate request
list, and could cancel it while queued. That duplicates the archive's state on a
second table, adds a cancellation path with no safety value, and forces the UI
to coordinate two resources for one action. The owner already chooses a specific
archive from the backup table; that row is the natural place to trigger and track
its restore.

## Decision

- **The owner triggers restore directly.** `POST /api/v1/backups/{backup_id}/restore`
  is the only restore endpoint. It requires `require_owner`, returns `202` with
  the `BackupOut` of the chosen archive, and validates that the archive is
  completed, unpruned, verified, locally present, not already being restored, and
  not blocked by a queued/running dump. A 404 covers a missing/ineligible archive;
  409 covers every state conflict.
- **The final confirmation is client-side only.** The owner picks an archive and
  confirms a destructive-action dialog in the panel before the request is sent.
  The API has no confirmation token, approval step, or second call. The dialog is
  a UI guard, not a server-side state machine.
- **Restore state lives on the archive.** `backup_records` gains nullable
  `restore_status` (`queued`, `running`, `completed`, `failed`, with a SQL CHECK),
  `restore_started_at`, `restore_finished_at`, `restore_error_code`, and
  `restored_at`. `BackupOut` exposes all five, so the existing `GET /backups`
  poll shows progress and the final result without a second endpoint.
- **No request/cancel/approval API or table.** `backup_restore_requests` and its
  model, schemas, repository helpers, CLI subcommand, and the request
  list/create/cancel routes are removed. Migration 0020 creates the final schema
  directly; migration 0021 only adds the worker lease and pruning metadata.
- **Execution safety is unchanged.** The worker takes one conditional
  queued→running transition under the existing single DB lease, writes and
  verifies a mandatory pre-restore dump, loads the chosen verified local archive
  in one `pg_restore` transaction with rollback on failure, and records completion
  or a stable error code on the same record. Stale running restores are marked
  `failed`/`interrupted`; pruning and explicit owner deletion refuse archives
  with an active restore but allow them once it completes or fails. Backup
  dumps still exclude backup metadata table data.

## Consequences

The owner has one place to act and one place to observe: the archive table and
its `restore_*` fields. Cancellation is gone; once the owner confirms and the API
accepts the request, the worker runs it. The old request history cannot be shown
for archives restored under earlier revisions, and any deployment that still
expects the request routes or table must move to the direct endpoint first.

ADR 023's transactional restore semantics, owner gating, local archive storage,
and retention rules remain in force. Only its restore-request workflow, request
list/cancellation routes, and request-table bookkeeping are superseded; the
existing ADR is left unchanged as an append-only record.
