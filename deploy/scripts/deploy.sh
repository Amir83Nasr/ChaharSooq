#!/usr/bin/env bash
# Single-slot Production deploy entry point, run on the server after a release.
#
# Usage (from /opt/charsooq on the server):
#   ./deploy/scripts/deploy.sh                 # newest published GitHub release
#   ./deploy/scripts/deploy.sh latest          # same as above
#   ./deploy/scripts/deploy.sh v1.2.3          # a specific published release
#   ./deploy/scripts/deploy.sh <api@sha256:..> <web@sha256:..>   # explicit digests
#
# With no argument the newest published GitHub Release is read from the API,
# its version tag is resolved to two immutable digests, and both images must
# report that version and the release commit before anything changes. The
# release is published only after CI verified the images (ADR 019), so this is
# the single all-or-nothing signal the operator needs. Nothing is removed;
# rollback is the same command with the previous version tag.
set -euo pipefail

COMPOSE_FILE="${CHARSOOQ_COMPOSE_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/compose.production.yml}"
ENV_FILE="${CHARSOOQ_ENV_FILE:-/etc/charsooq/production.env}"
TOTAL_STEPS=10
STEP=0
START_SECONDS=$SECONDS
BOLD=""
RESET=""
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  BOLD=$'\033[1m'
  RESET=$'\033[0m'
fi

log() { printf '[deploy] %s\n' "$*"; }
fail() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }
step() {
  STEP=$((STEP + 1))
  printf '\n[deploy] %s[%d/%d] %s%s\n' "$BOLD" "$STEP" "$TOTAL_STEPS" "$*" "$RESET"
}
note() { printf '[deploy]     %s\n' "$*"; }
skip() { printf '[deploy]     (skip) %s\n' "$*"; }

usage() {
  printf 'usage: %s [latest | vMAJOR.MINOR.PATCH | <api-ref@sha256:...> <web-ref@sha256:...>]\n' "$0" >&2
  exit 2
}

[ $# -le 2 ] || usage

step "Validating host configuration"

# The release identity must survive anything left in the host env file.
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a
  . "$ENV_FILE"
  set +a
fi

[ -f "$COMPOSE_FILE" ] || fail "compose file not found: $COMPOSE_FILE"

for name in CHARSOOQ_PROXY_BIND_IP CHARSOOQ_SITE_HOST CHARSOOQ_EDGE_SUBNET \
  CHARSOOQ_WEB_EDGE_IP CHARSOOQ_PUBLIC_SCHEME; do
  [ -n "${!name:-}" ] || fail "$name is not set in $ENV_FILE"
done
case "${CHARSOOQ_PUBLIC_SCHEME}" in
  http) CHARSOOQ_PUBLIC_PORT="${CHARSOOQ_PUBLIC_PORT:-80}" ;;
  https) CHARSOOQ_PUBLIC_PORT="${CHARSOOQ_PUBLIC_PORT:-443}" ;;
  *) fail "CHARSOOQ_PUBLIC_SCHEME must be 'http' or 'https'" ;;
esac
export CHARSOOQ_PUBLIC_SCHEME CHARSOOQ_PUBLIC_PORT

# Secret files stay root/UID-owned and are mounted by the Docker daemon. The
# deploy account never reads them; only the directory's presence is checked.
secret_dir="${CHARSOOQ_SECRETS_DIR:-/etc/charsooq/secrets}"
[ -d "$secret_dir" ] || fail "secret directory not found: $secret_dir"

command -v docker >/dev/null 2>&1 || fail "docker is required"
command -v curl >/dev/null 2>&1 || fail "curl is required for the GitHub API and health probes"
command -v jq >/dev/null 2>&1 || fail "jq is required to read the release and image labels"
note "host configuration, secret directory and command dependencies are valid"

COMPOSE=(docker compose -f "$COMPOSE_FILE")

step "Checking database cluster version"

# A major-version bump is a data migration, not just a new image tag: a newer
# image would initialise an empty cluster beside the old one and the API would
# silently see an empty database. Refuse to start until the on-disk cluster and
# the configured image agree on the major version.
db_image="$("${COMPOSE[@]}" config --format json 2>/dev/null |
  jq -r '.services.db.image // empty')" || fail "cannot read the database image from $COMPOSE_FILE"
case "$db_image" in
  postgres:*) ;;
  *) fail "unexpected database image in $COMPOSE_FILE: ${db_image:-<none>}" ;;
esac
image_major="${db_image#postgres:}"
image_major="${image_major%%.*}"

# Read only the cluster directory for this image's major: after a logical
# upgrade the old major's datadir stays in the same volume for rollback.
cluster_major="$("${COMPOSE[@]}" run --rm --no-deps --entrypoint sh db -c \
  "test -f '/var/lib/postgresql/$image_major/docker/PG_VERSION' && \
   cat '/var/lib/postgresql/$image_major/docker/PG_VERSION' || true" 2>/dev/null)" || fail "cannot read the database cluster version from the pgdata volume"
case "$cluster_major" in
  "$image_major") ;;
  "")
    fail "no PostgreSQL $image_major cluster in the pgdata volume.
     Run the 18 -> 19 data cutover first (ADR 028):
       1. take a verified full administrative dump and rehearse with ./deploy/scripts/pg_upgrade_drill.sh <dump.fc> --with-tests
       2. stop the stack, then run ./deploy/scripts/pg19_cutover.sh <dump.fc>
       3. re-run this deploy
     Never start the $db_image image against an older cluster: it would serve an empty database."
    ;;
  *)
    fail "cluster is PostgreSQL $cluster_major but the image is $db_image.
     A major bump is a data migration, not a tag change. Follow ADR 028:
       ./deploy/scripts/pg_upgrade_drill.sh <verified-dump.fc> --with-tests
       ./deploy/scripts/pg19_cutover.sh <verified-dump.fc>
     Deploy is refused until the $image_major cluster holds the data."
    ;;
esac
note "cluster and image agree on PostgreSQL major $image_major"

# ─── RELEASE DISCOVERY ───────────────────────────────────────────────────────

github_header_file=""
cleanup() {
  [ -z "$github_header_file" ] || rm -f "$github_header_file"
}
trap cleanup EXIT

# The optional token supports private repositories. It travels in a 0600
# header file instead of a command-line argument and is never logged.
fetch_release() {
  local endpoint="$1" url
  url="https://api.github.com/repos/${CHARSOOQ_GITHUB_REPO}/${endpoint}"
  local -a options=(
    -fsS --retry 2 --retry-delay 1 --connect-timeout 5 --max-time 20
    -H 'Accept: application/vnd.github+json'
    -H 'X-GitHub-Api-Version: 2022-11-28'
  )
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    github_header_file="$(mktemp "${TMPDIR:-/tmp}/charsooq-release.XXXXXX")"
    chmod 600 "$github_header_file"
    printf 'Authorization: Bearer %s\n' "$GITHUB_TOKEN" > "$github_header_file"
    options+=("-H" "@$github_header_file")
  fi
  curl "${options[@]}" "$url" || fail "cannot fetch the GitHub release from $url"
  rm -f "$github_header_file"
  github_header_file=""
}

resolve_digest() {
  local ref="$1" digest
  digest="$(docker buildx imagetools inspect "$ref" --format '{{.Manifest.Digest}}' 2>/dev/null)" ||
    fail "cannot resolve a digest for $ref"
  case "$digest" in
    sha256:*) printf '%s@%s\n' "${ref%:*}" "$digest" ;;
    *) fail "cannot resolve a digest for $ref" ;;
  esac
}

# Read an OCI label from an image we are about to deploy.
image_label() {
  local ref="$1" label="$2" json
  json="$(docker buildx imagetools inspect "$ref" --format '{{json .Image}}' 2>/dev/null)" ||
    return 1
  printf '%s' "$json" | jq -r --arg k "$label" \
    '.. | objects | .Labels? | select(. != null) | .[$k]? // empty' | head -n 1
}

step "Resolving the release to immutable image digests"

release_tag=""
release_commit=""
version=""
if [ $# -eq 2 ]; then
  case "$1" in
    *@sha256:*) ;;
    *) usage ;;
  esac
  case "$2" in
    *@sha256:*) ;;
    *) usage ;;
  esac
  CHAHARSOQ_API_IMAGE="$1"
  CHAHARSOQ_WEB_IMAGE="$2"
  note "using explicit digests; GitHub release discovery skipped"
else
  release="${1:-latest}"
  case "$release" in
    latest|v[0-9]*.[0-9]*.[0-9]*) ;;
    *) usage ;;
  esac

  # Hosts without GitHub access (or without the discovery variables) may pin
  # the two release digests directly in the env file. This keeps `make
  # prod-deploy` a single command: the env file is the sole source of the
  # deployment identity either way. Both refs must be digest-pinned.
  if [ -z "${CHARSOOQ_GITHUB_REPO:-}" ] &&
    { [ -n "${CHAHARSOQ_API_IMAGE:-}" ] || [ -n "${CHAHARSOQ_WEB_IMAGE:-}" ]; }; then
    case "${CHAHARSOQ_API_IMAGE:-}" in
      *@sha256:*) ;;
      *) fail "CHAHARSOQ_API_IMAGE in $ENV_FILE must be a repo@sha256:<digest> reference" ;;
    esac
    case "${CHAHARSOQ_WEB_IMAGE:-}" in
      *@sha256:*) ;;
      *) fail "CHAHARSOQ_WEB_IMAGE in $ENV_FILE must be a repo@sha256:<digest> reference" ;;
    esac
    note "using digest-pinned image references from $ENV_FILE; GitHub release discovery skipped"
  elif [ -z "${CHARSOOQ_GITHUB_REPO:-}" ]; then
    fail "CHARSOOQ_GITHUB_REPO is not set in $ENV_FILE. Set it for release discovery, or pin CHAHARSOQ_API_IMAGE and CHAHARSOQ_WEB_IMAGE to digest references in $ENV_FILE."
  else

  if [ "$release" = "latest" ]; then
    note "fetching the newest published release of $CHARSOOQ_GITHUB_REPO"
    release_json="$(fetch_release 'releases/latest')"
  else
    note "fetching release $release of $CHARSOOQ_GITHUB_REPO"
    release_json="$(fetch_release "releases/tags/$release")"
  fi

  release_tag="$(printf '%s' "$release_json" | jq -er '.tag_name // empty')" ||
    fail "the GitHub response has no release tag"
  [[ "$release_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
    fail "unexpected release tag '$release_tag'; expected vMAJOR.MINOR.PATCH"
  [ "$(printf '%s' "$release_json" | jq -r '.draft // false')" = "false" ] ||
    fail "release $release_tag is still a draft"
  [ "$(printf '%s' "$release_json" | jq -r '.prerelease // false')" = "false" ] ||
    fail "release $release_tag is a prerelease"

  # The release workflow passes --target <commit>, so this is normally a full
  # SHA. A release created with a branch target is still deployable, but its
  # commit cannot be cross-checked against the image label.
  release_commit="$(printf '%s' "$release_json" | jq -r '.target_commitish // empty')"
  [[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || release_commit=""
  version="${release_tag#v}"

  # Version tags are write-once; `latest` is never used as a deployment ref.
  [ -n "${CHAHARSOQ_API_REPO:-}" ] || fail "CHAHARSOQ_API_REPO is not set in $ENV_FILE"
  [ -n "${CHAHARSOQ_WEB_REPO:-}" ] || fail "CHAHARSOQ_WEB_REPO is not set in $ENV_FILE"
  CHAHARSOQ_API_IMAGE="$(resolve_digest "${CHAHARSOQ_API_REPO:-}:$version")"
  CHAHARSOQ_WEB_IMAGE="$(resolve_digest "${CHAHARSOQ_WEB_REPO:-}:$version")"
  fi
fi
note "api image   $CHAHARSOQ_API_IMAGE"
note "web image   $CHAHARSOQ_WEB_IMAGE"
export CHAHARSOQ_API_IMAGE CHAHARSOQ_WEB_IMAGE

step "Verifying that both images are from one release"
api_version="$(image_label "$CHAHARSOQ_API_IMAGE" org.opencontainers.image.version || true)"
web_version="$(image_label "$CHAHARSOQ_WEB_IMAGE" org.opencontainers.image.version || true)"
api_revision="$(image_label "$CHAHARSOQ_API_IMAGE" org.opencontainers.image.revision || true)"
web_revision="$(image_label "$CHAHARSOQ_WEB_IMAGE" org.opencontainers.image.revision || true)"
[ -n "$api_version" ] && [ "$api_version" = "$web_version" ] ||
  fail "images report different versions ('$api_version' vs '$web_version'); retry after the release finishes"
[ -n "$api_revision" ] && [ "$api_revision" = "$web_revision" ] ||
  fail "images report different commits ('$api_revision' vs '$web_revision'); retry after the release finishes"
if [ -n "$version" ]; then
  [ "$api_version" = "$version" ] ||
    fail "image version '$api_version' does not match GitHub release $release_tag"
  if [ -n "$release_commit" ]; then
    [ "$api_revision" = "$release_commit" ] ||
      fail "image commit '$api_revision' does not match release commit '$release_commit'"
  fi
fi
note "version $api_version, commit $api_revision"

# ─── DEPLOY ──────────────────────────────────────────────────────────────────

step "Validating the production Compose file"
"${COMPOSE[@]}" config --quiet || fail "compose configuration is invalid"

step "Pulling the released images"
"${COMPOSE[@]}" pull api web

step "Provisioning database roles"
"${COMPOSE[@]}" run --rm provision

step "Checking database migrations"
migration_check_failed=0
migration_output="$("${COMPOSE[@]}" run --rm migrate \
  python backend/api/scripts/migrate.py --check 2>&1)" || migration_check_failed=1
while IFS= read -r line; do
  if [ -n "$line" ]; then
    note "$line"
  fi
done <<< "$migration_output"
case "$migration_output" in
  *"usage: migrate.py"*)
    # A rollback may deploy an image from before --check existed. Its runner
    # still applies all pending migrations under the advisory lock, so use it
    # directly instead of refusing to roll back.
    note "image has no --check support; running the migration runner directly"
    "${COMPOSE[@]}" run --rm migrate
    migration_state="checked by runner"
    ;;
  *"migrate: migrations pending"*)
    note "applying pending migrations before the API starts"
    "${COMPOSE[@]}" run --rm migrate
    migration_state="applied"
    ;;
  *"migrate: database already at head"*)
    skip "database already at head"
    migration_state="already at head"
    ;;
  *)
    [ "$migration_check_failed" -eq 0 ] || fail "migration check failed; no service was started"
    fail "unexpected migration check output; refusing to start the API"
    ;;
esac

step "Starting api and web"

# Re-check the on-disk major immediately before starting services. The first
# check happened before release discovery and image pulls; a half-finished
# cutover in that window must not end with an empty database behind a healthy
# API (TOCTOU).
cluster_major_before_start="$("${COMPOSE[@]}" run --rm --no-deps --entrypoint sh db -c \
  "test -f '/var/lib/postgresql/$image_major/docker/PG_VERSION' && \
   cat '/var/lib/postgresql/$image_major/docker/PG_VERSION' || true" 2>/dev/null)" ||
  fail "cannot re-read the database cluster version before starting services"
[ "$cluster_major_before_start" = "$image_major" ] ||
  fail "database cluster changed to '$cluster_major_before_start' during the deploy; refusing to start services"

previous_version=""
api_container_id="$("${COMPOSE[@]}" ps -q api 2>/dev/null || true)"
api_container_id="${api_container_id%%$'\n'*}"
if [ -n "$api_container_id" ]; then
  previous_version="$(docker inspect \
    --format '{{index .Config.Labels "org.opencontainers.image.version"}}' \
    "$api_container_id" 2>/dev/null || true)"
  case "$previous_version" in
    ""|"<no value>") previous_version="" ;;
  esac
fi
"${COMPOSE[@]}" up -d --no-build --remove-orphans

# The upstream host is resolved by Caddy; a graceful reload refreshes that DNS
# after the web container was replaced (admin API is off, so SIGUSR1 is used).
caddy_id="$("${COMPOSE[@]}" ps -q caddy 2>/dev/null || true)"
caddy_id="${caddy_id%%$'\n'*}"
[ -n "$caddy_id" ] || fail "caddy container not found"
docker kill --signal=USR1 "$caddy_id" >/dev/null

# ─── VERIFICATION / SUMMARY ──────────────────────────────────────────────────

probe() {
  local base="${CHARSOOQ_PUBLIC_SCHEME}://${CHARSOOQ_SITE_HOST}" options=(-fsS --connect-timeout 5 --max-time 10)
  if [ "$CHARSOOQ_PUBLIC_SCHEME" = "https" ] && [ -n "${CHARSOOQ_CA_FILE:-}" ]; then
    options+=(--cacert "$CHARSOOQ_CA_FILE")
  fi
  curl "${options[@]}" "${base}$1" >/dev/null
}

container_state() {
  local service="$1" id state
  id="$("${COMPOSE[@]}" ps -q "$service" 2>/dev/null || true)"
  id="${id%%$'\n'*}"
  [ -n "$id" ] || { printf 'missing\n'; return 0; }
  state="$(docker inspect \
    --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    "$id" 2>/dev/null || true)"
  printf '%s\n' "${state:-unknown}"
}

healthy_state() {
  local service="$1" state="$2"
  # db, api and web all define healthchecks in compose; `running` is not enough.
  if [ "$service" = "caddy" ]; then
    [ "$state" = "running" ]
  else
    [ "$state" = "healthy" ]
  fi
}

step "Verifying service and endpoint health"
SERVICES=(db api web caddy)
PROBES=(/api/v1/health /api/v1/ready /login)
states=()
verified=0
for attempt in {1..45}; do
  states=()
  all_running=1
  for service in "${SERVICES[@]}"; do
    state="$(container_state "$service")"
    states+=("$state")
    healthy_state "$service" "$state" || all_running=0
  done
  endpoints_ok=1
  for endpoint in "${PROBES[@]}"; do
    probe "$endpoint" || endpoints_ok=0
  done
  if [ "$all_running" -eq 1 ] && [ "$endpoints_ok" -eq 1 ]; then
    verified=1
    break
  fi
  note "waiting for services (attempt $attempt/45)"
  sleep 2
done
[ "$verified" -eq 1 ] || {
  service_report=""
  for index in "${!SERVICES[@]}"; do
    service_report+="${SERVICES[index]}=${states[index]} "
  done
  fail "health verification failed ($service_report); check logs with: make prod-logs"
}

service_report=""
for index in "${!SERVICES[@]}"; do
  service_report+="${SERVICES[index]}=${states[index]} "
done
probe_report=""
for endpoint in "${PROBES[@]}"; do
  probe_report+="$endpoint ok  "
done
release_display="${release_tag:-$api_version}"
# Image labels may already carry the `v` prefix (local prod-build), so strip it
# before constructing the previous release tag.
rollback_to="${previous_version:+v${previous_version#v}}"
[ -n "$rollback_to" ] && [ "$rollback_to" != "$release_display" ] ||
  rollback_to="<previous-version>"
elapsed=$((SECONDS - START_SECONDS))

printf '\n[deploy] ── Deployment summary ──────────────────────────────────\n'
printf '[deploy]   %-11s %s\n' "Status" "deployed"
printf '[deploy]   %-11s %s\n' "Release" "$release_display ($api_revision)"
printf '[deploy]   %-11s %s\n' "Host" "${CHARSOOQ_PUBLIC_SCHEME}://${CHARSOOQ_SITE_HOST}"
printf '[deploy]   %-11s %s\n' "Database" "$migration_state"
printf '[deploy]   %-11s %s\n' "Services" "$service_report"
printf '[deploy]   %-11s %s\n' "Probes" "$probe_report"
printf '[deploy]   %-11s %s\n' "Duration" "${elapsed}s"
printf '[deploy]   %-11s %s\n' "Rollback" "./deploy/scripts/deploy.sh $rollback_to"
printf '\n[deploy] All services are up and every health probe passed on %s.\n' "$CHARSOOQ_SITE_HOST"
# A code-only rollback is not enough after a major-version cutover: the 19
# cluster cannot be served by the old image (ADR 028, rollback section).
printf '[deploy] If this release included the 18 -> 19 data cutover, a code-only rollback is NOT sufficient; see ADR 028 section 4 and keep the 18 datadir at rollback/18.\n'
log "deployment complete ($api_version)"
