#!/usr/bin/env bash
# Production Blue-Green deployment entry point, run by the self-hosted runner
# after the release workflow published both images.
#
# It never reads or prints a secret value. The six Production secret files stay
# on the host under CHARSOOQ_SECRETS_DIR and are read by Compose; this script
# only reads the non-secret deployment values from CHARSOOQ_ENV_FILE (or the
# environment) and the release identity from the workflow.
#
# The deploy is fail-closed and traffic-gated:
#   1. deploy by digest only and verify the published revision label;
#   2. detect the active slot, choose the inactive slot;
#   3. provision roles and apply migrations once (shared database) before the
#      new slot starts;
#   4. start the inactive slot (api, then web) and verify real health/smoke
#      checks against it while the active slot keeps serving;
#   5. switch Caddy to the inactive slot with a graceful reload and verify
#      external health;
#   6. persist the active slot and both image sets; keep the previous slot
#      running for rollback;
#   7. on failure before the switch, leave the previous slot active.
#
# No volume, database, or image is removed. `docker compose down -v` and every
# prune command are deliberately absent.
set -euo pipefail

COMPOSE_FILE="${CHARSOOQ_COMPOSE_FILE:-${GITHUB_WORKSPACE:-$PWD}/compose.production.yml}"
ENV_FILE="${CHARSOOQ_ENV_FILE:-/etc/charsooq/production.env}"
STATE_DIR="${CHARSOOQ_STATE_DIR:-/etc/charsooq/state}"
STATE_FILE="${CHARSOOQ_STATE_FILE:-$STATE_DIR/deploy-state.env}"
ACTIVE_UPSTREAM_FILE="${CHARSOOQ_ACTIVE_UPSTREAM_FILE:-${GITHUB_WORKSPACE:-$PWD}/deploy/caddy/active-upstream.caddy}"

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

write_upstream() {
  local slot="$1" tmp
  tmp="$(mktemp "${ACTIVE_UPSTREAM_FILE}.XXXXXX")"
  cat >"$tmp" <<EOF
# Active Blue-Green upstream, rewritten atomically by deploy/scripts/deploy.sh.
# Do not edit by hand during a deployment. The proxy forwards to exactly one
# slot; the inactive slot is never referenced here.
reverse_proxy web-${slot}:3000 {
	# Never forward client-supplied forwarding values. Caddy already ignores
	# incoming X-Forwarded-* by default (no trusted_proxies is configured), and
	# these lines make the rewrite explicit. They also drop the RFC 7239
	# \`Forwarded\` header and other IP hints that Caddy would otherwise pass
	# through untouched, so Next.js and FastAPI only ever see Caddy's values.
	# Caddy warns that the X-Forwarded-* sets duplicate its defaults; they stay
	# because a future global \`trusted_proxies\` would otherwise change behaviour
	# to "augment the client's header" without any visible config change here.
	header_up X-Forwarded-For {remote_host}
	header_up X-Forwarded-Proto {scheme}
	header_up X-Forwarded-Host {host}
	# The published external port for the configured public protocol.
	header_up X-Forwarded-Port ${CHARSOOQ_PUBLIC_PORT}
	header_up -Forwarded
	header_up -X-Real-IP
	header_up -X-Forwarded-Server
}
EOF
  mv "$tmp" "$ACTIVE_UPSTREAM_FILE"
}

detect_active_slot() {
  if [ -f "$STATE_FILE" ]; then
    # shellcheck disable=SC1090
    . "$STATE_FILE"
    case "${ACTIVE_SLOT:-}" in
      blue | green)
        printf '%s' "$ACTIVE_SLOT"
        return 0
        ;;
    esac
  fi
  if [ -f "$ACTIVE_UPSTREAM_FILE" ]; then
    if grep -q 'web-green:3000' "$ACTIVE_UPSTREAM_FILE"; then
      printf 'green'
      return 0
    fi
    if grep -q 'web-blue:3000' "$ACTIVE_UPSTREAM_FILE"; then
      printf 'blue'
      return 0
    fi
  fi
  printf 'none'
}

# The workflow-provided release identity must win over any value left in the
# host environment file by an earlier manual deployment.
release_api_image="${CHARSOOQ_API_IMAGE:-}"
release_web_image="${CHARSOOQ_WEB_IMAGE:-}"
release_tag="${CHARSOOQ_RELEASE_TAG:-}"
release_version="${CHARSOOQ_RELEASE_VERSION:-}"
release_sha="${CHARSOOQ_RELEASE_SHA:-}"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a
  . "$ENV_FILE"
  set +a
fi

CHARSOOQ_API_IMAGE="$release_api_image"
CHARSOOQ_WEB_IMAGE="$release_web_image"
CHARSOOQ_RELEASE_TAG="$release_tag"
CHARSOOQ_RELEASE_VERSION="$release_version"
CHARSOOQ_RELEASE_SHA="$release_sha"

# Backward compatibility: older env files used the single-edge names.
: "${CHARSOOQ_EDGE_BLUE_SUBNET:=${CHARSOOQ_EDGE_SUBNET:-}}"
: "${CHARSOOQ_WEB_BLUE_EDGE_IP:=${CHARSOOQ_WEB_EDGE_IP:-}}"
export CHARSOOQ_EDGE_BLUE_SUBNET CHARSOOQ_WEB_BLUE_EDGE_IP

[ -f "$COMPOSE_FILE" ] || fail "compose file not found: $COMPOSE_FILE"
[ -n "$CHARSOOQ_API_IMAGE" ] || fail "CHARSOOQ_API_IMAGE is not set"
[ -n "$CHARSOOQ_WEB_IMAGE" ] || fail "CHARSOOQ_WEB_IMAGE is not set"
[ -n "$CHARSOOQ_RELEASE_SHA" ] || fail "CHARSOOQ_RELEASE_SHA is not set"
: "${CHARSOOQ_PROXY_BIND_IP:?set CHARSOOQ_PROXY_BIND_IP to the approved internal IP}"
: "${CHARSOOQ_SITE_HOST:?set CHARSOOQ_SITE_HOST to the approved DNS name or IP}"
: "${CHARSOOQ_EDGE_BLUE_SUBNET:?set CHARSOOQ_EDGE_BLUE_SUBNET (or legacy CHARSOOQ_EDGE_SUBNET) to an approved CIDR}"
: "${CHARSOOQ_WEB_BLUE_EDGE_IP:?set CHARSOOQ_WEB_BLUE_EDGE_IP (or legacy CHARSOOQ_WEB_EDGE_IP) to the blue web address}"
: "${CHARSOOQ_EDGE_GREEN_SUBNET:?set CHARSOOQ_EDGE_GREEN_SUBNET to an approved CIDR for the green slot}"
: "${CHARSOOQ_WEB_GREEN_EDGE_IP:?set CHARSOOQ_WEB_GREEN_EDGE_IP to the green web address}"

# Public protocol/port are configuration-driven. Current Production is HTTP-only
# until HTTPS is ready; do not guess values. HTTPS requires a CA file for the
# external probe; HTTP-only does not require TLS material.
: "${CHARSOOQ_PUBLIC_SCHEME:=https}"
: "${CHARSOOQ_PUBLIC_PORT:=}"
case "$CHARSOOQ_PUBLIC_SCHEME" in
  http)
    : "${CHARSOOQ_PUBLIC_PORT:=80}"
    ;;
  https)
    : "${CHARSOOQ_PUBLIC_PORT:=443}"
    ;;
  *)
    fail "CHARSOOQ_PUBLIC_SCHEME must be 'http' or 'https' (set in configuration)"
    ;;
esac
export CHARSOOQ_PUBLIC_SCHEME CHARSOOQ_PUBLIC_PORT
if [ "$CHARSOOQ_PUBLIC_SCHEME" = "https" ] && [ -z "${CHARSOOQ_CA_FILE:-}" ]; then
  fail "CHARSOOQ_CA_FILE must be set for HTTPS external verification (or switch to HTTP-only only if approved and configured)"
fi

# All required variables and paths must be validated before any state change
# (no compose up/run, no upstream rewrite, no reload, no state write).
[ -f "$ACTIVE_UPSTREAM_FILE" ] || fail "active upstream file not found: $ACTIVE_UPSTREAM_FILE"
[ -w "$ACTIVE_UPSTREAM_FILE" ] || fail "active upstream file is not writable: $ACTIVE_UPSTREAM_FILE (required for traffic switch)"
if [ -e "$STATE_DIR" ]; then
  [ -d "$STATE_DIR" ] || fail "state path is not a directory: $STATE_DIR"
  [ -w "$STATE_DIR" ] || fail "state directory is not writable: $STATE_DIR"
else
  state_parent="$(dirname "$STATE_DIR")"
  [ -d "$state_parent" ] && [ -w "$state_parent" ] || fail "state directory cannot be created (parent not writable): $STATE_DIR"
fi
if [ -e "$STATE_FILE" ]; then
  [ -w "$STATE_FILE" ] || fail "state file exists but is not writable: $STATE_FILE"
fi
command -v curl >/dev/null 2>&1 || fail "curl is required for external health verification"

# A tag is a moving name. Production only ever deploys a content address.
case "$CHARSOOQ_API_IMAGE" in
  *@sha256:*) ;;
  *) fail "CHARSOOQ_API_IMAGE must be repository@sha256:<digest>" ;;
esac
case "$CHARSOOQ_WEB_IMAGE" in
  *@sha256:*) ;;
  *) fail "CHARSOOQ_WEB_IMAGE must be repository@sha256:<digest>" ;;
esac
[ "$CHARSOOQ_API_IMAGE" != "$CHARSOOQ_WEB_IMAGE" ] ||
  fail "the API and web image references must differ"

active_slot="$(detect_active_slot)"
case "$active_slot" in
  blue)
    target_slot="green"
    previous_api="${ACTIVE_API:-}"
    previous_web="${ACTIVE_WEB:-}"
    ;;
  green)
    target_slot="blue"
    previous_api="${ACTIVE_API:-}"
    previous_web="${ACTIVE_WEB:-}"
    ;;
  none)
    target_slot="blue"
    previous_api=""
    previous_web=""
    ;;
  *)
    fail "cannot determine the active slot"
    ;;
esac

COMPOSE=(docker compose -f "$COMPOSE_FILE")
COMPOSE_TARGET=("${COMPOSE[@]}" --profile "$target_slot")

log "release ${CHARSOOQ_RELEASE_TAG:-unknown} (${CHARSOOQ_RELEASE_VERSION:-unknown}) commit ${CHARSOOQ_RELEASE_SHA}"
log "api image   $CHARSOOQ_API_IMAGE"
log "web image   $CHARSOOQ_WEB_IMAGE"
log "active slot ${active_slot} -> target slot ${target_slot}"

# Interpolates the Compose file with the real host values for the target slot.
# It does not read secret file contents and it fails closed on a missing value.
"${COMPOSE_TARGET[@]}" config --quiet

log "pulling the released images by digest"
"${COMPOSE[@]}" pull "api-${target_slot}" "web-${target_slot}"

verify_revision() {
  local image="$1" revision
  revision="$(
    docker image inspect "$image" \
      --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
  )" || fail "cannot inspect $image"
  [ "$revision" = "$CHARSOOQ_RELEASE_SHA" ] ||
    fail "$image reports revision '${revision}', expected ${CHARSOOQ_RELEASE_SHA}"
}

verify_revision "$CHARSOOQ_API_IMAGE"
verify_revision "$CHARSOOQ_WEB_IMAGE"
log "both image revisions match the release commit"

slot_container() {
  local service="$1"
  "${COMPOSE[@]}" ps -q "$service" 2>/dev/null | head -n 1 || true
}

slot_health() {
  local service="$1" container_id status
  container_id="$(slot_container "$service")"
  [ -n "$container_id" ] || {
    log "ERROR: $service has no container"
    return 1
  }
  status="$(
    docker inspect --format \
      '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "$container_id"
  )"
  case "$status" in
    healthy | running) return 0 ;;
    *)
      log "ERROR: $service is ${status}"
      return 1
      ;;
  esac
}

verify_slot() {
  local slot="$1" api_service="api-${slot}" web_service="web-${slot}"
  slot_health "$api_service" || return 1
  slot_health "$web_service" || return 1
  "${COMPOSE[@]}" exec -T "$api_service" \
    python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready').read()" \
    >/dev/null || {
    log "ERROR: ${api_service} readiness probe failed"
    return 1
  }
  "${COMPOSE[@]}" exec -T "$api_service" \
    python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" \
    >/dev/null || {
    log "ERROR: ${api_service} liveness probe failed"
    return 1
  }
  "${COMPOSE[@]}" exec -T "$web_service" \
    node -e "fetch('http://127.0.0.1:3000/login').then((r)=>{if(r.status>=500)process.exit(1)}).catch(()=>process.exit(1))" \
    >/dev/null || {
    log "ERROR: ${web_service} login probe failed"
    return 1
  }
  # Smoke test the same-origin path the browser uses, through the slot's web.
  "${COMPOSE[@]}" exec -T "$web_service" \
    node -e "fetch('http://127.0.0.1:3000/api/v1/health').then((r)=>{if(r.status>=500)process.exit(1)}).catch(()=>process.exit(1))" \
    >/dev/null || {
    log "ERROR: ${web_service} same-origin API smoke test failed"
    return 1
  }
}

verify_external() {
  local base_url="${CHARSOOQ_PUBLIC_SCHEME}://${CHARSOOQ_SITE_HOST}"
  if [ "$CHARSOOQ_PUBLIC_SCHEME" = "https" ]; then
    [ -n "${CHARSOOQ_CA_FILE:-}" ] || fail "CHARSOOQ_CA_FILE must be set for HTTPS external verification"
    curl -fsS --cacert "$CHARSOOQ_CA_FILE" \
      "${base_url}/api/v1/health" >/dev/null || {
      log "ERROR: the external HTTPS health probe failed"
      return 1
    }
    curl -fsS --cacert "$CHARSOOQ_CA_FILE" \
      "${base_url}/login" >/dev/null || {
      log "ERROR: the external HTTPS login probe failed"
      return 1
    }
  else
    # HTTP-only mode (current temporary Production state): probe over HTTP.
    # Missing TLS material must not skip external verification.
    curl -fsS "${base_url}/api/v1/health" >/dev/null || {
      log "ERROR: the external HTTP health probe failed"
      return 1
    }
    curl -fsS "${base_url}/login" >/dev/null || {
      log "ERROR: the external HTTP login probe failed"
      return 1
    }
  fi
}

ensure_base() {
  log "starting shared infrastructure"
  "${COMPOSE[@]}" up -d --wait --wait-timeout 180 db
  log "provisioning database roles"
  "${COMPOSE[@]}" run --rm provision
  log "applying migrations (must remain compatible with the active slot during overlap)"
  "${COMPOSE[@]}" run --rm migrate
  "${COMPOSE[@]}" up -d caddy
}

reload_caddy() {
  local container_id
  container_id="$(slot_container caddy)"
  [ -n "$container_id" ] || fail "caddy container not found"
  # admin off: `caddy reload` requires the admin API, so use the verified
  # graceful in-process reload signal. A restart would interrupt active
  # connections during the traffic switch.
  docker kill --signal=USR1 "$container_id" >/dev/null
  # Give Caddy a moment to load the new upstream file.
  sleep 2
}

write_state() {
  mkdir -p "$STATE_DIR"
  chmod 700 "$STATE_DIR"
  local tmp
  tmp="$(mktemp "$STATE_FILE.XXXXXX")"
  chmod 600 "$tmp"
  {
    echo "ACTIVE_SLOT=${active_slot}"
    echo "ACTIVE_API=${active_api}"
    echo "ACTIVE_WEB=${active_web}"
    echo "INACTIVE_SLOT=${inactive_slot}"
    echo "INACTIVE_API=${inactive_api}"
    echo "INACTIVE_WEB=${inactive_web}"
    echo "RELEASE_TAG=${CHARSOOQ_RELEASE_TAG:-}"
    echo "RELEASE_VERSION=${CHARSOOQ_RELEASE_VERSION:-}"
    echo "RELEASE_SHA=${CHARSOOQ_RELEASE_SHA}"
    echo "DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >"$tmp"
  mv "$tmp" "$STATE_FILE"
}

active_api=""
active_web=""
inactive_slot=""
inactive_api=""
inactive_web=""

ensure_base

log "starting inactive slot ${target_slot}"
"${COMPOSE_TARGET[@]}" up -d --no-build --no-deps --wait --wait-timeout 180 "api-${target_slot}" ||
  fail "failed to start api-${target_slot}; the active slot was not changed"
"${COMPOSE_TARGET[@]}" up -d --no-build --no-deps --wait --wait-timeout 180 "web-${target_slot}" ||
  fail "failed to start web-${target_slot}; the active slot was not changed"

log "verifying inactive slot ${target_slot} before switching traffic"
if ! verify_slot "$target_slot"; then
  fail "slot ${target_slot} failed verification; the active slot was not changed"
fi

log "switching traffic to slot ${target_slot}"
# Persist the new upstream selection on disk before reload so a host restart
# recovers the intended active slot.
write_upstream "$target_slot"
reload_caddy

if ! verify_external; then
  log "post-switch verification failed; switching traffic back to slot ${active_slot}"
  if [ "$active_slot" = "blue" ] || [ "$active_slot" = "green" ]; then
    write_upstream "$active_slot"
    reload_caddy || true
    if verify_external; then
      fail "slot ${target_slot} did not pass post-switch verification; traffic was returned to ${active_slot}"
    fi
  fi
  fail "slot ${target_slot} did not pass post-switch verification and traffic could not be restored automatically; manual intervention is required"
fi

active_slot="$target_slot"
active_api="$CHARSOOQ_API_IMAGE"
active_web="$CHARSOOQ_WEB_IMAGE"
if [ "$target_slot" = "blue" ]; then
  inactive_slot="green"
else
  inactive_slot="blue"
fi
inactive_api="$previous_api"
inactive_web="$previous_web"

if ! write_state; then
  log "WARNING: the deployment succeeded but the state file could not be written"
fi

log "deployment complete: active slot ${active_slot}; previous slot ${inactive_slot} kept for rollback"
