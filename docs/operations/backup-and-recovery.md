# Database backup and recovery — چهارسوق Production

Status: **design only**. No backup has been taken, no archive exists in this repository, no database
or secret file was opened, and no restore was performed against Production. The procedures below are
for the operator on `market-linux`. The decision is recorded in
[ADR 014](../adr/014-production-backup-and-recovery.md).

Related: [Production runbook](production-runbook.md) · [Troubleshooting](troubleshooting.md) ·
[TLS certificate lifecycle](tls-certificate-lifecycle.md) (Caddy volumes and certificate material) ·
[Deployment](../architecture/deployment.md#production-secrets).

## 1. What exists today

| Capability                             | Status                                     | Notes                                                                 |
| -------------------------------------- | ------------------------------------------ | --------------------------------------------------------------------- |
| Logical PostgreSQL dump (`pg_dump`)    | Designed, not automated                    | The baseline in this document                                         |
| Encrypted archive                      | Designed                                   | Approved tool and key custody are open decisions                      |
| Off-host copy                          | Designed                                   | Destination and credentials are open decisions                        |
| Retention policy                       | Proposed                                   | Requires owner/IT approval; not configured                            |
| Restore drill                          | Required, not performed                    | Must pass before go-live and on the agreed cadence                    |
| Scheduled backup job                   | **Not implemented**                        | No timer/cron/agent is committed                                      |
| Dedicated backup role                  | **Not implemented**                        | The documented dump uses the admin role inside the DB container       |
| WAL archiving / Point-in-Time Recovery | **Not implemented**                        | No `archive_mode`, archive destination, or base-backup tooling exists |
| Physical base backup (`pg_basebackup`) | **Not implemented**                        | Would need a replication role and a storage target                    |
| Backup success/failure alerting        | **Not implemented**                        | Manual checklist until a monitoring channel exists                    |
| Production data copied off-host        | Not permitted without the approved process | Encrypted backup media is the exception, under custody rules          |

Do not assume any of the “not implemented” rows exists. In particular, a logical dump is **not** PITR:
the best recovery point is the last verified dump, not the last transaction.

## 2. What must be protected

| Item                               | Location                                           | Sensitivity                                 | Backup approach                                               |
| ---------------------------------- | -------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------- |
| Application data and schema        | `charsooq-production_pgdata` / database `charsooq` | Business data, password/session hashes      | Logical `pg_dump` (primary); cold volume copy optional        |
| PostgreSQL roles and grants        | Database catalog                                   | Role configuration (no passwords in a dump) | Recreated by `provision`, not restored from the dump          |
| `alembic_version`                  | Database table                                     | Release identity                            | Included in the dump; verify after restore                    |
| Caddy CA + issued certificates     | `charsooq-production_caddy_data`                   | Private keys; losing it breaks client trust | Encrypted, off-host; see TLS runbook                          |
| Caddy autosaved config             | `charsooq-production_caddy_config`                 | Internal config                             | Encrypted, off-host; see TLS runbook                          |
| Organization TLS material          | `${CHARSOOQ_TLS_DIR}`                              | Private key                                 | Encrypted, off-host, separate custody; see TLS runbook        |
| Compose, Caddy config, Dockerfiles | Git                                                | No secrets                                  | Git history + release SHA                                     |
| Deployment values (`CHARSOOQ_*`)   | Host/operator environment                          | Environment-specific, not secret            | Record in the release log; do not commit                      |
| Secret files                       | `/etc/charsooq/secrets`                            | Secrets                                     | **Not** part of the database backup; use the secret custodian |

A database dump contains password hashes, session hashes, and business data. Treat every dump as
sensitive even though it does not contain the role passwords or the secret files. Encrypt it and
restrict access.

## 3. Backup policy

### 3.1 Primary: logical dump

Use `pg_dump` in custom format for one database. It is portable across a fresh PostgreSQL 18.6
container, supports selective restore, and is small enough for the current single-host scale. Use the
`postgres:18.6-trixie` image for both dump and restore to avoid client/server version skew.

Why the admin role inside the container:

- the dump must read every table, including `alembic_version`, which the application role cannot read;
- the migration role owns the schema but the dump also needs catalog/ACL visibility;
- no password is placed on the command line: the container's local socket uses the image's local
  trust configuration, and the command runs inside the `db` container.

A dedicated, read-only backup role would be better least privilege and is a follow-up open decision.
Do not grant the application role extra rights just to make a dump work.

### 3.2 Secondary: cold volume copy (optional)

A raw copy of `pgdata` is only consistent when PostgreSQL is stopped. It is useful for evidence or a
fast same-version disaster restore, but it is not a substitute for a logical dump and is not portable
across major versions. If used, stop `db`, copy the volume read-only, encrypt it, and start `db` again.
Never copy a live data directory with `tar` and call it a backup.

### 3.3 Not a backup

- A Docker volume snapshot taken while PostgreSQL is running, without a filesystem-consistent
  mechanism.
- `caddy_data` alone (it is TLS state, not application data).
- A dump that has never been restored or at least listed/verified.
- A copy that exists only on the same host or the same volume.
- A Git checkout of the schema (migrations recreate structure, not data).

## 4. Taking a logical backup

### 4.1 Preflight

```bash
docker compose -f compose.production.yml ps db
docker compose -f compose.production.yml exec -T db \
  pg_isready -U charsooq -d charsooq -h 127.0.0.1
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT version_num FROM alembic_version;'
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc "SELECT pg_size_pretty(pg_database_size('charsooq'));"
df -h /var/lib/docker
```

Host/operator + container, read-only. Healthy: `db` is `healthy`, `accepting connections`, one
revision, and enough free space for the dump plus encryption overhead. Record the revision and
database size in the backup log. If the database is not healthy, fix it before dumping; a dump of a
corrupt database is not a recovery point.

### 4.2 Dump and encrypt in one stream

Choose the approved backup directory and encryption tool. The examples use `age`; `gpg` is an
acceptable alternative only if the organization approves it. `openssl enc` is unauthenticated and is
**not** the production format.

Run this block in a **root shell** on the host (the archive is root-owned; the Docker CLI works for
root). Do not run it as an operator who cannot write the root-only backup directory.

```bash
set -euo pipefail

BACKUP_DIR=/secure/charsooq-db-backups          # host path, root-owned 0700, outside the repo
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
ARCHIVE="$BACKUP_DIR/charsooq-$STAMP.dump.age"
RECIPIENT='<approved-age-recipient-or-key-id>'  # public key/recipient, not a secret

install -d -m 0700 -o root -g root "$BACKUP_DIR"

docker compose -f compose.production.yml exec -T db \
  pg_dump -U charsooq -d charsooq \
    --format=custom --compress=9 --no-owner --no-privileges \
  | age --encrypt --recipient "$RECIPIENT" \
  > "$ARCHIVE"

chmod 0600 "$ARCHIVE"
( cd "$BACKUP_DIR" && sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256" )
docker compose -f compose.production.yml exec -T db pg_dump --version
```

Host/root + container, read-only against the database; writes only the encrypted archive on the
host. `set -o pipefail` makes a failed `pg_dump` fail the pipeline instead of writing a truncated
archive. `--no-owner --no-privileges` makes the dump portable: restore it as the admin, then run
`provision` to transfer ownership to the migration role and apply the application grants. This is the
supported “existing objects owned by the admin” path.

Record, in the backup log:

```text
UTC timestamp:
Release SHA / image digests:
Database revision (alembic_version):
Database size:
Archive name / size:
Archive SHA-256:
Encryption recipient/key ID (not the private key):
pg_dump version:
Operator:
Off-host copy location / verification:
Restore test date/result:
```

Do not record the database URL, a password, or any secret file content.

### 4.3 Verify the archive

A dump that has not been read is unverified. At minimum, list the archive after decrypting into a
scratch directory with `0700`; preferably restore it (section 6).

```bash
SCRATCH=$(mktemp -d)
chmod 700 "$SCRATCH"
age --decrypt --identity '<approved-identity>' "$ARCHIVE" > "$SCRATCH/charsooq.dump"
docker run --rm --network none -v "$SCRATCH:/scratch:ro" postgres:18.6-trixie \
  pg_restore --list /scratch/charsooq.dump | sed -n '1,40p'
# Check that the listing contains TABLE DATA entries and the alembic_version table.
shred -u "$SCRATCH/charsooq.dump" 2>/dev/null || rm -f "$SCRATCH/charsooq.dump"
rmdir "$SCRATCH"
```

Host/root, temporary write only in a `0700` scratch directory. Expected: a valid archive listing with
schema and data entries, including `alembic_version`. If decryption or listing fails, the archive is
not a backup; fix the pipeline and retake it. Never leave the decrypted dump behind.

### 4.4 Move off-host

Copy the encrypted archive and its checksum to the approved off-host destination with the approved
transport. The encryption key/identity must be held separately from the destination.

```bash
# Example only; replace with the approved transport and destination.
rsync -av --chmod=F0600 "$ARCHIVE" "$ARCHIVE.sha256" \
  '<approved-backup-host>:/approved/path/'
ssh '<approved-backup-host>' "cd /approved/path && sha256sum -c '$(basename "$ARCHIVE").sha256'"
```

Host/root, state-changing (writes off-host). Verify the checksum **on the destination**, not only on
the source. A copy with the same key in the same place is not an off-host backup. Record the
destination and verification result, never the key.

### 4.5 Retention (proposal, not configured)

The following is a proposal for approval; it is not implemented by any timer:

| Tier    | Keep      | Purpose                      |
| ------- | --------- | ---------------------------- |
| Daily   | 14 days   | Recent operational recovery  |
| Weekly  | 8 weeks   | Medium-term recovery         |
| Monthly | 12 months | Longer-term recovery / audit |

Delete expired archives only through the approved retention process, never by `rm -rf` on a guess.
Retention, legal hold, and RPO/RTO are open decisions.

## 5. Backup before a migration

Take a verified backup before every migration that is not purely additive, and before the first
migration on an existing database. The release gate is:

1. Record the current `alembic_version` and image digests.
2. Dump, encrypt, checksum, and copy off-host.
3. Verify the archive (list or scratch restore).
4. Only then run `make prod-migrate`.
5. Record the archive ID next to the release.

| Migration shape                                      | Backup required? | Why                                                               |
| ---------------------------------------------------- | ---------------- | ----------------------------------------------------------------- |
| New nullable column, new table, new non-unique index | Recommended      | Usually backward-compatible, but a failed DDL still needs a point |
| Backfill or data rewrite                             | **Yes**          | Data changes are not reversed by a code rollback                  |
| Rename/drop/narrow type/add strict constraint        | **Yes**          | Old code may not read the new schema; recovery needs the dump     |
| Role/grant-only change (`provision`)                 | Recommended      | No data rewrite, but grants can lock out the API                  |
| Image/config only                                    | No               | No schema change; keep the previous digest                        |

A code rollback does not restore data. If the new code wrote rows or a migration transformed them,
only the dump (or a forward fix) recovers the prior state. Plan the data-loss window before choosing
restore.

## 6. Restore drills

A restore drill is mandatory before go-live and on the cadence approved by IT. It uses a **scratch**
container and volume, never the Production stack. This is the only place in this runbook that removes
a volume, and it removes only the clearly named drill volume.

### 6.1 Start a scratch PostgreSQL

```bash
docker volume create charsooq-restore-check
docker run -d --name charsooq-restore-check \
  --network none \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -e POSTGRES_DB=charsooq \
  -v charsooq-restore-check:/var/lib/postgresql \
  postgres:18.6-trixie
```

Host/operator, state-changing (creates a throwaway container/volume). No host port is published and
the network is disabled; `trust` is acceptable only because this container is isolated and disposable.
Never use this pattern for Production.

Wait for readiness:

```bash
until docker exec charsooq-restore-check pg_isready -U postgres -d charsooq >/dev/null 2>&1; do
  sleep 1
done
docker exec charsooq-restore-check pg_isready -U postgres -d charsooq
```

### 6.2 Restore and verify

```bash
age --decrypt --identity '<approved-identity>' "$ARCHIVE" \
  | docker exec -i charsooq-restore-check \
      pg_restore -U postgres -d charsooq --no-owner --no-privileges --exit-on-error

docker exec charsooq-restore-check psql -U postgres -d charsooq -tAc \
  'SELECT version_num FROM alembic_version;'

docker exec charsooq-restore-check psql -U postgres -d charsooq -c \
  'ANALYZE;'

docker exec charsooq-restore-check psql -U postgres -d charsooq -c \
  "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;"

docker exec charsooq-restore-check psql -U postgres -d charsooq -tAc \
  'SELECT count(*) FROM admins;'
```

Host/root (the archive is root-owned), state-changing only inside the drill container. Expected:
restore exits 0; the revision
equals the backup log; `admins` has one owner; table counts match the recorded pre-backup counts (allow
for normal growth if the dump is not the latest); no sequence errors. Then test a real query that the
application uses, for example a product/category count and a dashboard aggregate.

```bash
docker exec charsooq-restore-check psql -U postgres -d charsooq -tAc \
  'SELECT count(*) FROM products;'
docker exec charsooq-restore-check psql -U postgres -d charsooq -tAc \
  'SELECT count(*) FROM competitor_listings;'
```

### 6.3 Clean up the drill

```bash
docker rm -f charsooq-restore-check
docker volume rm charsooq-restore-check
```

Host/operator, **destructive to the drill only**. Confirm the name is exactly
`charsooq-restore-check`; never run this against `charsooq-production_pgdata`. Record the drill result,
the restore duration, and any count/revision mismatch.

## 7. Disaster restore

Choose the least destructive path that restores a verified point. Always preserve the current state
before changing it.

### 7.1 Preserve evidence first

```bash
docker compose -f compose.production.yml stop caddy web api
# Keep db stopped if it is corrupt; do not run initdb.
```

Host/operator, state-changing (traffic and API stop; database preserved).

If the volume is readable, snapshot it read-only to an encrypted archive before any removal:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 0700 -o root -g root /secure/charsooq-db-backups
docker run --rm --user 0 \
  --volume charsooq-production_pgdata:/source:ro \
  --volume /secure/charsooq-db-backups:/backup \
  postgres:18.6-trixie \
  tar -C /source -czf "/backup/pgdata-broken-$STAMP.tar.gz" .
# Encrypt with the approved tool, checksum, and copy off-host.
```

Host/root, read-only against the volume; writes an archive. If `tar` fails on a corrupted volume,
record what failed and do not delete the volume until the incident owner approves.

### 7.2 Restore into a running database (volume is intact)

Use this when PostgreSQL starts and the data is logically damaged but the volume is usable.

1. Stop `caddy`, `web`, and `api` so no writes occur.
2. Take a fresh dump of the current database if it is readable; preserve it as evidence.
3. Verify the chosen archive in a scratch container (section 6).
4. Replace only the `charsooq` database, not the volume. This is destructive; it requires an incident
   owner and a verified archive:

   ```bash
   # As the admin, from the maintenance database. Terminate other sessions first.
   docker compose -f compose.production.yml exec -T db \
     psql -U charsooq -d postgres -c \
     "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'charsooq' AND pid <> pg_backend_pid();"
   docker compose -f compose.production.yml exec -T db \
     psql -U charsooq -d postgres -c 'DROP DATABASE charsooq;'
   docker compose -f compose.production.yml exec -T db \
     psql -U charsooq -d postgres -c 'CREATE DATABASE charsooq OWNER charsooq;'
   ```

   Container, **destructive** (drops the current database). Do not run it before step 3 and before the
   evidence dump. `CREATE DATABASE ... OWNER charsooq` matches the image-created admin role; the
   migration role and grants are recreated next.

5. Restore the logical dump **before** provisioning. Run the command as root because the archive is
   root-owned. The empty database is owned by the admin; the dump is loaded with `--no-owner
--no-privileges`, so it does not need the application or migration role to exist yet. Do not run
   `provision` first: it creates `alembic_version`, and the dump also contains that table.

   ```bash
   age --decrypt --identity '<approved-identity>' "$ARCHIVE" \
     | docker compose -f compose.production.yml exec -T db \
         pg_restore -U charsooq -d charsooq --no-owner --no-privileges --exit-on-error
   ```

6. Run provisioning so objects owned by the admin are transferred to the migration role and the
   application grants are applied. If the archive is older than the current code, run `migrate` to
   reach head.

   ```bash
   make prod-provision
   make prod-migrate
   ```

7. If the owner account is missing (for example an older dump), run `make prod-bootstrap-owner`.
8. Delete restored sessions so pre-restore cookies cannot be reused:

   ```bash
   docker compose -f compose.production.yml exec -T db \
     psql -U charsooq -d charsooq -c 'DELETE FROM admin_sessions;'
   ```

   As the admin, after the backup. This is a security step, not data recovery; record it.

9. Start `api`, wait for healthy, start `web`, then `caddy`, and run the verification matrix.

### 7.3 Restore when the volume is corrupt or missing

If PostgreSQL cannot start and the volume is corrupt, you need a fresh data directory. Preserve the
old volume first (7.1). Removing it is **destructive and requires incident-owner approval**; only after
the evidence copy is encrypted and off-host:

```bash
# STOP: confirm the volume name and that the evidence copy is verified.
docker compose -f compose.production.yml down          # keeps volumes
docker volume rm charsooq-production_pgdata            # destructive; never routine
docker compose -f compose.production.yml up -d --wait --wait-timeout 120 db
```

Host/operator, **destructive**. The new `db` initializes an empty volume and creates the
admin role/database from `postgres_password`. Restore the dump as in 7.2 step 5 **before**
provisioning, then run `make prod-provision`, `make prod-migrate`, and bootstrap if needed, then start
the app. If you cannot remove the volume under policy, use a compose override with a new, clearly
named volume and document the deviation; do not improvise an in-place repair with `initdb`.

### 7.4 Storage failure

If the host disk/volume is lost:

1. Provision a replacement host/volume with the same Docker and PostgreSQL versions.
2. Restore the six secret files from the approved secret custodian (the database dump does not contain
   them). Verify ownership/mode, not contents.
3. Restore the latest verified dump; restore Caddy/TLS material from their separate backup if needed.
4. Rebuild the images from the approved release SHA or pull the recorded digests.
5. Run the full startup sequence (db → restore → provision → migrate → bootstrap → api → web →
   caddy) and the verification matrix. Restore before `provision` so the dump creates
   `alembic_version` before provisioning owns it.
6. Record the actual RPO (time of the dump) and RTO (detected to verified service).

### 7.5 Isolated rehearsal result

The order and flags above were rehearsed against a throwaway PostgreSQL 18.6 cluster with synthetic
data, separate from Production. The rehearsal:

| Check                                                                                 | Result                                                                                                                       |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `pg_restore --no-owner --no-privileges` into an empty database on a **fresh cluster** | Succeeded; objects were created as the administrative role and then transferred by `provision`.                              |
| `pg_restore` without `--no-owner` on a fresh cluster                                  | Failed: `ERROR: role "charsooq_migrator" does not exist`. `--no-owner --no-privileges` is therefore mandatory.               |
| Run `provision` before restore                                                        | `provision` created `alembic_version`; `pg_restore --exit-on-error` failed with `relation "alembic_version" already exists`. |
| Restore **before** `provision`, then `provision`                                      | Succeeded. Migration role owned `public` and every table; application role had `SELECT/INSERT/UPDATE/DELETE` on `products`.  |
| Application role after restore + provision                                            | TCP login worked; `CREATE TABLE` on `public` denied; `SELECT` on `alembic_version` denied.                                   |
| Default privileges after restore + provision                                          | A table created by the migration role received app `SELECT/INSERT/UPDATE/DELETE`; a table created by the admin did not.      |
| `bootstrap_owner.py` after restore + provision                                        | Succeeded; the owner row existed with role `owner`.                                                                          |
| `migrate.py` after restore at head                                                    | No-op: `migrate: database is at head`.                                                                                       |

The rehearsal used only synthetic rows and was destroyed afterwards. It used the locally available
`postgres:18` image (PostgreSQL 18.6) and a `charsooq-api:rehearsal` image rebuilt from the current
checkout, because the pre-existing local image predates
`provision_database_roles.py`. Production must use the approved, pinned image/digest built from the
release commit, not a stale local image.

## 8. Consistency checks after restore

Run these before declaring recovery complete:

| Check                        | Command / query                                      | Expected                                                        |
| ---------------------------- | ---------------------------------------------------- | --------------------------------------------------------------- |
| Database accepts connections | `pg_isready -U charsooq -d charsooq -h 127.0.0.1`    | `accepting connections`                                         |
| Revision                     | `SELECT version_num FROM alembic_version;`           | Equals the release/dump record; run `migrate` if older          |
| Owner                        | `SELECT count(*) FROM admins WHERE role = 'owner';`  | `1`                                                             |
| Key table counts             | `SELECT count(*) FROM products;` etc.                | Matches the recorded counts within expected growth              |
| Sequences                    | `SELECT sequencename, last_value FROM pg_sequences;` | `last_value` is at or above the max id; no `NULL` for used seqs |
| Grants/ownership             | `provision` output, `\dn+`, `\dt` owners             | Migration role owns objects; app has DML, no schema `CREATE`    |
| Application readiness        | `curl … /api/v1/ready`                               | `{"status":"ready"}`                                            |
| Login                        | Browser on an approved client                        | Owner login works; session cookie is `Secure`/`HttpOnly`/`Lax`  |
| Spot checks                  | One product, one category, one dashboard aggregate   | Values match expectations; no 500s                              |
| Sessions                     | `SELECT count(*) FROM admin_sessions;`               | `0` after the deliberate logout-all, or a known value           |
| Backups                      | Latest archive checksum, off-host copy, restore date | Present and verified                                            |

`ANALYZE` after a restore is safe and improves planner statistics. Do not run `VACUUM FULL` as part of
recovery; it takes an exclusive lock and needs free disk equal to the table size.

## 9. Point-in-Time Recovery (not implemented)

PITR is **not** available. The architecture has:

- no `archive_mode = on`;
- no `archive_command` or archive destination;
- no base backup;
- no `restore_command`;
- no retention/verification for WAL.

A logical dump restores to the moment of the dump, not to an arbitrary transaction. If the
organization requires a low RPO, the follow-up design needs approved storage and tooling, for example:

1. A dedicated replication/backup role.
2. A base backup taken on a schedule.
3. Continuous WAL archiving to an off-host, encrypted object store.
4. A tested `restore_command` and recovery target procedure.
5. Retention, encryption, access control, and a restore drill for the WAL chain.
6. Monitoring for archive failures and gaps.

Do not claim PITR exists because a volume snapshot or a dump is present. Adding it is a separate ADR
and a change to the PostgreSQL configuration, not a documentation-only step.

## 10. Monitoring backup success

Until a scheduler and alert channel are approved, use this manual checklist after every backup:

- [ ] `pg_dump` exited 0 (pipefail; no truncated stream).
- [ ] Archive exists, is non-zero, and has mode `0600`.
- [ ] SHA-256 recorded and matches.
- [ ] Archive decrypts and lists (or restores) successfully.
- [ ] Off-host copy exists and its checksum matches on the destination.
- [ ] Revision, size, release SHA, and operator recorded.
- [ ] Retention job (if any) did not delete the newest verified copy.
- [ ] Restore drill date is within the approved cadence.

Failure of any item means the backup is not trustworthy. Treat a missed backup as an incident when the
RPO would be exceeded. An external monitor should eventually alert on: last successful backup age,
archive size anomaly, checksum failure, off-host copy failure, and restore-drill age.

## 11. Open decisions

| Decision                                   | Why it blocks a production backup policy                                                                                      |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| RPO and RTO                                | Determines dump frequency, retention, and whether PITR is needed                                                              |
| Approved encryption tool and key custody   | No archive may be created without it                                                                                          |
| Off-host destination and access control    | “Off-host” is not defined yet                                                                                                 |
| Retention and legal hold                   | Cannot delete or keep archives without a policy                                                                               |
| Scheduler/owner                            | No backup timer or paging owner exists                                                                                        |
| Dedicated backup role                      | Least privilege for dumps is not implemented                                                                                  |
| PITR/WAL archiving                         | Not implemented; requires storage/tooling and a restore drill                                                                 |
| Restore drill cadence and sign-off         | A backup is unverified until restored                                                                                         |
| Secret-file recovery custodian             | The database dump does not restore the secrets                                                                                |
| Administrative password rotation procedure | Resolved: the image does not re-apply the file, but the runbook documents a verified `psql \password` procedure (section 9.4) |

If any of these is unknown, the safe state is a **verified logical dump plus an explicit statement
that PITR is unavailable**, not an assumption that a volume snapshot is enough.
