#!/usr/bin/env bash
# Outbound-only auto-deploy agent: poll the published GitHub Release and deploy
# a new version through the existing deploy.sh. No inbound access, no runner,
# no new deployment logic on the host (ADR 033).
#
# Designed to run under the charsooq-release-watch systemd timer every 5 minutes.
# It is safe to run manually at any time. A lock prevents overlapping deploys.
set -euo pipefail

log() { printf '[watch] %s\n' "$*"; }
fail() { printf '[watch] ERROR: %s\n' "$*" >&2; exit 1; }

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${CHARSOOQ_ENV_FILE:-/etc/charsooq/production.env}"
STATE_FILE="${CHARSOOQ_WATCH_STATE_FILE:-/var/lib/charsooq/last-deployed-release}"
LOCK_FILE="${CHARSOOQ_WATCH_LOCK_FILE:-/run/charsooq-release-watch.lock}"
REPO="${CHARSOOQ_RELEASE_REPO:-Amir83Nasr/ChaharSooq}"
DEPLOY_SCRIPT="${CHARSOOQ_WATCH_DEPLOY_SCRIPT:-$repo_root/deploy/scripts/deploy.sh}"

[ -f "$ENV_FILE" ] || fail "env file not found: $ENV_FILE"
# shellcheck disable=SC1090
set -a
. "$ENV_FILE"
set +a
[ -f "$DEPLOY_SCRIPT" ] || fail "deploy script not found: $DEPLOY_SCRIPT"
command -v docker >/dev/null 2>&1 || fail "docker is required"
command -v curl >/dev/null 2>&1 || fail "curl is required to read the GitHub Release"
command -v jq >/dev/null 2>&1 || fail "jq is required to read the GitHub Release"
command -v flock >/dev/null 2>&1 || fail "flock is required to serialize deploys"

for name in CHARSOOQ_PROXY_BIND_IP CHARSOOQ_SITE_HOST CHARSOOQ_EDGE_SUBNET \
  CHARSOOQ_WEB_EDGE_IP CHARSOOQ_PUBLIC_SCHEME; do
  [ -n "${!name:-}" ] || fail "$name is not set in $ENV_FILE"
done

mkdir -p "$(dirname "$LOCK_FILE")" "$(dirname "$STATE_FILE")"

exec 9>"$LOCK_FILE"
flock -n 9 || { log "another deploy is still running; skipping this tick"; exit 0; }

read_release() {
  local endpoint="$1" url json
  url="https://api.github.com/repos/${REPO}/${endpoint}"
  local -a options=(
    -fsS --retry 2 --retry-delay 1 --connect-timeout 5 --max-time 20
    -H 'Accept: application/vnd.github+json'
    -H 'X-GitHub-Api-Version: 2022-11-28'
  )
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    local header_file
    header_file="$(mktemp "${TMPDIR:-/tmp}/charsooq-watch.XXXXXX")"
    chmod 600 "$header_file"
    printf 'Authorization: Bearer %s\n' "$GITHUB_TOKEN" > "$header_file"
    options+=("-H" "@$header_file")
    json="$(curl "${options[@]}" "$url")" || { rm -f "$header_file"; return 1; }
    rm -f "$header_file"
    printf '%s' "$json"
    return 0
  fi
  curl "${options[@]}" "$url"
}

log "checking the newest published release of $REPO"
release_json="$(read_release 'releases/latest')" ||
  fail "cannot read the GitHub release; will retry on the next tick"

[ "$(printf '%s' "$release_json" | jq -r '.draft // false')" = "false" ] ||
  { log "newest release is a draft; skipping"; exit 0; }
[ "$(printf '%s' "$release_json" | jq -r '.prerelease // false')" = "false" ] ||
  { log "newest release is a prerelease; skipping"; exit 0; }

release_tag="$(printf '%s' "$release_json" | jq -er '.tag_name // empty')" ||
  fail "the GitHub response has no release tag"
[[ "$release_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  fail "unexpected release tag '$release_tag'; expected vMAJOR.MINOR.PATCH"

last_tag=""
[ -f "$STATE_FILE" ] && last_tag="$(tr -d '[:space:]' < "$STATE_FILE")"
if [ "$release_tag" = "$last_tag" ]; then
  log "release $release_tag is already deployed; nothing to do"
  exit 0
fi
log "new release $release_tag found (last deployed: ${last_tag:-none})"

# deploy.sh re-fetches the same release to extract the verified digests and
# runs all health gates; on any failure it exits non-zero and the state file
# is left untouched, so the next tick retries.
log "calling deploy.sh for $release_tag"
if "$DEPLOY_SCRIPT" "$release_tag"; then
  printf '%s\n' "$release_tag" > "$STATE_FILE"
  chmod 0600 "$STATE_FILE"
  log "deployed $release_tag and recorded it in $STATE_FILE"
else
  fail "deploy of $release_tag failed; state file was not updated, will retry"
fi
