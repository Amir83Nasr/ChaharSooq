#!/usr/bin/env bash
# Rehearse a PostgreSQL 18 -> 19 logical upgrade on throwaway containers only.
# It never starts, stops, reads or deletes a Production container or volume.
#
# Usage (from the repository root):
#   ./deploy/scripts/pg_upgrade_drill.sh /path/to/full-admin-dump.fc [--with-tests]
#
# The dump must be a full administrative-role pg_dump custom-format archive
# (see ADR 028). The optional --with-tests flag runs the opt-in real-grants test
# against the scratch 19 container; it needs `uv` and the repo dev dependencies.
set -euo pipefail

log() { printf '[drill] %s\n' "$*"; }
fail() { printf '[drill] ERROR: %s\n' "$*" >&2; exit 1; }

[ $# -ge 1 ] && [ $# -le 2 ] || {
  printf 'usage: %s <full-dump.fc> [--with-tests]\n' "$0" >&2
  exit 2
}
dump_file="$1"
[ "${2:-}" = "--with-tests" ] || [ $# -eq 1 ] || fail "unknown argument: $2"
[ -f "$dump_file" ] || fail "dump file not found: $dump_file"
command -v docker >/dev/null 2>&1 || fail "docker is required"

# Fixed names: no operator input is interpolated into Docker resource names.
pg18="${DRILL_PG18_CONTAINER:-charsooq-upgrade-drill-pg18}"
pg19="${DRILL_PG19_CONTAINER:-charsooq-upgrade-drill-pg19}"
vol18="${DRILL_PG18_VOLUME:-charsooq-upgrade-drill-pg18-data}"
vol19="${DRILL_PG19_VOLUME:-charsooq-upgrade-drill-pg19-data}"
image18="${DRILL_PG18_IMAGE:-postgres:18.6-trixie}"
image19="${DRILL_PG19_IMAGE:-postgres:19.0-trixie}"

cleanup() {
  log "removing scratch resources"
  docker rm -f "$pg18" "$pg19" >/dev/null 2>&1 || true
  docker volume rm "$vol18" "$vol19" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_ready() {
  local container="$1" attempt
  for attempt in $(seq 1 30); do
    if docker exec "$container" pg_isready -U charsooq -d charsooq >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  fail "$container did not become ready"
}

state() {
  local container="$1"
  docker exec "$container" psql -v ON_ERROR_STOP=1 -U charsooq -d charsooq -At \
    -c "select version();" \
    -c "select current_setting('data_directory');" \
    -c "select version_num from alembic_version;" \
    -c "select count(*) from products;" \
    -c "select count(*) from admins;"
}

log "starting scratch $image18 and $image19 containers"
cleanup
docker volume create "$vol18" >/dev/null
docker volume create "$vol19" >/dev/null
docker run -d --name "$pg18" \
  -e POSTGRES_USER=charsooq -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=charsooq \
  -v "$vol18:/var/lib/postgresql" -p 127.0.0.1:55432:5432 "$image18" >/dev/null
docker run -d --name "$pg19" \
  -e POSTGRES_USER=charsooq -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=charsooq \
  -v "$vol19:/var/lib/postgresql" -p 127.0.0.1:55433:5432 "$image19" >/dev/null
wait_ready "$pg18"
wait_ready "$pg19"

log "restoring the full dump into the scratch 18 cluster"
docker exec -i "$pg18" pg_restore --no-owner --no-privileges --exit-on-error \
  -U charsooq -d charsooq < "$dump_file"
state_18="$(state "$pg18")"

log "dumping 18 and restoring into the scratch 19 cluster"
docker exec "$pg18" pg_dump -Fc --no-owner --no-privileges -U charsooq -d charsooq |
  docker exec -i "$pg19" pg_restore --no-owner --no-privileges --exit-on-error \
    -U charsooq -d charsooq
state_19="$(state "$pg19")"

log "scratch 18: $state_18"
log "scratch 19: $state_19"
case "$state_19" in
  *"PostgreSQL 19"*) ;;
  *) fail "scratch 19 does not report PostgreSQL 19" ;;
esac
# Every line matters: a missing alembic_version row or a different data
# directory must fail the drill, not just a row-count mismatch.
migration_18="$(printf '%s\n' "$state_18" | sed -n '3p')"
migration_19="$(printf '%s\n' "$state_19" | sed -n '3p')"
[ -n "$migration_18" ] && [ "$migration_18" = "$migration_19" ] ||
  fail "migration revision differs (18: '${migration_18:-empty}', 19: '${migration_19:-empty}')"
counts_18="$(printf '%s\n' "$state_18" | tail -n 2)"
counts_19="$(printf '%s\n' "$state_19" | tail -n 2)"
[ -n "$counts_18" ] && [ "$counts_18" = "$counts_19" ] || fail "row counts differ after the upgrade"

if [ "${2:-}" = "--with-tests" ]; then
  log "running the opt-in real-grants test against scratch 19"
  CHARSOOQ_TEST_POSTGRES_ADMIN_URL=postgresql://charsooq:drill@127.0.0.1:55433/charsooq \
    uv run --project backend/api pytest -q backend/api/tests/test_role_grants_postgres.py
fi

log "drill passed: data, migration revision and major version match"
