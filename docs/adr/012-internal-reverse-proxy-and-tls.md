# ADR 012 — Internal reverse proxy and TLS foundation

Date: 2026-11-13 · Status: accepted

## Context

Production runs on the organization's internal Ubuntu host (`market-linux`) and is reachable only
from the internal network. Until now [compose.production.yml](../../compose.production.yml)
published no host port: `web:3000`, `api:8000`, and `db:5432` existed only inside the Compose
project. Real users need a browser-facing HTTPS endpoint, and the API and PostgreSQL must never be
reachable from a browser or from the host network directly.

Several inputs are still missing: whether an internal DNS name exists, whether the organization has
a CA, which internal IP is finally approved, whether ports 80/443 are free, and what the Docker
address pools look like. The architecture therefore has to be complete, explicit, and **impossible
to start with guessed values** rather than hardcoded to the currently reported address
(`172.30.2.2`).

## Decision

- **Caddy is the internal reverse proxy and the only TLS terminator.** Pinned image
  `caddy:2.11.9-alpine` (official image), no Docker socket, read-only root filesystem, all
  capabilities dropped except `NET_BIND_SERVICE`, `no-new-privileges`, admin API off. Configuration
  is committed under [deploy/caddy](../../deploy/caddy/), state and certificates live in the named
  volumes `caddy_data` / `caddy_config`.
- **Caddy has exactly one upstream: `web:3000`.** The request path is
  `client → Caddy → web (Next.js) → /api/* rewrite → api → db`. The API is never exposed through
  the proxy, so browser traffic is same-origin and the session cookie stays first-party.
- **A dedicated `proxy` Docker network carries only `caddy` and `web`.** `web` stays on `edge` as
  well; `api` stays on `edge` + `backend`; `db`, `provision`, and `migrate` stay on `backend` only.
  `proxy` therefore gives the proxy no route to the API, PostgreSQL, provisioning, or migrations.
- **Only Caddy publishes ports, bound to one approved internal IP.** `80` and `443` are mapped as
  `${CHARSOOQ_PROXY_BIND_IP}:port:port`; no bare `"80:80"`, no `0.0.0.0`, no IPv6 listener, no
  HTTP/3/UDP. Listeners are restricted to `h1 h2` so Caddy never advertises an `alt-svc` HTTP/3
  endpoint that nothing publishes. The bind address is required input (`:?` in Compose), not a
  default.
- **The `proxy` network has no hardcoded subnet.** Docker assigns it from its own pool until the
  organization's routes and address pools are known; a conflict is resolved by an approved
  `ipam` block or the daemon's `default-address-pools`, documented in the deployment runbook.
- **`edge` takes an explicit, operator-supplied subnet and `web` gets a fixed address there.**
  Uvicorn matches its trusted proxy by IP only; a dynamic Docker address would make the trust list
  unknowable. The same value (`CHARSOOQ_WEB_EDGE_IP`) is both `web`'s address and the API's
  `FORWARDED_ALLOW_IPS`, so the two cannot drift.
- **TLS is configurable in three shapes** selected by `CHARSOOQ_TLS_MODE`:

  | Mode           | Material                                                  | Client trust                                      | Priority   |
  | -------------- | --------------------------------------------------------- | ------------------------------------------------- | ---------- |
  | `organization` | certificate issued by the organization CA (DNS or IP SAN) | the organization's CA is already distributed      | first      |
  | `organization` | certificate issued by a public CA with a DNS SAN          | public trust store                                | if allowed |
  | `internal-ca`  | certificate issued by Caddy's local CA                    | Caddy's root CA must be installed on every client | fallback   |

  No certificate is generated, committed, or trusted in this task. Certificate files live outside
  the repository (`CHARSOOQ_TLS_DIR`, default `/etc/charsooq/tls`) and are mounted read-only.
  Caddy's local-CA material stays in `caddy_data`.

- **The site address is always `https://` plus `CHARSOOQ_SITE_HOST`.** Plain-HTTP Production is not
  expressible in the Caddyfile, and the `:80` listener only performs Caddy's automatic redirect to
  HTTPS.
- **HSTS has one owner: Caddy.** It sends `Strict-Transport-Security: max-age=31536000` on HTTPS
  responses only, without `includeSubDomains` and without `preload`. The API's automatic
  production HSTS header was removed; this supersedes the HSTS part of
  [ADR 008](008-perf-security-hardening.md).
- **Access logs never capture credentials.** The site uses Caddy's default JSON access log on
  stdout. `log_credentials` is never enabled, so `Cookie`, `Set-Cookie`, `Authorization`, and
  `Proxy-Authorization` are omitted; no custom log format references headers. A static test fails if
  any snippet introduces them.
- **Forwarded headers are rewritten, not trusted.** Caddy sets `X-Forwarded-For` to the direct peer
  (`{remote_host}`), `X-Forwarded-Proto` to `{scheme}`, `X-Forwarded-Host` to `{host}`, and
  `X-Forwarded-Port` to the fixed published port (`443`), and strips `Forwarded`, `X-Real-IP`, and
  `X-Forwarded-Server`. Next.js preserves those values and only fills gaps from its own socket, and
  its rewrite forwards them to FastAPI. FastAPI/Uvicorn trusts only `web`'s fixed address
  (`FORWARDED_ALLOW_IPS`); `FORWARDED_ALLOW_IPS=*` is forbidden.
- **Documentation is the operational source of truth:**
  [deployment.md](../architecture/deployment.md#reverse-proxy-tls-and-exposure) holds the topology,
  variables, certificate handling, verification commands, and the open decisions that IT must
  answer.

## Alternatives

- **Nginx or Traefik:** rejected — Caddy gives automatic HTTP→HTTPS redirect, certificate loading,
  and an internal CA without extra configuration files; the project has no existing investment in
  either.
- **Publish the web port and skip the proxy:** rejected — no TLS, no single place for HSTS and
  header hygiene, and the browser would talk to Next.js over plain HTTP.
- **Let Caddy proxy `/api/*` straight to FastAPI:** rejected — it would make FastAPI
  internet-facing through the proxy, split the origin (CORS and third-party cookies), and give the
  proxy a route to the application server.
- **Trust the whole `edge` subnet in Uvicorn:** rejected — broader than the only legitimate peer;
  a single fixed address is equivalent and narrower.
- **Hardcode `172.30.2.2` as the bind address or a subnet:** rejected — reported environment
  information, not an approved decision, and a wrong bind either exposes the panel on the wrong
  interface or silently collides with the organization's routes.
- **Enable HTTP/3 and IPv6 because Caddy supports them:** rejected — both are open decisions; the
  IPv6 path would bypass the explicit IPv4 bind.

## Consequences

- Production cannot start until the operator supplies `CHARSOOQ_PROXY_BIND_IP`,
  `CHARSOOQ_SITE_HOST`, `CHARSOOQ_EDGE_SUBNET`, and `CHARSOOQ_WEB_EDGE_IP`, plus TLS material or an
  explicit `internal-ca` decision. That is intentional: an unconfigured stack fails instead of
  publishing on every interface.
- `make prod-config` validates structure with RFC 5737 documentation addresses; it no longer proves
  that a real deployment is configured. Real validation happens with the deployment environment's
  values.
- Changing `web`'s fixed address, the `edge` subnet, or the trusted proxy requires restarting `api`;
  a mismatch fails closed (forwarded headers ignored) rather than trusting the wrong peer.
- With Caddy's admin API off, a configuration or certificate change needs
  `docker compose restart caddy`; there is no hot reload path.
- Caddy is a single instance; there is no HA pair. A proxy outage takes the panel offline even
  though the API and database keep running.
- HSTS is one year from the first HTTPS response. Because this task does not deploy TLS, no browser
  has cached it yet; `includeSubDomains`/`preload` stay off until every subdomain is confirmed.
- Client trust for `internal-ca` is an organizational rollout (for example Group Policy). Losing the
  `caddy_data` volume replaces the CA and breaks every trusting client.
- Staging is served by Vercel, whose edge sends HSTS for every deployment
  (`max-age=63072000`, plus `includeSubDomains; preload` on `*.vercel.app`; custom domains get the
  `max-age` only). The API no longer adds a second, shorter policy through the Next rewrite, so
  Staging keeps HSTS with a single owner. If a custom policy is needed there, it belongs in the
  Vercel project's response headers, not in the application. A regression test
  (`backend/api/tests/test_hsts_ownership.py`) fails if environment-conditional HSTS returns.
- The ten IT-owned decisions (DNS, CA, root-CA distribution, fixed IP, ports 80/443, IPv6, Docker
  address pools, firewall/VLAN, certificate policy) remain open and are listed in
  [deployment.md](../architecture/deployment.md#open-decisions-owned-by-it).
