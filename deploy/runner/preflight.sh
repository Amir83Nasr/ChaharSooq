#!/usr/bin/env bash
# Read-only preflight checks for preparing a ChaharSooq Production self-hosted
# runner host. It does NOT install or register a runner, does NOT change system
# state, and does NOT read or print secret values.
#
# Usage:
#   bash deploy/runner/preflight.sh
#   bash deploy/runner/preflight.sh /path/to/runner.env
#
# The optional env file is sourced only to read non-secret path/label hints;
# registration tokens and secrets must never be placed in it.
set -euo pipefail

ENV_FILE="${1:-}"
if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a
  . "$ENV_FILE"
  set +a
fi

RUNNER_DIR="${CHARSOOQ_RUNNER_DIR:-/opt/actions-runner-charsooq}"
RUNNER_USER="${CHARSOOQ_RUNNER_USER:-charsooq-runner}"
COMPOSE_FILE="${CHARSOOQ_COMPOSE_FILE:-/opt/charsooq/compose.production.yml}"
PROD_ENV_FILE="${CHARSOOQ_ENV_FILE:-/etc/charsooq/production.env}"
STATE_DIR="${CHARSOOQ_STATE_DIR:-/etc/charsooq/state}"
SECRETS_DIR="${CHARSOOQ_SECRETS_DIR:-/etc/charsooq/secrets}"
UPSTREAM_FILE="${CHARSOOQ_ACTIVE_UPSTREAM_FILE:-/opt/charsooq/deploy/caddy/active-upstream.caddy}"

# Blue-Green/protocol config hints (non-secret). Values come from the optional
# env file or current environment; missing required values must stop deployment.
EDGE_BLUE_SUBNET="${CHARSOOQ_EDGE_BLUE_SUBNET:-${CHARSOOQ_EDGE_SUBNET:-}}"
WEB_BLUE_EDGE_IP="${CHARSOOQ_WEB_BLUE_EDGE_IP:-${CHARSOOQ_WEB_EDGE_IP:-}}"
EDGE_GREEN_SUBNET="${CHARSOOQ_EDGE_GREEN_SUBNET:-}"
WEB_GREEN_EDGE_IP="${CHARSOOQ_WEB_GREEN_EDGE_IP:-}"
PUBLIC_SCHEME="${CHARSOOQ_PUBLIC_SCHEME:-https}"

pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; FAILURES=$((FAILURES + 1)); }
info() { printf '[INFO] %s\n' "$*"; }

FAILURES=0

info "ChaharSooq runner preflight (read-only). No install/register performed."

if command -v docker >/dev/null 2>&1; then
  pass "docker CLI found: $(command -v docker)"
  if docker --version >/dev/null 2>&1; then
    pass "docker version available"
  else
    warn "docker version command did not succeed for the current user"
  fi
  if docker compose version >/dev/null 2>&1; then
    pass "docker compose v2 available"
  else
    warn "docker compose v2 is not available to the current user"
  fi
else
  fail "docker CLI not found"
fi

if command -v curl >/dev/null 2>&1; then
  pass "curl found"
else
  warn "curl not found (needed for GitHub/diagnostic checks and optional external probes)"
fi

if command -v tar >/dev/null 2>&1; then
  pass "tar found"
else
  fail "tar not found (required to extract the GitHub Actions runner package)"
fi

if command -v sha256sum >/dev/null 2>&1 || command -v shasum >/dev/null 2>&1; then
  pass "SHA-256 tool found"
else
  warn "sha256sum/shasum not found (recommended to verify runner package checksum)"
fi

if command -v systemctl >/dev/null 2>&1; then
  pass "systemctl found (required for runner service management on systemd hosts)"
else
  warn "systemctl not found; service management steps may differ on this host"
fi

if id "$RUNNER_USER" >/dev/null 2>&1; then
  pass "runner user exists: $RUNNER_USER"
  if id -nG "$RUNNER_USER" 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
    warn "runner user is in the docker group (root-equivalent access). Review least-privilege options in docs/operations/self-hosted-runner.md"
  else
    info "runner user is not in the docker group (check how Docker access will be granted)"
  fi
else
  warn "runner user does not exist yet: $RUNNER_USER"
fi

if [ -d "$RUNNER_DIR" ]; then
  pass "runner directory exists: $RUNNER_DIR"
else
  info "runner directory not present yet (expected before install): $RUNNER_DIR"
fi

for p in "$COMPOSE_FILE" "$PROD_ENV_FILE" "$UPSTREAM_FILE"; do
  if [ -e "$p" ]; then
    pass "path exists: $p"
  else
    warn "path not found (required before automated deploy): $p"
  fi
done

for p in "$STATE_DIR" "$SECRETS_DIR"; do
  if [ -d "$p" ]; then
    pass "directory exists: $p"
  else
    warn "directory not found (required on Production host): $p"
  fi
done

# Deploy script requires writable state dir/file and writable active upstream file.
if [ -d "$STATE_DIR" ]; then
  if [ -w "$STATE_DIR" ]; then
    pass "state directory is writable: $STATE_DIR"
  else
    warn "state directory is not writable (deploy will fail before state write): $STATE_DIR"
  fi
fi
if [ -f "$UPSTREAM_FILE" ]; then
  if [ -w "$UPSTREAM_FILE" ]; then
    pass "active upstream file is writable: $UPSTREAM_FILE"
  else
    fail "active upstream file is not writable (required for Blue-Green traffic switch): $UPSTREAM_FILE"
  fi
fi

# Required Blue-Green/protocol values must be present before any deployment.
for name in CHARSOOQ_PROXY_BIND_IP CHARSOOQ_SITE_HOST; do
  eval "v=\${$name:-}"
  if [ -n "$v" ]; then
    pass "$name is set"
  else
    warn "$name is not set (required by deploy script)"
  fi
done
if [ -n "$EDGE_BLUE_SUBNET" ] && [ -n "$WEB_BLUE_EDGE_IP" ]; then
  pass "blue slot edge values are set"
else
  warn "blue slot edge values are missing (CHARSOOQ_EDGE_BLUE_SUBNET/CHARSOOQ_WEB_BLUE_EDGE_IP or legacy names)"
fi
if [ -n "$EDGE_GREEN_SUBNET" ] && [ -n "$WEB_GREEN_EDGE_IP" ]; then
  pass "green slot edge values are set"
else
  fail "green slot edge values are missing (CHARSOOQ_EDGE_GREEN_SUBNET and CHARSOOQ_WEB_GREEN_EDGE_IP are required; deploy must stop before changes)"
fi
case "$PUBLIC_SCHEME" in
  http)
    pass "public scheme is http (HTTP-only external probes; TLS/HSTS/redirect must remain disabled by config)"
    ;;
  https)
    pass "public scheme is https (HTTPS external probes)"
    if [ -n "${CHARSOOQ_CA_FILE:-}" ]; then
      info "CHARSOOQ_CA_FILE is set for HTTPS probes"
    else
      warn "CHARSOOQ_CA_FILE is not set (deploy script requires it for HTTPS external verification)"
    fi
    ;;
  *)
    fail "CHARSOOQ_PUBLIC_SCHEME must be 'http' or 'https'"
    ;;
esac

if [ -n "${CHARSOOQ_RUNNER_LABELS:-}" ]; then
  info "configured runner labels: ${CHARSOOQ_RUNNER_LABELS}"
else
  info "runner labels not set in env; deploy workflow requires: charsooq-production"
fi

if [ "$FAILURES" -gt 0 ]; then
  printf '[RESULT] %s failure(s). Resolve required items before runner activation/deploy.\n' "$FAILURES"
  exit 1
fi

printf '[RESULT] No hard failures detected. Review WARN/INFO items before activation/deploy.\n'
