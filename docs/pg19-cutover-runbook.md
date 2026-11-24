# Production PostgreSQL 18 → 19 cutover runbook

Scope: the real Production host (`market-linux`, repository checkout at `/opt/charsooq`).
This is the operational companion to [ADR 028](adr/028-postgresql-19-upgrade-readiness.md).
The repository already pins `postgres:19.0-trixie` and builds `postgresql-client-19`
into the API image; the only remaining work is the **data** migration and the deploy.

> **Why a runbook, not just a tag change.** The 18+ `postgres` image refuses to
> start if it finds a `PG_VERSION` file at `/var/lib/postgresql/*/docker`.
> Starting 19 on the current volume without moving the 18 datadir would either
> fail at startup or create an empty cluster. Never delete a volume or datadir.

All commands below run on the server unless stated otherwise. Source the host env
first, and never print a database URL, host, username, password, or secret:

```bash
cd /opt/charsooq
set -a; . /etc/charsooq/production.env; set +a
```

## 0. Record the current state

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR=/var/backups/charsooq-upgrade-$STAMP
mkdir -p "$BACKUP_DIR" && chmod 0700 "$BACKUP_DIR"

docker compose -f compose.production.yml exec -T db psql -U charsooq -d charsooq -At \
  -c 'select version();' \
  -c "select current_setting('data_directory');" \
  -c 'select version_num from alembic_version;' \
  -c "select extname, extversion from pg_extension order by 1;" \
  -c "select 'products', count(*) from products union all select 'admins', count(*) from admins;" \
  | tee "$BACKUP_DIR/preflight.txt"

docker compose -f compose.production.yml config --format json | jq -r '.services.db.image'
docker compose -f compose.production.yml exec -T db sh -c \
  'cat /var/lib/postgresql/18/docker/PG_VERSION'
df -h / /var/lib/docker
```

Keep `preflight.txt`: it is the comparison baseline after the upgrade.

## 1. Ship the PostgreSQL 19 client first

The API image already installs `postgresql-client-19`; a 18 client cannot dump a
19 server. Pull the release image that contains it **before** the maintenance
window so the dump can be taken with either server version:

```bash
make prod-deploy-simulate          # preview only, touches nothing
make prod-pull                     # with the release image refs exported
docker compose -f compose.production.yml run --rm --no-deps api pg_dump --version
```

Expect `pg_dump (PostgreSQL) 19.x`.

## 2. Take a full administrative dump and copy it off-host

The in-app backup is **not** sufficient: it excludes `alembic_version`, sessions
and backup records. Use the database's administrative role:

```bash
docker compose -f compose.production.yml exec -T db pg_dump -Fc \
  --no-owner --no-privileges -U charsooq -d charsooq \
  > "$BACKUP_DIR/charsooq-full-$STAMP.fc"

docker compose -f compose.production.yml exec -T db pg_dumpall \
  --globals-only --no-role-passwords -U charsooq \
  > "$BACKUP_DIR/charsooq-globals-$STAMP.sql"

sha256sum "$BACKUP_DIR"/* > "$BACKUP_DIR/SHA256SUMS"
# Verify the archive can be listed before relying on it:
docker cp "$BACKUP_DIR/charsooq-full-$STAMP.fc" \
  "$(docker compose -f compose.production.yml ps -q db)":/tmp/verify.fc
docker compose -f compose.production.yml exec -T db pg_restore -l /tmp/verify.fc | head
tar czf "$BACKUP_DIR.tar.gz" -C "$(dirname "$BACKUP_DIR")" "$(basename "$BACKUP_DIR")"
scp "$BACKUP_DIR.tar.gz" operator@offhost:/approved/backup/path/
```

Do **not** apply `charsooq-globals-*.sql` to a live Production cluster; it is for
DR/empty clusters only. Pause scheduled backups for the window via the owner
settings in the panel.

## 3. Rehearse on scratch containers

Host ports 55432 and 55433 must be free. The drill creates and removes only its
own `charsooq-upgrade-drill-*` containers and volumes:

```bash
./deploy/scripts/pg_upgrade_drill.sh "$BACKUP_DIR/charsooq-full-$STAMP.fc" --with-tests
```

It restores the dump into a scratch 18 cluster, dumps/restores into a scratch 19
cluster, and checks version, data directory, migration revision and row counts.
Do not continue if it fails.

## 4. Stop writes and take the final dump

```bash
docker compose -f compose.production.yml stop web api caddy provision migrate db

docker compose -f compose.production.yml up -d db   # only the 18 db, briefly
docker compose -f compose.production.yml exec -T db pg_dump -Fc \
  --no-owner --no-privileges -U charsooq -d charsooq \
  > "$BACKUP_DIR/charsooq-final-$STAMP.fc"
sha256sum "$BACKUP_DIR/charsooq-final-$STAMP.fc" | tee -a "$BACKUP_DIR/SHA256SUMS"
scp "$BACKUP_DIR/charsooq-final-$STAMP.fc" operator@offhost:/approved/backup/path/
docker compose -f compose.production.yml stop db
```

Never use `compose down -v` or `docker volume rm`.

## 5. Migrate the data into the 19 cluster

`pg19_cutover.sh` keeps the 18 datadir at `/var/lib/postgresql/rollback/18` on
the **same** `pgdata` volume, creates a 19 cluster there, restores the final dump,
and verifies it:

```bash
./deploy/scripts/pg19_cutover.sh "$BACKUP_DIR/charsooq-final-$STAMP.fc"
```

It refuses to run while services are up, when the compose pin is not 19, or when
a 19 cluster already exists (a second run is a no-op). On success both datadirs
remain in the volume:

```bash
docker run --rm --network none -v chaharsooq-production_pgdata:/var/lib/postgresql \
  --entrypoint sh postgres:19.0-trixie \
  -c 'cat /var/lib/postgresql/19/docker/PG_VERSION; cat /var/lib/postgresql/rollback/18/docker/PG_VERSION'
# expect: 19 then 18
```

## 6. Verify config and deploy

The compose pin in this repository is already `19.0-trixie`; make sure the host
checkout has it, then run the normal deploy. It re-checks the on-disk major
before and after release discovery, applies Alembic migrations only when needed,
and gates completion on real health checks:

```bash
grep -n 'image: postgres:' compose.production.yml
make prod-config
make prod-deploy VERSION=v<release>     # or omit VERSION for the newest release
```

## 7. Verify and refresh backups

```bash
docker compose -f compose.production.yml exec -T db psql -U charsooq -d charsooq -At \
  -c 'select version();' \
  -c "select current_setting('data_directory');" \
  -c 'select version_num from alembic_version;' \
  -c 'select count(*) from products;'
# compare with preflight.txt

curl -fsS "http://$CHARSOOQ_SITE_HOST/api/v1/health"
curl -fsS "http://$CHARSOOQ_SITE_HOST/api/v1/ready"
curl -fsS "http://$CHARSOOQ_SITE_HOST/login"
make doctor-prod

# Fresh 19-era full dump, copied off-host:
docker compose -f compose.production.yml exec -T db pg_dump -Fc \
  --no-owner --no-privileges -U charsooq -d charsooq \
  > "$BACKUP_DIR/charsooq-post19-$STAMP.fc"
sha256sum "$BACKUP_DIR/charsooq-post19-$STAMP.fc"
scp "$BACKUP_DIR/charsooq-post19-$STAMP.fc" operator@offhost:/approved/backup/path/

# Resume scheduled backups in the owner settings.
```

## 8. Rollback

A code-only rollback is **not** enough after the cutover: the old 18 image
cannot serve the 19 cluster. To return to 18:

```bash
docker compose -f compose.production.yml stop web api caddy provision migrate db
docker run --rm --network none -v chaharsooq-production_pgdata:/var/lib/postgresql \
  --entrypoint sh postgres:19.0-trixie \
  -c 'rm -rf /var/lib/postgresql/19 && mv /var/lib/postgresql/rollback/18 /var/lib/postgresql/18'
# Switch the host checkout to the release with postgres:18.6-trixie and an
# 18-client API image, then:
make prod-config
make prod-deploy VERSION=v<last-18-release>
```

Keep the abandoned 19 datadir as evidence until the rollback is verified. If the
18 datadir is unusable, restore `charsooq-final-$STAMP.fc` into a fresh 18 cluster
and re-run `provision`/`migrate` before starting the API.
