# ADR 014 — Production database backup and recovery model

Date: 2026-11-14 · Status: accepted

## Context

Production is a single-host Docker Compose stack on `market-linux` with PostgreSQL 18.6 in the
`charsooq-production_pgdata` volume. [deployment.md](../architecture/deployment.md#backups-and-recovery)
recorded that database backups, encryption, off-host retention, and a rehearsed restore are not
implemented. The TLS volumes have a separate encrypted backup design in
[ADR 013](013-tls-certificate-lifecycle.md); that is not a database backup.

The organization has not yet approved a backup tool, encryption/key custody, off-host destination,
RPO/RTO, retention, or a scheduler. PostgreSQL has no WAL archiving, base backup, or replication role.
The decision must therefore work with the tools already present (`pg_dump` in the pinned image) and
must not claim point-in-time recovery that does not exist.

## Decision

- **Logical `pg_dump` custom-format archives are the baseline.** The dump runs inside the `db`
  container against the `charsooq` database with the administrative role over the container's local
  socket. No password is placed on the command line. Custom format supports verification and
  selective restore; the dump uses `--no-owner --no-privileges` so a restore can be loaded as the
  admin and then converged by `provision`.
- **Restore is a two-step ownership model.** After restoring schema and data as the admin, run the
  one-shot `provision` service so the migration role owns schema objects and the application role gets
  its least-privilege DML grants. This reuses the supported “existing objects owned by admin” path
  instead of hand-editing ownership.
- **Backups are encrypted, checked, and off-host.** Every archive is encrypted with the approved tool
  before it leaves the host; the key/identity is held separately from the archive. A SHA-256 checksum is
  recorded and verified on the destination. A backup is not trusted until it has been decrypted and
  listed or restored.
- **A verified backup gates destructive migrations.** Non-additive migrations, data rewrites, and the
  first migration of an existing database require a fresh verified dump and a recorded revision. A
  code rollback is not a data rollback.
- **Restore drills use a scratch container/volume.** Production data is restored into an isolated
  `postgres:18.6-trixie` container first; the drill volume is removed afterwards. Production volumes
  are never used as a drill target. Volume deletion is never a routine repair.
- **PITR is explicitly out of scope for this iteration.** There is no `archive_mode`, WAL archive,
  base backup, or `restore_command`, and none is assumed. The recovery point is the last verified dump.
  Adding PITR requires approved storage/tooling, a dedicated replication/backup role, an ADR update,
  and a restore drill.
- **No backup sidecar or new stateful service is added to Production.** Backups are an operator/IT
  operation using the pinned images and approved external tooling. Scheduling, alert delivery,
  retention automation, and a dedicated backup role remain follow-ups.
- **The database dump does not include secret files.** The six files under `/etc/charsooq/secrets`
  are recovered through the secret custodian. A dump contains password/session hashes and business
  data and is therefore treated as sensitive and encrypted.

## Alternatives

- **Raw volume snapshot as the primary backup.** Rejected: a live `pgdata` copy is not guaranteed
  consistent, is tied to the PostgreSQL major version, and gives no selective restore.
- **`pg_dumpall`.** Rejected: it includes cluster-wide roles and can carry role password hashes, which
  widens the secret exposure and conflicts with the three-role least-privilege model. Roles are
  recreated by `provision`.
- **PITR via WAL archiving now.** Rejected for this iteration: the storage target, credentials,
  encryption, retention, and restore procedure are unapproved. Claiming it without a drill would be
  unsafe.
- **A backup container in `compose.production.yml`.** Rejected: it would add another always-on
  service with access to the database and backup credentials, before the tooling and custody model are
  decided. The operation is documented instead.
- **Deleting/recreating the volume to recover.** Rejected: it destroys the only copy and turns a
  recoverable incident into data loss. Evidence is preserved first.

## Consequences

Positive:

- A recovery path exists using only committed, pinned components.
- The release process has an explicit backup gate and a recorded revision.
- Restores are testable without touching Production data.
- The model is honest about its recovery point: the last verified dump.

Residual risks / open items:

- RPO can be as large as the backup interval; RTO depends on dump size and restore throughput.
- No scheduler or alerting exists; a missed backup is silent until the checklist is run.
- No dedicated backup role; the dump uses the administrative credential inside the database container.
- Encryption tool, key custody, off-host destination, retention, and legal hold are unapproved.
- PITR/WAL archiving is not implemented.
- The administrative PostgreSQL password is not rotated by changing `POSTGRES_PASSWORD_FILE` on an
  existing volume; the documented `psql \password` procedure, TCP verification, atomic secret-file
  replacement, and rollback are in the Production runbook. The procedure was rehearsed with synthetic
  credentials.
- A database dump does not restore secret files or TLS material; those have separate custodians and
  procedures.

## References

- [Database backup and recovery runbook](../operations/backup-and-recovery.md)
- [Production runbook](../operations/production-runbook.md)
- [Troubleshooting](../operations/troubleshooting.md)
- [TLS certificate lifecycle](../operations/tls-certificate-lifecycle.md)
- [ADR 013 — TLS certificate lifecycle](013-tls-certificate-lifecycle.md)
- [Deployment](../architecture/deployment.md)
