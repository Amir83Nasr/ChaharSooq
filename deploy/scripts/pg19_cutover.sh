#!/usr/bin/env bash
# Production data cutover 18 -> 19, on the server, against the real pgdata volume.
#
# This fills the gap between ADR 028's runbook and deploy.sh's fail-closed guard:
# deploy.sh refuses to start PostgreSQL 19 until a healthy 19 cluster exists in
# the pgdata volume. This script creates that cluster by restoring a verified
# full dump, while keeping the original 18 datadir intact for rollback.
#
# The postgres:18+ entrypoint refuses to start when it finds a PG_VERSION file
# directly under /var/lib/postgresql/*/docker, so the 18 datadir is moved to
# /var/lib/postgresql/rollback/18 on the SAME volume. Nothing is deleted.
#
# Run it ONLY after the rehearsal (deploy/scripts/pg_upgrade_drill.sh) passed and
# the stack was stopped for the maintenance window. The script never removes a
# volume, a datadir, an image, or the dump file. Once a healthy 19 cluster
# exists, re-running it is a no-op.
#
# Usage (from /opt/charsooq on the server):
#   ./deploy/scripts/pg19_cutover.sh /var/backups/charsooq-final-<stamp>.fc
#
# Optional overrides (see deploy/README.md):
#   CHARSOOQ_PGDATA_VOLUME   named volume (default: chaharsooq-production_pgdata)
#   PG19_CUTOVER_IMAGE       PostgreSQL 19 image (default: compose pin)
#   PG19_CUTOVER_CONTAINER   scratch container name (default: fixed, see below)
set -euo pipefail

log() { printf '[cutover] %s\n' "$*"; }
fail() { printf '[cutover] ERROR: %s\n' "$*" >&2; exit 1; }

[ $# -eq 1 ] || {
  printf 'usage: %s <verified-full-dump.fc>\n' "$0" >&2
  exit 2
}
dump_file="$1"
[ -f "$dump_file" ] || fail "dump file not found: $dump_file"
command -v docker >/dev/null 2>&1 || fail "docker is required"
command -v jq >/dev/null 2>&1 || fail "jq is required to read the compose image"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="${CHARSOOQ_COMPOSE_FILE:-$repo_root/compose.production.yml}"
secret_dir="${CHARSOOQ_SECRETS_DIR:-/etc/charsooq/secrets}"
volume="${CHARSOOQ_PGDATA_VOLUME:-chaharsooq-production_pgdata}"
container="${PG19_CUTOVER_CONTAINER:-charsooq-upgrade-cutover-pg19}"

[ -f "$compose_file" ] || fail "compose file not found: $compose_file"
[ -f "$secret_dir/postgres_password" ] || fail "missing secret: postgres_password (path not printed)"
[ -r "$secret_dir/postgres_password" ] || fail "postgres_password is not readable by this account"

# The compose pin is the single source of truth for the target image; do not
# let a manual override silently upgrade to an unpinned minor.
db_image="$(docker compose -f "$compose_file" config --format json 2>/dev/null |
  jq -r '.services.db.image // empty')" || fail "cannot read the database image from $compose_file"
case "$db_image" in
  postgres:19.*) ;;
  *) fail "compose does not pin PostgreSQL 19 ($db_image); switch the pin first" ;;
esac
image="${PG19_CUTOVER_IMAGE:-$db_image}"

# Never run against a live stack: api/web would reach the new cluster too early.
active="$(docker compose -f "$compose_file" ps -q db api web 2>/dev/null || true)"
[ -z "$active" ] || fail "production services are still running; stop them first (ADR 028 cutover step 1)"

docker volume inspect "$volume" >/dev/null 2>&1 || fail "pgdata volume not found: $volume"

# A helper container reads the volume. The entrypoint is overridden so no
# server starts and no PostgreSQL image can auto-initialise anything.
volume_sh() {
  docker run --rm --network none \
    -v "$volume:/var/lib/postgresql" --entrypoint sh "$image" -c "$1" 2>/dev/null
}

marker_18="$(volume_sh "[ -s /var/lib/postgresql/18/docker/PG_VERSION ] && cat /var/lib/postgresql/18/docker/PG_VERSION || true")" ||
  fail "cannot read the 18 cluster marker from $volume"
marker_19="$(volume_sh "[ -s /var/lib/postgresql/19/docker/PG_VERSION ] && cat /var/lib/postgresql/19/docker/PG_VERSION || true")" ||
  fail "cannot read the 19 cluster marker from $volume"

if [ -n "$marker_19" ]; then
  log "a PostgreSQL $marker_19 cluster already exists in $volume; nothing to do"
  log "verify it and run make prod-deploy instead"
  exit 0
fi
[ "$marker_18" = "18" ] || fail "no PostgreSQL 18 datadir in $volume (found '${marker_18:-none}'); do not continue without a verified rollback copy"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

log "keeping the 18 datadir at /var/lib/postgresql/rollback/18 (same volume, no deletion)"
volume_sh "mkdir -p /var/lib/postgresql/rollback && \
  { [ -e /var/lib/postgresql/rollback/18 ] && exit 1 || mv /var/lib/postgresql/18 /var/lib/postgresql/rollback/18; }" ||
  fail "cannot move the 18 datadir; the volume already has a rollback/18 entry"

log "creating a scratch PostgreSQL 19 cluster inside $volume"
docker run -d --name "$container" --network none \
  -e POSTGRES_USER=charsooq -e POSTGRES_DB=charsooq \
  -e POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password \
  -v "$volume:/var/lib/postgresql" \
  -v "$secret_dir/postgres_password:/run/secrets/postgres_password:ro" \
  "$image" >/dev/null

ready=0
for attempt in $(seq 1 30); do
  if docker exec "$container" pg_isready -U charsooq -d charsooq -h 127.0.0.1 >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[ "$ready" -eq 1 ] || fail "scratch 19 cluster did not become ready; the 18 datadir is kept at rollback/18"

cluster_major="$(docker exec "$container" sh -c \
  "cat /var/lib/postgresql/19/docker/PG_VERSION" 2>/dev/null)" || fail "19 cluster has no PG_VERSION"
[ "$cluster_major" = "19" ] || fail "unexpected cluster major '$cluster_major'"

log "restoring the verified dump into the scratch 19 cluster"
docker exec -i "$container" pg_restore --no-owner --no-privileges --exit-on-error \
  -U charsooq -d charsooq < "$dump_file" ||
  fail "pg_restore failed; remove the empty 19 datadir manually and restore rollback/18 before retrying"

log "verifying data, migration revision and major version"
state="$(docker exec "$container" psql -v ON_ERROR_STOP=1 -U charsooq -d charsooq -At \
  -c 'select version();' \
  -c "select current_setting('data_directory');" \
  -c 'select version_num from alembic_version;' \
  -c 'select count(*) from products;' \
  -c 'select count(*) from admins;')" || fail "verification query failed"
case "$state" in
  *"PostgreSQL 19"*) ;;
  *) fail "restored cluster does not report PostgreSQL 19" ;;
esac
case "$state" in
  *"/var/lib/postgresql/19/docker"*) ;;
  *) fail "restored cluster is not using the 19 datadir" ;;
esac
migration_revision="$(printf '%s\n' "$state" | sed -n '3p')"
[ -n "$migration_revision" ] || fail "alembic_version is empty; the dump is not a complete administrative dump"

log "scratch 19 state: $state"
log "stopping the scratch container; both datadirs stay in $volume"
docker stop "$container" >/dev/null
docker rm "$container" >/dev/null
trap - EXIT

log "cutover complete: the 19 cluster is ready in $volume"
log "next: make prod-config && make prod-deploy VERSION=v<release>"
log "rollback: stop the stack, move rollback/18 back to /var/lib/postgresql/18, restore the 18 pin; keep the 19 datadir as evidence (ADR 028)"
