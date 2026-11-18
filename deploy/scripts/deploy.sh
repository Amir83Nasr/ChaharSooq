#!/usr/bin/env bash
# Single-slot Production deploy entry point, run on the server after a release.
#
# Usage (from /opt/charsooq on the server):
#   ./deploy/scripts/deploy.sh                 # deploy the newest release
#   ./deploy/scripts/deploy.sh v1.2.3          # deploy a specific release
#   ./deploy/scripts/deploy.sh <api@sha256:..> <web@sha256:..>   # explicit digests
#
# With no argument the `latest` discovery pointer is resolved to two immutable
# digests before anything changes. Both images must report the same version and
# commit label, so a half-published release can never be deployed mixed. Nothing
# is removed; rollback is the same command with the previous version tag.
set -euo pipefail

COMPOSE_FILE="${CHARSOOQ_COMPOSE_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/compose.production.yml}"
ENV_FILE="${CHARSOOQ_ENV_FILE:-/etc/charsooq/production.env}"

log() { printf '[deploy] %s\n' "$*"; }
fail() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  printf 'usage: %s [version-tag | <api-ref@sha256:...> <web-ref@sha256:...>]\n' "$0" >&2
  exit 2
}

[ $# -le 2 ] || usage

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
command -v curl >/dev/null 2>&1 || fail "curl is required for the health probe"

resolve_digest() {
  local ref="$1" digest
  digest="$(docker buildx imagetools inspect "$ref" --format '{{.Manifest.Digest}}' 2>/dev/null)" ||
    fail "cannot resolve a digest for $ref"
  case "$digest" in
    sha256:*) printf '%s@%s\n' "${ref%%:*}" "$digest" ;;
    *) fail "cannot resolve a digest for $ref" ;;
  esac
}

# Read an OCI label from an image we are about to deploy. `latest` is only a
# name: the labels tie the resolved bytes back to one release and one commit.
image_label() {
  local ref="$1" label="$2" json
  json="$(docker buildx imagetools inspect "$ref" --format '{{json .Image}}' 2>/dev/null)" ||
    return 1
  printf '%s' "$json" | grep -o "\"${label}\":\"[^\"]*\"" | head -n 1 |
    sed -E 's/.*:"([^"]*)"/\1/'
}

if [ $# -eq 2 ]; then
  case "$1" in
    *@sha256:*) ;;
    *) usage ;;
  esac
  case "$2" in
    *@sha256:*) ;;
    *) usage ;;
  esac
  CHARSOOQ_API_IMAGE="$1"
  CHARSOOQ_WEB_IMAGE="$2"
else
  # No argument means the newest published release. Both forms resolve to
  # digests; a tag is never the deployment reference.
  release="${1:-latest}"
  [ -n "${CHARSOOQ_API_REPO:-}" ] || fail "CHARSOOQ_API_REPO is not set in $ENV_FILE"
  [ -n "${CHARSOOQ_WEB_REPO:-}" ] || fail "CHARSOOQ_WEB_REPO is not set in $ENV_FILE"
  case "$release" in
    *@sha256:*)
      fail "pass both image digests explicitly, or pass a version tag"
      ;;
  esac
  log "resolving '$release' to image digests"
  CHARSOOQ_API_IMAGE="$(resolve_digest "${CHARSOOQ_API_REPO}:$release")"
  CHARSOOQ_WEB_IMAGE="$(resolve_digest "${CHARSOOQ_WEB_REPO}:$release")"
fi
export CHARSOOQ_API_IMAGE CHARSOOQ_WEB_IMAGE

# Fail closed on a mixed pair: both images must come from the same release.
api_version="$(image_label "$CHARSOOQ_API_IMAGE" org.opencontainers.image.version || true)"
web_version="$(image_label "$CHARSOOQ_WEB_IMAGE" org.opencontainers.image.version || true)"
api_revision="$(image_label "$CHARSOOQ_API_IMAGE" org.opencontainers.image.revision || true)"
web_revision="$(image_label "$CHARSOOQ_WEB_IMAGE" org.opencontainers.image.revision || true)"
[ -n "$api_version" ] && [ "$api_version" = "$web_version" ] ||
  fail "images report different versions ('$api_version' vs '$web_version'); retry after the release finishes"
[ -n "$api_revision" ] && [ "$api_revision" = "$web_revision" ] ||
  fail "images report different commits ('$api_revision' vs '$web_revision'); retry after the release finishes"
log "release $api_version ($api_revision)"

# Interpolate the whole Compose file with real host values before changing state.
COMPOSE=(docker compose -f "$COMPOSE_FILE")
"${COMPOSE[@]}" config --quiet || fail "compose configuration is invalid"

log "api image   $CHARSOOQ_API_IMAGE"
log "web image   $CHARSOOQ_WEB_IMAGE"

log "pulling released images"
"${COMPOSE[@]}" pull api web

log "provisioning database roles"
"${COMPOSE[@]}" run --rm provision

log "applying migrations before the API starts"
"${COMPOSE[@]}" run --rm migrate

log "starting api and web"
"${COMPOSE[@]}" up -d --no-build --remove-orphans

# The upstream host is resolved by Caddy; a graceful reload refreshes that DNS
# after the web container was replaced (admin API is off, so SIGUSR1 is used).
caddy_id="$("${COMPOSE[@]}" ps -q caddy | head -n 1)"
[ -n "$caddy_id" ] || fail "caddy container not found"
docker kill --signal=USR1 "$caddy_id" >/dev/null

probe() {
  local base="${CHARSOOQ_PUBLIC_SCHEME}://${CHARSOOQ_SITE_HOST}"
  if [ "$CHARSOOQ_PUBLIC_SCHEME" = "https" ] && [ -n "${CHARSOOQ_CA_FILE:-}" ]; then
    curl -fsS --cacert "$CHARSOOQ_CA_FILE" "${base}$1" >/dev/null
  else
    curl -fsS "${base}$1" >/dev/null
  fi
}

log "verifying external health"
verified=0
for _ in {1..30}; do
  if probe /api/v1/health && probe /login; then
    verified=1
    break
  fi
  sleep 2
done
[ "$verified" -eq 1 ] || fail "health probe failed; check logs with: make prod-logs"

log "deployment complete ($api_version). Rollback: deploy.sh <previous-version>"
