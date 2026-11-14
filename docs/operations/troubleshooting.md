# Troubleshooting — چهارسوق Production

Status: **diagnostic procedure only**. Nothing here was run against `market-linux`; no Production
stack, database, secret file, or real certificate was opened. Use this with the
[Production runbook](production-runbook.md), the [TLS lifecycle](tls-certificate-lifecycle.md), and
[backup and recovery](backup-and-recovery.md).

## 1. How to work a failure

Work from the outside in, and stop at the first failing layer:

```text
client DNS → TCP 443 → Caddy/TLS → web:3000 → /api/* rewrite → api:8000 → db:5432
```

Rules:

1. **Do not change two things at once.** One hypothesis, one read-only check, one fix.
2. **Preserve evidence before restarting.** A restart can erase the only copy of the error.
3. **Never print a secret.** Do not run `cat` on `/etc/charsooq/secrets/*`, `docker inspect` without a
   narrow format, `env`, or `docker compose config` pasted into a ticket.
4. **Never delete a volume** as a diagnostic step. `pgdata`, `caddy_data`, and `caddy_config` are
   state, not cache.
5. **Prefer `stop`/`restart` of one service** over `down`. `make prod-down` keeps volumes but causes a
   full outage; `down -v` destroys them and is never a repair.

Quick orientation:

```bash
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml ps -a
docker compose -f compose.production.yml logs --since 15m --tail=200
```

Host/operator, read-only. Use the same exported `CHARSOOQ_*` values as the runbook.

## 2. Evidence kit

Collect into a root-owned directory outside the repository, mode `0700`, for example
`/var/log/charsooq-incident-<id>/`. Redact before sharing.

```bash
INCIDENT_DIR=/var/log/charsooq-incident-20261113-example   # replace with the incident ID
install -d -m 0700 -o root -g root "$INCIDENT_DIR"
date -u
docker version
docker compose version
docker compose -f compose.production.yml ps -a
docker compose -f compose.production.yml logs --since 2h --tail=500 \
  > "$INCIDENT_DIR/compose.log"
```

For a single container, narrow the inspection instead of dumping everything:

```bash
SERVICE=api
CID=$(docker compose -f compose.production.yml ps -q "$SERVICE")
docker inspect --format '{{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CID"
```

Container, read-only (the `docker inspect` runs on the host against one container). Do not run a bare
`docker inspect` and paste the output: it contains environment variables and paths.

Also record, when relevant:

```bash
ss -ltnp '( sport = :80 or sport = :443 )'
df -h / /var/lib/docker
df -i / /var/lib/docker
free -h
docker system df
docker stats --no-stream
docker network inspect charsooq-production_edge
```

`docker network inspect` is read-only but reveals container addresses; it is not a secret. `docker
stats` is a snapshot; run it once, not in a tight loop.

## 3. Quick matrix

| #   | Symptom                           | First checks                                                                 | Healthy result                                      | Allowed action                                         | Dangerous / forbidden                                            |
| --- | --------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------- |
| 1   | Site does not open                | DNS, `ss -ltnp`, `ps caddy`, `ps web`, Caddy logs                            | Name resolves, 443 listening, `caddy`/`web` healthy | Fix DNS/port/process; restart the failing layer        | Changing firewall, deleting `caddy_data`, exposing `web`         |
| 2   | HTTPS error / certificate warning | `openssl s_client`, `tls-validate`, SAN, CA trust, Caddy logs                | Chain verifies, SAN matches, not expired            | Renew/activate via TLS runbook; restart Caddy          | `curl -k` acceptance, disabling TLS/HSTS, placeholder cert       |
| 3   | Login fails                       | API `/ready`, login response, cookie flags, `admin_sessions`, `admins`       | 200 + `charsooq_session` `Secure`/`HttpOnly`/`Lax`  | Fix API/DB, re-bootstrap owner, clear expired sessions | Editing password hashes by hand, disabling rate limit            |
| 4   | API unavailable                   | `ps api`, `/health`, `/ready`, API logs, DB reachability                     | `healthy`, `/health` ok, `/ready` ready             | Fix config/secret/DB; recreate API                     | Starting API before migrate; deleting DB volume                  |
| 5   | Database not ready                | `ps db`, `pg_isready`, DB logs, `df`, `free`, volume state                   | `healthy`, `accepting connections`, `SELECT 1`      | Free resources, restart `db` once, restore if corrupt  | `initdb` over data, removing `pgdata`, `down -v`                 |
| 6   | Migration failed                  | `make prod-migrate` output, `alembic current/heads`, `pg_locks`, role grants | Current == head, exit 0, no advisory lock           | Fix revision/role, re-run; restore if destructive      | `alembic downgrade`, editing `alembic_version`, starting API     |
| 7   | Provisioning failed               | Provision output, secret `stat`, role list, URL roles/database               | Both roles ready, grants converged                  | Fix permissions/URLs; re-run `prod-provision`          | Superuser for app role, same role for both URLs, world-readable  |
| 8   | Web cannot reach API              | `web` fetch to `api:8000`, `ps api`, `edge` membership, `API_URL_INTERNAL`   | Fetch returns 200                                   | Fix API/network; rebuild web if build URL changed      | Publishing `api:8000`, adding API to `proxy`                     |
| 9   | Caddy will not start              | `logs caddy`, `prod-caddy-validate`, Compose config, ports, mounts           | `Valid configuration`, listener bound               | Fix input; recreate or restart Caddy                   | Deleting Caddy volumes, disabling TLS, binding `0.0.0.0`         |
| 10  | Disk full                         | `df -h`, `df -i`, `docker system df`, biggest log/image/volume               | Free space and inodes above threshold               | Prune dangling images/build cache after evidence       | `docker system prune --volumes`, deleting `pgdata`/Caddy volumes |
| 11  | Service down after restart        | `ps -a`, logs, exit/OOM, dependency health, image presence                   | Bottom-up start reaches `healthy`                   | Start db → api → web → caddy; run one-shots if needed  | Starting all at once, `down -v`, recreating DB volume            |

## 4. Detailed diagnostics

### 4.1 The site does not open

**Symptom:** browser cannot connect, times out, or gets a connection reset; `curl` fails before any
HTTP status.

**Checks, in order:**

```bash
# 1. From an approved client: does the name resolve to the approved address?
getent ahosts '<site-host>'

# 2. On the host: is anything listening on the approved address and ports?
ss -ltnp '( sport = :80 or sport = :443 )'
docker compose -f compose.production.yml port caddy 443

# 3. Is the proxy container up and healthy enough to serve?
docker compose -f compose.production.yml ps caddy
docker compose -f compose.production.yml logs --since 20m caddy

# 4. Is the upstream web container up?
docker compose -f compose.production.yml ps web
docker compose -f compose.production.yml logs --since 20m web
```

Healthy: DNS returns the approved address; `443` is bound to `CHARSOOQ_PROXY_BIND_IP`; `caddy` is
`running` and its log has no config/TLS error; `web` is `healthy`. If DNS is wrong, fix DNS with IT,
not `/etc/hosts` on every client. If the port is not bound, see 4.9. If Caddy is up but web is not,
see 4.11.

**Allowed:** fix the failing layer, restart that one service, or ask IT to correct DNS/firewall.
**Dangerous:** changing the bind address or firewall to “test”, publishing `web`/`api`, deleting Caddy
volumes, or running the stack without TLS.

### 4.2 HTTPS returns an error or a certificate warning

**Symptom:** `ERR_CERT_*`, untrusted issuer, name mismatch, expired certificate, or a TLS handshake
failure.

**Checks:**

```bash
SITE_HOST='<site-host>'
CA_FILE="$CHARSOOQ_TLS_DIR/org-root.crt"   # or the distributed public root in internal-ca mode

openssl s_client -connect "$SITE_HOST:443" -servername "$SITE_HOST" \
  -CAfile "$CA_FILE" -verify_return_error -verify_hostname "$SITE_HOST" </dev/null
openssl s_client -connect "$SITE_HOST:443" -servername "$SITE_HOST" </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName -fingerprint -sha256

make tls-validate \
  CERT="$CHARSOOQ_TLS_DIR/current/fullchain.pem" \
  KEY="$CHARSOOQ_TLS_DIR/current/privkey.pem" \
  HOST="$SITE_HOST" \
  CA_FILE="$CHARSOOQ_TLS_DIR/org-root.crt" \
  MIN_DAYS=30

docker compose -f compose.production.yml logs --since 20m caddy
```

Healthy: verify exits 0; SAN equals `$SITE_HOST`; `notAfter` is in the future with at least 30 days;
served fingerprint equals the recorded activation; Caddy logs show no certificate/TLS error.

Common distinctions:

| Finding                               | Meaning                                                           | Next step                                                                   |
| ------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Name mismatch                         | Browser URL is not the certificate SAN                            | Use the exact DNS name/IP; do not add a random alias                        |
| Unknown issuer in `organization` mode | Client does not trust the organization CA, or chain is incomplete | Install/distribute the root; supply leaf + intermediates in `fullchain.pem` |
| Unknown issuer in `internal-ca` mode  | Client does not trust Caddy's root                                | Distribute the public root; never copy `root.key`                           |
| Expired / near expiry                 | Renewal missed                                                    | Renew, validate, activate, restart Caddy; treat ≤7 days as an incident      |
| Key mismatch                          | `current` points at a half-switched pair, or files were edited    | Run `tls-rollback` to a known version; never hand-edit `current`            |
| Handshake works but HTTP 502          | TLS is fine; Caddy cannot reach `web`                             | See 4.8/4.11                                                                |

**Allowed:** use the TLS lifecycle to install/rotate/rollback, validate, restart Caddy, verify the
served fingerprint.
**Dangerous:** `curl -k`, browser “proceed anyway”, disabling HSTS, replacing the certificate with a
self-signed placeholder, or deleting `caddy_data`.

### 4.3 Login does not work

**Symptom:** login page loads, but credentials are rejected, the page loops, or the session does not
persist.

**Checks:**

```bash
# Is the API alive and database-ready?
curl -sS --cacert "$CA_FILE" "https://$SITE_HOST/api/v1/health"
curl -sS --cacert "$CA_FILE" "https://$SITE_HOST/api/v1/ready"

# What does the API say around the attempt?
docker compose -f compose.production.yml logs --since 15m api

# Is the browser using the exact site host and HTTPS?
# DevTools → Application → Cookies: charsooq_session should be Secure, HttpOnly, SameSite=Lax, Path=/.

# Is there an owner account? Read only non-secret columns.
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT username, role FROM admins;'
```

Healthy: `/health` and `/ready` return 200 JSON; API logs show a normal `401` only for a bad password;
the cookie is present after login with the flags above; the owner row exists. A `429` means the login
rate limiter (10 attempts/minute/IP+username) is active; wait for the window, do not disable it. A
`502` means the API/web path, not the password.

If the owner is missing or the password was changed intentionally, update `owner_password` through
the approved secret process and run `make prod-bootstrap-owner`. Do not insert/modify password hashes
with SQL. If sessions must be wiped after a suspected compromise, delete `admin_sessions` rows with a
backup and incident record; otherwise old sessions expire normally.

**Allowed:** fix API/DB, re-bootstrap the owner, wait out the rate limit, recreate `api` after a secret
change.
**Dangerous:** disabling rate limiting, setting a plaintext password in the DB, copying a cookie from
a browser into a ticket, or disabling `Secure`/`HttpOnly`.

### 4.4 The API is unavailable

**Symptom:** `/api/*` returns 502/500/connection error; login and data pages fail; Caddy may still
serve the login shell.

**Checks:**

```bash
docker compose -f compose.production.yml ps api
docker compose -f compose.production.yml logs --since 20m api
CID=$(docker compose -f compose.production.yml ps -q api)
docker inspect --format '{{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CID"
docker compose -f compose.production.yml exec -T api \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
docker compose -f compose.production.yml exec -T db \
  pg_isready -U charsooq -d charsooq -h 127.0.0.1
```

Healthy: `healthy`; exit 0; `/health` returns `{"status":"ok"}`; DB accepts connections. `oom=true` or
exit `137` points at memory; exit `1` usually points at configuration, a missing secret file, or a
database failure. Check file ownership/mode with `stat` (never `cat`). If `/ready` fails while
`/health` works, the API process is alive but the database/app role is not usable.

**Allowed:** fix the cause, then `restart api` (process) or `up -d --no-deps --force-recreate api`
(config/secret change); wait for `healthy`.
**Dangerous:** starting the API before migrations, repeatedly restarting a crash loop, running
`alembic downgrade`, or deleting the database volume.

### 4.5 The database is not ready

**Symptom:** `db` is `starting`/`unhealthy`; API `/ready` fails; PostgreSQL logs show startup or I/O
errors.

**Checks:**

```bash
docker compose -f compose.production.yml ps db
docker compose -f compose.production.yml logs --since 20m db
docker compose -f compose.production.yml exec -T db \
  pg_isready -U charsooq -d charsooq -h 127.0.0.1
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT 1;'
df -h / /var/lib/docker
df -i / /var/lib/docker
free -h
```

Healthy: `healthy`; `accepting connections`; `1`. The `db` healthcheck allows 20 s startup plus 10
retries at 5 s, so a slow disk can look like a failure. Look for “no space left on device”, “could not
extend file”, “invalid checkpoint”, or “database system is in recovery mode”. If the volume is
corrupt, stop and follow [backup-and-recovery.md](backup-and-recovery.md) section 7; do not run
`initdb` over the existing data directory.

**Allowed:** free disk/memory, fix the volume mount, restart `db` once, restore from a verified dump.
**Dangerous:** removing `charsooq-production_pgdata`, `docker compose down -v`, `pg_resetwal`, or
starting a second PostgreSQL against the same volume.

### 4.6 Migration failed

**Symptom:** `make prod-migrate` exits non-zero; `api` is not recreated; logs show a SQL, permission,
or lock timeout error.

**Checks:**

```bash
# State-changing: this re-runs the migration; capture the exact exit and message.
make prod-migrate
# The run --rm container is removed; its output is the primary evidence.
docker compose -f compose.production.yml logs --since 30m migrate 2>/dev/null || true
docker compose -f compose.production.yml run --rm --no-deps migrate \
  sh -c 'cd backend/api && alembic current'
docker compose -f compose.production.yml run --rm --no-deps migrate \
  sh -c 'cd backend/api && alembic heads'
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT version_num FROM alembic_version;'
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -c \
  "SELECT pid, locktype, mode, granted FROM pg_locks WHERE locktype = 'advisory';"
```

Healthy: `migrate: database is at head`; `current` equals the single `heads` revision; the DB row
matches; no advisory lock held. A lock timeout means another runner is active or a session died while
holding the lock; PostgreSQL releases a session lock when the connection closes. A permission error
usually means the migration role does not own the schema/object; run `prod-provision` and inspect
ownership, do not grant superuser.

**Allowed:** fix the revision or role and re-run; restore the pre-change dump if the migration was
destructive/partially applied; keep the old API serving if it is still compatible.
**Dangerous:** starting the new API, editing `alembic_version`, running `alembic downgrade`, or
dropping/recreating the schema.

### 4.7 Provisioning failed

**Symptom:** `make prod-provision` exits non-zero; `migrate` and `api` do not start; the log names a
role, password, ownership, or grant failure.

**Checks:**

```bash
# State-changing: idempotent re-run; it may rotate role passwords to the URL values.
make prod-provision
# The run --rm container is removed; its output is the primary evidence.
docker compose -f compose.production.yml logs --since 30m provision 2>/dev/null || true

# Presence, owner, and mode only — never contents.
sudo stat -c '%A %U:%G %n' /etc/charsooq/secrets/postgres_password \
  /etc/charsooq/secrets/database_url /etc/charsooq/secrets/migration_database_url

# Roles and schema ownership, no passwords printed.
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -c '\du'
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -c '\dn+'
```

Healthy: `provision-database-roles: application and migration roles are ready`; both roles exist;
`public` is owned by the migration role; the app role has no `CREATE` on the schema; the admin password
file is `999:999 0440`, the other two are `10001:10001 0400`. Both URLs must target `db:5432/charsooq`
with different roles; the script fails closed if they do not.

**Allowed:** fix ownership/mode or the URL role names; re-run provisioning; if an object is owned by an
unexpected role, stop and investigate.
**Dangerous:** granting `SUPERUSER` to the app role, reusing one URL for both roles, making the admin
password world-readable, or mass-changing object ownership without a transaction/record.

### 4.8 Web cannot reach the API

**Symptom:** the login page may render, but `/api/*` returns 502/500; web logs show
`ECONNREFUSED api:8000` or a DNS error; Caddy is healthy.

**Checks:**

```bash
docker compose -f compose.production.yml exec -T web \
  node -e "fetch('http://api:8000/health').then(async r=>{console.log(r.status, await r.text())}).catch(e=>{console.error(e.message);process.exit(1)})"
docker compose -f compose.production.yml ps api web
docker compose -f compose.production.yml exec -T web node -e "console.log(process.env.API_URL_INTERNAL)"
docker network inspect charsooq-production_edge
docker compose -f compose.production.yml logs --since 20m web api
```

Healthy: fetch returns `200 {"status":"ok"}`; both `api` and `web` are attached to the `edge` network;
`API_URL_INTERNAL` is `http://api:8000`. Remember it is a **build arg** and a runtime variable: changing
it requires rebuilding `web`, not just restarting it. Caddy never calls the API; if Caddy is healthy
but this fetch fails, the problem is `edge`, `api`, or the Next rewrite, not TLS.

**Allowed:** start/fix `api`; fix the `edge` membership; rebuild/recreate `web` if the URL changed;
restart `caddy` after a `web` recreate.
**Dangerous:** publishing `api:8000`, adding `api` to `proxy`, or bypassing the rewrite so the browser
talks to the API cross-origin (the session cookie would become third-party).

### 4.9 Caddy will not start

**Symptom:** `caddy` is `restarting`/`exited`; the site is unreachable; logs show a Caddyfile parse,
certificate, mount, or bind error.

**Checks:**

```bash
docker compose -f compose.production.yml ps -a caddy
docker compose -f compose.production.yml logs --since 30m caddy
make prod-caddy-validate
docker compose -f compose.production.yml config --quiet
ss -ltnp '( sport = :80 or sport = :443 )'
readlink -f "$CHARSOOQ_TLS_DIR/current"
sudo stat -c '%A %U:%G %n' "$CHARSOOQ_TLS_DIR" "$CHARSOOQ_TLS_DIR/current" \
  "$CHARSOOQ_TLS_DIR/current/fullchain.pem" "$CHARSOOQ_TLS_DIR/current/privkey.pem" 2>/dev/null
docker compose -f compose.production.yml run --rm --no-deps caddy caddy version
```

Healthy: `Valid configuration`; `config --quiet` exits 0; ports are free; `current` points inside the
mounted directory; the Caddy image version is `2.11.9`. Common causes: missing `current` in
`organization` mode, wrong `CHARSOOQ_SITE_HOST`, unknown `CHARSOOQ_TLS_MODE`, a missing
`deploy/caddy` directory, a read-only mount that does not exist, or another process on 80/443. In
`internal-ca` mode an empty cert directory is expected; Caddy creates its CA in `caddy_data`.

**Allowed:** fix the input; `restart caddy` for a certificate/process fix; `up -d --no-deps caddy` for
an environment/config/mount change.
**Dangerous:** deleting `caddy_data`/`caddy_config`, binding `0.0.0.0`, disabling TLS, or replacing the
Caddyfile with an unvalidated one.

### 4.10 Disk is full

**Symptom:** containers exit or restart; PostgreSQL reports “No space left on device”; Caddy cannot
write state; image builds fail.

**Checks:**

```bash
df -h / /var/lib/docker
df -i / /var/lib/docker
docker system df
sudo du -xh /var/lib/docker 2>/dev/null | sort -h | tail -20
sudo find /var/lib/docker/containers -name '*-json.log' -size +100M \
  -printf '%s %p\n' 2>/dev/null | sort -n
```

Healthy: used space and inodes are below the agreed threshold (target at least 20% free). The largest
consumers are usually images, build cache, container json logs, and `pgdata`. The Compose file now
bounds new container logs at 10 MB × 5; containers created before that change are not bounded until
recreated.

Safe cleanup, in order:

1. Collect logs for failed/one-shot containers before removing them.
2. `docker image prune` (dangling images only).
3. `docker builder prune` (build cache only).
4. Remove old, unused images by digest after confirming they are not the current/rollback images.
5. Recreate services to adopt log rotation.

**Allowed:** the above, plus expanding the host disk with IT.
**Dangerous:** `docker system prune --volumes`, `docker volume prune`, deleting
`charsooq-production_pgdata`, truncating a live PostgreSQL data file, or deleting Caddy's CA volume.

### 4.11 A service does not start after a restart

**Symptom:** after a host reboot, Docker restart, or `prod-down`/`prod-up`, one or more services are
`exited`/`restarting`; dependents return 502.

**Checks:**

```bash
SERVICE=api   # replace with the failing service
docker compose -f compose.production.yml ps -a
docker compose -f compose.production.yml logs --since 30m "$SERVICE"
CID=$(docker compose -f compose.production.yml ps -q "$SERVICE")
docker inspect --format '{{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CID"
docker image inspect "$CHARSOOQ_API_IMAGE" >/dev/null && echo api-image-present
docker image inspect "$CHARSOOQ_WEB_IMAGE" >/dev/null && echo web-image-present
```

Healthy: `db` becomes `healthy`; `provision`/`migrate` exit 0; `api` becomes `healthy`; `web` becomes
`healthy`; `caddy` is running and serves HTTPS. Common causes: a missing image after a prune, a
one-shot failure that blocked `api`, a secret file with the wrong owner/mode, a changed environment
that a `restart` did not pick up, or Caddy holding the old `web` address after a recreate.

**Allowed:** start bottom-up (`db` → `provision`/`migrate` if the volume is new → `api` → `web` →
`caddy`), wait for health at each layer, and recreate a service when its env/secret changed.
**Dangerous:** starting all services at once and hoping Compose sorts it out, `down -v`, recreating
the database volume, or starting Caddy before web is healthy.

## 5. Cross-cutting checks

### 5.1 Ports and bindings

```bash
ss -ltnp '( sport = :80 or sport = :443 )'
docker compose -f compose.production.yml port caddy 80
docker compose -f compose.production.yml port caddy 443
docker compose -f compose.production.yml ps
```

Only `caddy` may show published ports. They must be bound to `CHARSOOQ_PROXY_BIND_IP`, never `0.0.0.0`
or `[::]`. `db`, `api`, `web`, `provision`, and `migrate` must show no host ports.

### 5.2 Networks

```bash
docker network ls
docker network inspect charsooq-production_backend
docker network inspect charsooq-production_edge
docker network inspect charsooq-production_proxy
```

Expected membership: `backend` = db/provision/migrate/api (internal); `edge` = web/api; `proxy` =
caddy/web. Caddy must not appear on `backend` or `edge`; `db` must not appear on `edge` or `proxy`.

### 5.3 DNS and hosts

```bash
getent ahosts '<site-host>'
```

If a client resolves a different address than `CHARSOOQ_PROXY_BIND_IP`, fix DNS or the client's host
entry through IT. Do not add permanent `/etc/hosts` entries on user machines as a workaround.

### 5.4 Clock

```bash
timedatectl status
```

A wrong clock breaks certificate validation and session expiry. Stop and fix NTP; do not “fix” a TLS
error by lowering validation.

## 6. Escalation and evidence template

Escalate to the service owner when: data may be lost, a secret is exposed, TLS is invalid for users,
the database volume is corrupt, or the fix requires a schema downgrade/restore. Do not attempt a
destructive repair without an owner and a verified backup.

Incident record (keep outside the repository, access-controlled):

```text
Incident ID:
Start (UTC) / detected (UTC) / resolved (UTC):
Severity / user impact:
Detected by / incident lead:
Affected layer: dns | tcp | caddy | tls | web | api | db | host
Symptom:
Commands run and results (redacted):
Evidence location:
Secret exposure: no | suspected | confirmed (do not record the value)
Backup used (archive ID / checksum / off-host location):
Data-loss window:
Root cause:
Fix / rollback:
Verification (HTTPS / login / API / DB / row counts):
Follow-ups / owner / due date:
```

## 7. Forbidden shortcuts

- `docker compose down -v`, `docker volume prune`, `docker system prune --volumes`.
- Deleting or recreating `charsooq-production_pgdata`, `caddy_data`, or `caddy_config`.
- Running `initdb`, `pg_resetwal`, or `alembic downgrade` as a first response.
- Editing `alembic_version`, password hashes, or role grants by hand without a review and record.
- Disabling TLS/HSTS, using `curl -k` as acceptance, or installing a placeholder certificate.
- Publishing `db`, `api`, or `web` on a host port.
- Printing or pasting secrets, cookies, Authorization headers, or full database URLs.
- Rebuilding/deploying from a dirty working tree or an unapproved commit.
