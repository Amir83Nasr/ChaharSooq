# Production runbook — چهارسوق

Status: **procedure only**. Nothing in this file has been executed against `market-linux`, no
Production stack was started, no database or secret file was read, and no deployment was performed.
The architecture is in [deployment.md](../architecture/deployment.md); TLS operations are in
[TLS certificate lifecycle](tls-certificate-lifecycle.md); diagnostics are in
[troubleshooting.md](troubleshooting.md); backup and restore are in
[backup-and-recovery.md](backup-and-recovery.md).

Production is an internal-only, single-host Docker Compose stack. There is no HA pair, no zero-downtime
deployment, no registry/deploy pipeline, and no monitoring agent committed to this repository. Treat
every restart as a short outage and every schema change as irreversible until a verified backup exists.

## 1. Command conventions

Every command below is real for the current checkout. The labels say where it runs and what it can do.

| Label               | Meaning                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Host / root**     | A shell on `market-linux` as `root` (or through `sudo`). Can read secret files and change host state.                          |
| **Host / operator** | A shell on `market-linux` as the deployment account. Must be in the `docker` group; that group is effectively root-equivalent. |
| **Container**       | Run through `docker compose exec`/`run`; it executes inside the named container, not on the host.                              |
| **Read-only**       | Reads state only. It does not change containers, volumes, files, or the database.                                              |
| **State-changing**  | Starts/stops/recreates a container, writes a file, rotates a credential, or changes grants. Expect a short outage or lock.     |
| **Destructive**     | Can remove data or make a database unrecoverable without a backup. Never run as a first response.                              |

Directory: run Compose commands from the deployment checkout (for example `/opt/charsooq`) at the
approved commit. The file is `compose.production.yml`; `compose.yml` is the development stack and must
never be used for Production.

The four required deployment values have no defaults. Export them in the operator shell. They are
not secrets, but they are environment-specific and must not be committed:

```bash
export CHARSOOQ_PROXY_BIND_IP='<approved-internal-ip>'
export CHARSOOQ_SITE_HOST='<approved-dns-name-or-ip>'
export CHARSOOQ_EDGE_SUBNET='<approved-conflict-free-cidr>'
export CHARSOOQ_WEB_EDGE_IP='<web-fixed-address-in-that-cidr>'
export CHARSOOQ_TLS_MODE='organization'          # or internal-ca
export CHARSOOQ_TLS_DIR='/etc/charsooq/tls'      # default
export CHARSOOQ_SECRETS_DIR='/etc/charsooq/secrets'  # default
```

`CHARSOOQ_SITE_HOST` must be exactly the certificate SAN: a DNS name for a DNS SAN, or the literal
address for an IP SAN. Do not include a scheme, port, or trailing slash.

## 2. Stack inventory

```text
client --HTTPS--> caddy:443 (bound to CHARSOOQ_PROXY_BIND_IP)
                    │ proxy
                    ▼
                  web:3000 (Next.js standalone, /api/* rewrite)
                    │ edge
                    ▼
                  api:8000 (FastAPI, two Uvicorn workers)
                    │ backend (internal)
                    ▼
                  db:5432 (PostgreSQL 18.6)
```

| Service     | Image / build          | Identity      | Exposure / purpose                                                           |
| ----------- | ---------------------- | ------------- | ---------------------------------------------------------------------------- |
| `db`        | `postgres:18.6-trixie` | `999:999`     | `backend` only; volume `charsooq-production_pgdata` at `/var/lib/postgresql` |
| `provision` | `Dockerfile.api`       | `10001:10001` | One-shot, idempotent role and grant provisioning; exits 0                    |
| `migrate`   | `Dockerfile.api`       | `10001:10001` | One-shot Alembic runner under the advisory lock; exits 0 at head             |
| `api`       | `Dockerfile.api`       | `10001:10001` | `backend` + `edge`; `/health` and `/ready`                                   |
| `web`       | `Dockerfile.web`       | `1000:1000`   | `edge` + `proxy`; Next.js on `3000`; `/login`                                |
| `caddy`     | `caddy:2.11.9-alpine`  | image default | `proxy` only; published `80`/`443`; TLS terminator                           |

The Compose project name is `charsooq-production`, so the volumes are
`charsooq-production_pgdata`, `charsooq-production_caddy_data`, and
`charsooq-production_caddy_config`. `make prod-down` keeps them. Nothing in the Makefile runs
`docker compose down -v`; do not add it.

Container logs are bounded by the Compose file: `json-file`, `max-size: 10m`, `max-file: 5` per
service. Existing containers must be recreated once (not restarted) to adopt the setting.

## 3. Preflight

Run every check before the first start and after any host or Docker upgrade. If an IT-owned value is
unknown, stop. Do not guess a bind address, subnet, hostname, or certificate mode.

### 3.1 Host, clock, and access

```bash
hostnamectl status
timedatectl status
timedatectl show -p NTPSynchronized --value
```

| Fact                | Healthy result                           | If not healthy                                                   |
| ------------------- | ---------------------------------------- | ---------------------------------------------------------------- |
| Host identity       | The agreed `market-linux` host           | Stop and confirm with IT; do not deploy to a look-alike host     |
| Clock/NTP           | `NTPSynchronized=yes`; time close to UTC | Stop: certificate and session expiry checks are unreliable       |
| Docker access       | `docker info` succeeds for the operator  | Get the approved operator into the `docker` group; group is root |
| Deployment checkout | Approved commit, clean working tree      | Do not build from a dirty tree or an unapproved branch           |

```bash
git status --porcelain
git rev-parse HEAD
git describe --tags --always --dirty
```

Expected: no output from `git status --porcelain`; `git rev-parse HEAD` equals the approved release
SHA; `git describe` is not `-dirty`.

### 3.2 Docker Engine and Compose

```bash
docker version
docker compose version
docker info --format 'driver={{.Driver}} logging={{.LoggingDriver}} cpus={{.NCPU}} mem={{.MemTotal}}'
docker compose up --help | grep -E -- '--wait|--wait-timeout'
```

Healthy: a supported Docker Engine and Compose v2, `overlay2` (or the approved storage driver), a
known logging driver, and `--wait` support. The file requires Compose features
`depends_on.condition: service_completed_successfully`, `name:`, and `--wait`; if `--wait` is absent,
use `docker compose ps` and wait for `healthy` manually. Record both versions in the release log.

### 3.3 Disk, memory, and CPU

```bash
df -h / /var/lib/docker
df -i / /var/lib/docker
docker system df
free -h
nproc
sudo du -sh /var/lib/docker/volumes/charsooq-production_pgdata \
  /var/lib/docker/volumes/charsooq-production_caddy_data \
  /var/lib/docker/volumes/charsooq-production_caddy_config 2>/dev/null
```

Healthy: at least 20% free on `/var/lib/docker` and enough room for a full logical dump plus the
next image set; no inode exhaustion. The Compose limits total 2.75 GiB if every service ran at once,
but `provision` and `migrate` are sequential one-shots; plan headroom for the host, Docker, and
PostgreSQL shared buffers. Do not rely on the limits as a capacity plan.

### 3.4 Address space and port availability

```bash
ip -brief address
ip -4 route
ip -6 route
ss -ltnp '( sport = :80 or sport = :443 )'
docker network ls
docker network inspect $(docker network ls -q) \
  --format '{{.Name}} {{range .IPAM.Config}}{{.Subnet}} {{end}}'
```

Healthy: the approved bind address exists on the intended interface; `80`/`443` are unused; the
`CHARSOOQ_EDGE_SUBNET` does not overlap the LAN, VPN, Docker pools, or the `proxy` network's assigned
range. IPv6 is intentionally unused. Do not change firewall or network configuration as part of this
runbook; resolve a conflict with IT before starting.

### 3.5 Secret files, data paths, and permissions

Never `cat`, `less`, `env`, or `docker inspect` a secret value. Check names, ownership, mode, and
non-emptiness:

```bash
sudo stat -c '%A %U:%G %n' /etc/charsooq /etc/charsooq/secrets /etc/charsooq/tls
sudo stat -c '%A %U:%G %n' /opt/charsooq /var/lib/docker /var/lib/docker/volumes \
  /secure/charsooq-db-backups 2>/dev/null
sudo ls -ld /var/lib/docker/volumes/charsooq-production_pgdata/_data 2>/dev/null
sudo find /etc/charsooq/secrets -maxdepth 1 -type f -printf '%m %u:%g %f\n' | sort

for f in postgres_password database_url migration_database_url session_secret owner_password parsina_password; do
  sudo test -f "/etc/charsooq/secrets/$f" && echo "present: $f" || echo "MISSING: $f"
done

for f in postgres_password database_url migration_database_url session_secret owner_password; do
  sudo test -s "/etc/charsooq/secrets/$f" && echo "non-empty: $f" || echo "EMPTY (fix): $f"
done
# parsina_password is allowed to be empty when the integration is disabled, but the file must exist.
```

Expected ownership/mode (the exact commands are in
[deployment.md](../architecture/deployment.md#production-secrets)):

| File                     | Owner:group   | Mode   | Consumer                    |
| ------------------------ | ------------- | ------ | --------------------------- |
| `postgres_password`      | `999:999`     | `0440` | `db`, `provision` (GID 999) |
| `database_url`           | `10001:10001` | `0400` | `provision`, `api`          |
| `migration_database_url` | `10001:10001` | `0400` | `provision`, `migrate`      |
| `session_secret`         | `10001:10001` | `0400` | `api`                       |
| `owner_password`         | `10001:10001` | `0400` | `api`                       |
| `parsina_password`       | `10001:10001` | `0400` | `api`                       |

A wrong owner or mode fails closed at container start; it is not something to “fix” by making the
file world-readable. The directory must be outside the repository.

Host data paths should be root-owned and not world-writable. The PostgreSQL volume's `_data`
directory is normally owned by `999:999` with a restrictive mode; Docker manages it, so do not
`chown -R` it by hand. On a first start the volume path may not exist yet. The backup directory is
root-owned `0700` and outside the repository. The deployment checkout may be owned by the deploy
account, but it must not contain secret files; verify with `git status --ignored` and the
secret-file check above only if you understand the output, and never print file contents.

### 3.6 TLS material and Caddy configuration

```bash
# Mode A only; the tool reads the files, prints no key material, and issues nothing.
make tls-validate \
  CERT="$CHARSOOQ_TLS_DIR/current/fullchain.pem" \
  KEY="$CHARSOOQ_TLS_DIR/current/privkey.pem" \
  HOST="$CHARSOOQ_SITE_HOST" \
  CA_FILE="$CHARSOOQ_TLS_DIR/org-root.crt" \
  MIN_DAYS=30

make prod-caddy-validate
```

Healthy: `RESULT: PASS` from the validation tool and `Valid configuration` from the pinned Caddy
binary. Mode A needs `current` to point at one version directory; mode B has no `current` pair and
Caddy creates its local CA in `caddy_data` on first start. Do not run `prod-caddy-validate` against
unvalidated or placeholder material. The full intake, rotation, and rollback procedure is
[tls-certificate-lifecycle.md](tls-certificate-lifecycle.md).

### 3.7 DNS and client reachability

From a client on the approved VLAN:

```bash
getent ahosts '<approved-dns-name-or-ip>'
curl -sSI "http://<approved-dns-name-or-ip>/"    # before start: connection refused is expected
```

Healthy after start: the name resolves to the approved address; TCP `443` is reachable from the
approved client network; `80` redirects. For an IP SAN, there may be no DNS record; `CHARSOOQ_SITE_HOST`
must then be the literal address. Firewall/VLAN approval is owned by IT; this runbook does not change
it.

### 3.8 Compose structure with the real values

```bash
# The Make target always substitutes RFC 5737 documentation values.
make prod-config

# The direct command uses the exported real values. It still does not read
# secret file contents; it only interpolates the Compose file.
docker compose -f compose.production.yml config --quiet
```

Healthy: `production compose: structure valid (documentation values only)` from the Make target, and
exit 0 from the direct command with the real environment. The Make target is a structural smoke test,
not proof that the real values are correct. Neither check reads secret file contents or proves the
stack can start.

The direct command also needs `CHARSOOQ_API_IMAGE` and `CHARSOOQ_WEB_IMAGE`, because the Compose
file requires them: an unset image reference is an error, not a default. The Make target supplies
documentation-only digests.

### 3.9 Release images exist and match the approved commit

```bash
# The release path: both images come from one published release and are
# selected by digest. The digests are in the release body.
export CHARSOOQ_API_IMAGE='<registry>/charsooq-api@sha256:<digest>'
export CHARSOOQ_WEB_IMAGE='<registry>/charsooq-web@sha256:<digest>'

# Temporary host-build fallback, only from a clean approved commit:
# make prod-build

docker compose -f compose.production.yml pull api web
docker image inspect "$CHARSOOQ_API_IMAGE" --format '{{.Id}}'
docker image inspect "$CHARSOOQ_WEB_IMAGE" --format '{{.Id}}'

# Which commit each image was built from:
make prod-image-revision
```

Host/operator, state-changing (a pull or a build). The first-start commands below use
`--no-build`, so both images must exist before step 3. `CHARSOOQ_API_IMAGE` and `CHARSOOQ_WEB_IMAGE`
are required and have no default: an unset reference stops the stack instead of deploying whatever
is in the local cache. Record the digests and the commit SHA. If you cannot prove which commit
produced an image, pull the released digest; do not deploy an untracked image. The full procedure is
in [release-management.md](release-management.md).

## 4. First startup sequence

This is the only supported order. `provision` and `migrate` are not daemons; they must exit 0 before
the API is created. Do not start `api`, `web`, or `caddy` early.

| #   | Step                     | Executor       | Effect                                                  | Destructive? |
| --- | ------------------------ | -------------- | ------------------------------------------------------- | ------------ |
| 1   | Configuration validation | Host/operator  | Reads Compose and environment only                      | No           |
| 2   | Secret preparation       | Host/root      | Ownership/mode changes; no content read                 | No data loss |
| 3   | Start PostgreSQL         | Host/operator  | Creates/starts `db`; creates a new volume if absent     | No           |
| 4   | Database health          | Host/operator  | Read-only `pg_isready`                                  | No           |
| 5   | Provision roles          | Host/operator  | Creates/updates roles, rotates role passwords, grants   | No data loss |
| 6   | Migrate schema           | Host/operator  | Applies pending Alembic revisions under a lock          | Possibly     |
| 7   | Verify migration         | Host/operator  | Reads current revision                                  | No           |
| 8   | Bootstrap owner          | Host/operator  | Creates/updates the owner account; re-hashes if changed | No data loss |
| 9   | Start API                | Host/operator  | Starts FastAPI; waits for `/ready`                      | No           |
| 10  | Start web                | Host/operator  | Starts Next.js; healthchecks `/login`                   | No           |
| 11  | Start Caddy              | Host/operator  | Publishes `80`/`443`, terminates TLS                    | No           |
| 12  | Verify HTTPS             | Host + client  | Read-only TLS/HTTP probes                               | No           |
| 13  | Verify login and session | Client/browser | Read-only user flow                                     | No           |
| 14  | Verify web → API         | Host + client  | Read-only `/api/v1/*` probes                            | No           |

Before step 1, take a backup if an existing database will be migrated. On a fresh volume there is no
database to back up; record that explicitly.

### Step 1 — Configuration validation

```bash
make prod-config
docker compose -f compose.production.yml config --quiet
```

Host/operator, read-only. Expected: exit 0. The Make target supplies RFC 5737 documentation addresses;
the direct command interpolates the exported real values. Do not proceed if either fails.

### Step 2 — Secret preparation

```bash
sudo install -d -m 0700 -o root -g root /etc/charsooq/secrets
sudo chown 999:999 /etc/charsooq/secrets/postgres_password
sudo chown 10001:10001 /etc/charsooq/secrets/database_url \
  /etc/charsooq/secrets/migration_database_url /etc/charsooq/secrets/session_secret \
  /etc/charsooq/secrets/owner_password /etc/charsooq/secrets/parsina_password
sudo chmod 0440 /etc/charsooq/secrets/postgres_password
sudo chmod 0400 /etc/charsooq/secrets/database_url \
  /etc/charsooq/secrets/migration_database_url /etc/charsooq/secrets/session_secret \
  /etc/charsooq/secrets/owner_password /etc/charsooq/secrets/parsina_password
```

Host/root, state-changing. This only changes ownership/mode and directory existence; it never reads
or prints file contents. Do not run it blindly on a directory with unknown files, and never relax
permissions to “make it work”. The six files must already exist and contain the intended values.
`postgres_password` is readable by `db` and by `provision` (which joins GID 999); the other five are
readable by UID 10001 only.

### Step 3 — Start PostgreSQL

```bash
docker compose -f compose.production.yml up -d --wait --wait-timeout 120 db
docker compose -f compose.production.yml ps db
```

Host/operator, state-changing. Creates the container and, on a fresh host, the `pgdata` volume. Wait
for `healthy`; `starting` is not ready. If the volume exists but is corrupt, do not delete it: follow
[backup-and-recovery.md](backup-and-recovery.md).

### Step 4 — Database health

```bash
docker compose -f compose.production.yml exec -T db \
  pg_isready -U charsooq -d charsooq -h 127.0.0.1
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT 1;'
```

Container, read-only. Expected: `accepting connections` and `1`. These use the administrative role
over the container's local socket; no password is printed. If this fails, stop; do not run
provisioning or migrations against an unready database.

### Step 5 — Provision database roles

```bash
make prod-provision
```

Host/operator, state-changing (roles/grants; not application data). `docker compose run --rm provision`
starts `db` if needed and exits 0 only when the application and migration roles are ready. Expected
output ends with `provision-database-roles: application and migration roles are ready`. It is
idempotent and may rotate both role passwords to the values in the URLs; run it in a low-traffic
window if the API is already serving.

### Step 6 — Migrate schema

```bash
make prod-migrate
```

Host/operator, state-changing and potentially destructive. It uses only the migration credential,
holds the ChaharSooq advisory lock, and exits non-zero on failure or lock timeout. Expected:
`migrate: database is at head`. Take a verified backup first if the database already contains data
and the release includes a non-additive migration. Never start `api` after a failed migration.

### Step 7 — Verify migration result

```bash
docker compose -f compose.production.yml run --rm --no-deps migrate \
  sh -c 'cd backend/api && alembic current'
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT version_num FROM alembic_version;'
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT count(*) FROM pg_locks WHERE locktype = $$advisory$$;'
```

Container, read-only. Expected: one current revision, matching the DB row, and no advisory lock left
behind. `alembic current` also proves the migration credential works. Do not edit `alembic_version`
by hand.

### Step 8 — Bootstrap the owner (first deployment or credential change only)

```bash
make prod-bootstrap-owner
```

Host/operator, state-changing (account row only). Expected:
`bootstrap_owner: owner account '<username>' ensured`. It is idempotent, never calls `create_all`,
and refuses if the `admins` table is missing. It runs the `api` image with the `api` service's
dependencies, so it may also start `db` and the `migrate` one-shot; both are idempotent. Re-running it
after changing `owner_password` re-hashes the password and preserves the single-owner invariant. It
does not invalidate existing sessions; see [Compromised secret](#compromised-secret).

### Step 9 — Start the API

```bash
docker compose -f compose.production.yml up -d --no-build --no-deps \
  --wait --wait-timeout 180 api
docker compose -f compose.production.yml ps api
docker compose -f compose.production.yml exec -T api \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

Host/operator (Compose) + container (health request). Expected: status `healthy` and
`{"status": "ok"}`. `/ready` is the database-backed check; it is also the container healthcheck.
`--no-deps` is deliberate: `db` is already up and `migrate` has already completed. With the default
`make prod-up`, Compose enforces the same order automatically.

### Step 10 — Start the web tier

```bash
docker compose -f compose.production.yml up -d --no-build --no-deps \
  --wait --wait-timeout 180 web
docker compose -f compose.production.yml ps web
docker compose -f compose.production.yml exec -T web \
  node -e "fetch('http://127.0.0.1:3000/login').then(r=>{console.log(r.status);process.exit(r.status>=500?1:0)}).catch(()=>process.exit(1))"
```

Host/operator. Expected: `healthy` and an HTTP status below `500` (normally `200`). `web` was built
with `API_URL_INTERNAL=http://api:8000`; changing that value requires a rebuild, not a restart.

### Step 11 — Start Caddy

```bash
docker compose -f compose.production.yml up -d --no-build --no-deps caddy
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml port caddy 443
```

Host/operator. Expected: `caddy` is the only service with published ports, bound to
`CHARSOOQ_PROXY_BIND_IP`. Caddy has no Compose healthcheck; verify it from outside with step 12. If
`web` was recreated, restart Caddy so it re-resolves the upstream address.

### Step 12 — Verify HTTPS

```bash
SITE_HOST="$CHARSOOQ_SITE_HOST"
CA_FILE="$CHARSOOQ_TLS_DIR/org-root.crt"   # mode A; use the distributed public root in mode B

curl -sS --cacert "$CA_FILE" -o /dev/null -w '%{http_code}\n' "https://$SITE_HOST/login"
curl -sSI --cacert "$CA_FILE" "https://$SITE_HOST/login" | grep -i '^strict-transport-security'
curl -sSI "http://$SITE_HOST/" | sed -n '1p;/^[Ll]ocation:/p'
openssl s_client -connect "$SITE_HOST:443" -servername "$SITE_HOST" -CAfile "$CA_FILE" \
  </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -fingerprint -sha256 -ext subjectAltName
```

Host/client, read-only. Expected: `200`; `Strict-Transport-Security: max-age=31536000` with no
`includeSubDomains` or `preload`; `308` plus `Location: https://$SITE_HOST/`; a certificate whose SAN
is exactly `$SITE_HOST`, whose dates match the intake record, and whose fingerprint matches the
activated version. For an IP SAN omit `-servername` and verify with `-verify_ip`. Do not accept
`curl -k`, a browser warning, or a placeholder certificate as success.

### Step 13 — Verify login and session

Open `https://<site-host>/login` in a browser on an approved client.

| Check               | Expected                                                             |
| ------------------- | -------------------------------------------------------------------- |
| Page loads          | Persian RTL login page, no mixed-content or certificate warning      |
| Login               | Owner credentials from the approved secret succeed                   |
| Cookie              | `charsooq_session` is `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/` |
| Reload / navigation | Session survives a full page reload                                  |
| Logout              | Session is cleared and a protected page redirects to login           |
| Rate limiting       | Ten failed attempts in a minute return `429`, not a server error     |

If the page loads over plain HTTP or the cookie is missing, stop at the proxy/TLS layer; do not
“fix” it by changing cookie flags. The full auth model is
[authentication.md](../architecture/authentication.md).

### Step 14 — Verify web → API

```bash
curl -sS --cacert "$CA_FILE" "https://$SITE_HOST/api/v1/health"
curl -sS --cacert "$CA_FILE" "https://$SITE_HOST/api/v1/ready"
```

Host/client, read-only. Expected: `{"status":"ok"}` and `{"status":"ready"}` through the same-origin
Next rewrite. Then perform one real read (for example load the dashboard or a product page) and one
write (only if the release includes and approves it). A direct connection to `<host>:8000`,
`<host>:3000`, or `<host>:5432` from another host must fail.

## 5. Service lifecycle

Use the same exported environment for every Compose command. `make prod-ps` and `make prod-logs` are
thin wrappers; the direct commands below are equivalent and are what you should use when targeting
one service.

### 5.1 Per-service commands

| Service     | Start                                         | Stop                          | Restart                          | Status / health                                  | Logs                                         |
| ----------- | --------------------------------------------- | ----------------------------- | -------------------------------- | ------------------------------------------------ | -------------------------------------------- |
| `db`        | `docker compose … up -d --wait db`            | `docker compose … stop db`    | `docker compose … restart db`    | `docker compose … ps db`; `pg_isready`           | `docker compose … logs --tail=200 -f db`     |
| `provision` | `make prod-provision` (one-shot)              | not applicable (exits)        | `make prod-provision` (re-run)   | exit code 0; `docker compose … ps -a provision`  | `docker compose … logs --tail=200 provision` |
| `migrate`   | `make prod-migrate` (one-shot)                | not applicable (exits)        | `make prod-migrate` (re-run)     | exit code 0; `alembic current`                   | `docker compose … logs --tail=200 migrate`   |
| `api`       | `docker compose … up -d --no-deps --wait api` | `docker compose … stop api`   | `docker compose … restart api`   | `/health`, `/ready`, `ps api`                    | `docker compose … logs --tail=200 -f api`    |
| `web`       | `docker compose … up -d --no-deps --wait web` | `docker compose … stop web`   | `docker compose … restart web`   | `/login`, `ps web`                               | `docker compose … logs --tail=200 -f web`    |
| `caddy`     | `docker compose … up -d --no-deps caddy`      | `docker compose … stop caddy` | `docker compose … restart caddy` | `ps caddy`, `port caddy 443`, external TLS probe | `docker compose … logs --tail=200 -f caddy`  |

`…` stands for `-f compose.production.yml`. For a stopped service that still exists, `start <service>`
is the lightest command; for a missing container or a changed environment/image, use `up -d`.
`make prod-provision` and `make prod-migrate` use `docker compose run --rm`, so their output is on the
terminal and the container is removed afterwards; `docker compose logs` can only show them if they
were started by `prod-up`. Capture the command output when you run them manually. If a one-shot hangs,
`docker compose stop provision` or `stop migrate` cancels it; PostgreSQL rolls back an open
transaction when the connection closes, but investigate the cause before re-running.

### 5.2 What a restart affects

| Action              | Direct effect                                                               | Follow-up / risk                                                                                 |
| ------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Restart `db`        | PostgreSQL closes connections; `api` `/ready` fails; `web` may still render | Do not restart in a loop. Check disk/CPU/OOM and logs first. `provision`/`migrate` do not rerun. |
| Restart `provision` | Runs the idempotent provisioning transaction again                          | It may rotate role passwords to the URL values and change grants. Do it in a low-traffic window. |
| Restart `migrate`   | Starts a new one-shot and applies pending revisions                         | Advisory lock serializes runners; a failed revision stops the API release. Backup first.         |
| Restart `api`       | Brief 5xx/502 from `web`; `db` and `caddy` stay up                          | `restart` does not pick up changed env/secret files; recreate for those.                         |
| Restart `web`       | Brief 502 from Caddy; `api`/`db` stay up                                    | A restart keeps the container IP. A recreate can change it; restart `caddy` afterwards.          |
| Restart `caddy`     | TCP listener and TLS terminate for a few seconds                            | In-flight requests fail; `db`/`api`/`web` are untouched. Certificate changes need this.          |
| Restart everything  | Full outage                                                                 | Never the first response. Fix the failing layer; keep the rest serving.                          |

### 5.3 Restart vs. recreate vs. rebuild

| Operation    | What changes                                                               | Command pattern                                                        | When                                                   |
| ------------ | -------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------ |
| **Restart**  | Process state only; same container, same image, same env, same filesystem  | `docker compose … restart <service>`                                   | Crash recovery, certificate file swap, transient fault |
| **Recreate** | New container from the same image; env, secrets, ports, and mounts re-read | `docker compose … up -d --no-deps --force-recreate <service>`          | Secret/env/compose change, log-rotation adoption       |
| **Rebuild**  | New image from the current checkout, then recreate                         | `make prod-build` or `docker compose … build`, then `up -d --no-build` | Code change; only from an approved clean commit        |

`restart` is not a configuration reload. `up -d --no-deps <service>` recreates only if the service
definition or image changed; use `--force-recreate` when you know the container must be replaced.
Rebuilding on the Production host is a fallback, not the target release path; see section 6.

### 5.4 Stopping the stack

```bash
make prod-down
```

Host/operator, state-changing, **keeps all named volumes**. It stops and removes the containers and
the Compose networks. It is appropriate for a planned host maintenance window, not for “fixing” a
crash. To stop one service, use `stop <service>`; to stop traffic only, use `stop caddy`.

Never use `docker compose down -v`, `docker volume prune`, `docker system prune --volumes`, or
`docker volume rm charsooq-production_pgdata`. Those remove the database and/or Caddy state and turn a
short outage into a restore.

## 6. Update and release workflow

The target is: build once from an approved commit, publish it under a version tag and a commit-SHA
tag, push to the approved registry, and deploy that exact image **by digest**. `latest` is never a
Production release identity, and a tag is never the deployment reference: the digest is the
authoritative one. The registry, promotion mechanism, and deploy access are still open decisions;
until they exist, a host build from a clean approved commit is a temporary, recorded fallback, not
the target.

### 6.1 Release gates

Do not start an update unless all gates pass:

| Gate            | Evidence                                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------------------ |
| Approved commit | Git SHA; a published GitHub Release tagged `v<version>`; `git status --porcelain` empty in the deployment checkout |
| CI              | GitHub Actions `frontend`, `backend`, `migrations`, and `build` jobs green for that SHA                            |
| Staging         | The same SHA exercised in Staging, including frontend ↔ API integration and login                                  |
| Image identity  | Registry digest recorded for API and web; the image `revision` label matches the SHA (`make prod-image-revision`)  |
| Database review | Migration classified as none/additive/expand-contract; backup gate decided                                         |
| Backup          | A verified, encrypted, off-host dump from before the change; restore path known                                    |
| Rollback        | Previous API/web digests and the previous release record are available                                             |
| TLS             | Valid certificate for the site host; no expiry inside the change window                                            |
| Capacity        | Disk, memory, and database size checked; no active incident                                                        |
| Window          | Approved maintenance window and an operator who can roll back                                                      |

### 6.2 Build and record the artifact

The target path is the publishing workflow: publish a GitHub Release, and it builds both images from
that commit and records both digests in the release body. See
[release-management.md](release-management.md).

On the approved builder, from the release commit:

```bash
git rev-parse HEAD
# The fallback, only from a clean approved commit, when no registry is reachable:
make prod-build
docker image inspect "charsooq-api:<short-sha>" --format '{{.Id}}'
docker image inspect "charsooq-web:<short-sha>" --format '{{.Id}}'
```

Host/operator, state-changing (build artifacts only). Record: commit SHA, build time, both digests,
base image versions, and the operator. Do not build on the Production host from a dirty checkout. A
tag is not a commit identity: the isolated rehearsal found a pre-existing local image that predated
`provision_database_roles.py`. Pull the approved digest before the first start; never assume a
cached image matches the release.

### 6.3 Pre-change backup

Follow [backup-and-recovery.md](backup-and-recovery.md) section 5. At minimum:

1. Take an encrypted `pg_dump` custom-format archive.
2. Verify it by restoring into a scratch database (or at least `pg_restore --list`).
3. Copy it off-host and record its checksum and the current `alembic_version`.
4. Record the current image digests and certificate fingerprint.

If the backup cannot be verified, do not proceed.

### 6.4 Pull and verify the new images

```bash
docker compose -f compose.production.yml pull api web
docker image inspect "$CHARSOOQ_API_IMAGE" --format '{{index .RepoDigests 0}}'
docker image inspect "$CHARSOOQ_WEB_IMAGE" --format '{{index .RepoDigests 0}}'
make prod-image-revision
```

Host/operator, read-only after the pull. With registry digests, the inspect output must match the
release record, and the `revision` label must equal the approved commit SHA. If the registry requires
authentication, use the approved credential helper; never put a token on a command line or in Git.

### 6.5 Choose the migration path

| Change                                               | Migration needed?   | Release order / rule                                                                                                         |
| ---------------------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Application code, UI, config only                    | No                  | Deploy images; verify.                                                                                                       |
| New nullable column, new table, new index            | Yes, additive       | Expand migration first; old and new code must both tolerate it; then deploy code. Index creation can lock, so plan a window. |
| Backfill data                                        | Yes, data           | Separate, batched, idempotent step; monitor locks and runtime.                                                               |
| Rename, drop, narrow a type, add a strict constraint | Yes, incompatible   | Expand/contract over two releases; never in one step.                                                                        |
| Role/grant changes only                              | No Alembic revision | Run `make prod-provision`; recreate the consuming service if its URL changed.                                                |
| Base image, dependency, or Dockerfile change         | No Alembic revision | Rebuild, scan/record, deploy by digest.                                                                                      |

Apply migrations before the new API image:

```bash
make prod-migrate
docker compose -f compose.production.yml run --rm --no-deps migrate \
  sh -c 'cd backend/api && alembic current'
```

Host/operator, state-changing. `make prod-migrate` exits non-zero on failure; the API must not be
recreated until it succeeds. The advisory lock makes a concurrent manual run wait or time out rather
than race.

### 6.6 Update API, web, and proxy

```bash
docker compose -f compose.production.yml up -d --no-build --no-deps \
  --wait --wait-timeout 180 api
docker compose -f compose.production.yml up -d --no-build --no-deps \
  --wait --wait-timeout 180 web
docker compose -f compose.production.yml restart caddy
```

Host/operator, state-changing. Recreating `web` can change its `proxy` address; Caddy resolves
`web:3000` at configuration load, so restart Caddy after the web recreate. If only the API changed
and `web` was not recreated, a Caddy restart is not required, but running it is a short, safe outage
that removes stale upstream state. If the environment or Caddy configuration changed, replace the
restart with `up -d --no-deps caddy` so the new environment is read.

### 6.7 Verify the release

Repeat the HTTPS, login/session, and web → API verification in steps 12–14. Additionally:

```bash
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --since 15m api web caddy
docker compose -f compose.production.yml exec -T db \
  psql -U charsooq -d charsooq -tAc 'SELECT version_num FROM alembic_version;'
```

Expected: all long-running services `healthy` or `running`; no repeated 5xx, TLS, or upstream errors;
the migration revision matches the release record. Record the deployed SHA, digests, revision,
certificate fingerprint, verification results, and any warnings.

### 6.8 Rollback

Code rollback is not a database rollback. A previous image can read only a schema it understands.

**Code-only rollback (safe when the migration was additive and backward-compatible):**

```bash
export CHARSOOQ_API_IMAGE='<previous-api-digest>'
export CHARSOOQ_WEB_IMAGE='<previous-web-digest>'
docker compose -f compose.production.yml pull api web
docker compose -f compose.production.yml up -d --no-build --no-deps api web
docker compose -f compose.production.yml restart caddy
```

Host/operator, state-changing. Then repeat the verification in 6.7. Keep the migration in place; old
code must tolerate the expanded schema. Do not run `alembic downgrade` as a reflex.

**Rollback after an incompatible or failed migration:**

1. Stop traffic if data could be written in an unknown state: `docker compose … stop caddy`.
2. Preserve evidence: logs, `alembic_version`, failed revision, and a backup of the current database
   (if it is still readable). Do not delete the volume.
3. Restore the verified pre-change dump into a scratch database first and confirm the revision and
   row counts. If the Production database must be replaced, follow
   [backup-and-recovery.md](backup-and-recovery.md) section 6.
4. Start the previous image digests, then `caddy`, and verify.
5. Record the data-loss window (the dump point) in the incident log.

`alembic downgrade` is not the Production rollback plan: it can drop columns/tables or fail halfway,
it is not rehearsed for every revision, and it does not restore deleted or transformed data. A
forward fix plus a restore is the safe path when the migration is not backward-compatible.

### 6.9 Expand/contract for incompatible schema changes

Use three releases, not one:

1. **Expand**: add the new nullable column/table/index and dual-write or backfill in the background.
   Deploy code that writes both shapes and reads the old one. Rollback is safe: the old code ignores
   the new shape.
2. **Migrate**: backfill in bounded batches, verify counts and constraints, and switch reads to the
   new shape once the data is complete. Keep the old shape until no running code reads it.
3. **Contract**: after the old code is gone from every deployment and the rollback window has passed,
   drop the old column/table/constraint. This is one-way; take a fresh backup and record it.

Never combine expand and contract in one migration. A rename is an expand (new name) plus a contract
(drop old name), not a single `ALTER ... RENAME`.

## 7. Logging and monitoring

No monitoring agent, log shipper, or alerting service is added. The current stack exposes enough for
manual operation; external monitoring is required for paging and history.

### 7.1 Sources and commands

| Source                | Command                                                                           | What it shows                                                       |
| --------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Container logs        | `docker compose -f compose.production.yml logs --since 1h --tail=200`             | All services' stdout/stderr                                         |
| API logs              | `docker compose … logs --since 1h -f api`                                         | Requests, startup, migration/readiness errors; no secrets by design |
| Web logs              | `docker compose … logs --since 1h -f web`                                         | Next.js render, rewrite, and upstream errors                        |
| Caddy access/error    | `docker compose … logs --since 1h -f caddy`                                       | JSON access log on stdout; certificate/upstream errors              |
| PostgreSQL logs       | `docker compose … logs --since 1h -f db`                                          | Startup, connection, checkpoint, and fatal errors                   |
| Container health      | `docker compose … ps`; `docker inspect --format '{{.State.Health.Status}}' <id>`  | `healthy`/`unhealthy`/`starting` for db/api/web                     |
| Resource use          | `docker stats --no-stream`                                                        | Per-container CPU, memory, network, block I/O                       |
| Disk                  | `df -h /var/lib/docker`; `docker system df`                                       | Host and Docker usage; inode checks with `df -i`                    |
| Certificate           | `openssl s_client …`; `make tls-validate …`                                       | Served chain, SAN, dates; file-level validity                       |
| Database availability | `pg_isready`; `curl …/api/v1/ready`                                               | Listener and a real `SELECT 1` through the app                      |
| Backup success        | Artifact exists, decrypts, restores into scratch, checksum/off-host copy recorded | Manual until a scheduler is approved                                |

Caddy's default JSON access log excludes `Cookie`, `Set-Cookie`, `Authorization`, and
`Proxy-Authorization` unless `log_credentials` is enabled. The committed snippets never enable it, and
a static test guards that. The API does not log request bodies, passwords, session IDs, or database
URLs. Do not add a log format that prints headers or query strings containing credentials.

### 7.2 Rotation and retention

The Compose file sets `json-file` with `max-size: 10m` and `max-file: 5` for every service. That bounds
each container's local log at roughly 50 MB and keeps five files. Existing containers created before
this setting must be recreated once:

```bash
SERVICE=api   # replace with the service whose log settings must be adopted
docker compose -f compose.production.yml up -d --no-deps --force-recreate "$SERVICE"
```

Host/operator, state-changing (short outage for that service). Do not truncate a live PostgreSQL or
Caddy log as a routine action; fix rotation instead. Host-level log retention, central collection, and
the retention period are IT decisions. `docker compose logs` is not an audit log and is lost when a
container is removed.

### 7.3 Manual vs. external monitoring

| Signal                 | Current capability                         | Needs external monitoring?                               |
| ---------------------- | ------------------------------------------ | -------------------------------------------------------- |
| Container up/unhealthy | `docker compose ps`                        | Yes, for paging when nobody is watching                  |
| API/database readiness | `/health`, `/ready`                        | Yes, from a client on the approved network               |
| HTTPS/certificate      | `curl`, `openssl s_client`, `tls-validate` | Yes, for expiry alerts and multi-client reachability     |
| Disk/inodes            | `df`, `docker system df`                   | Yes, threshold alert                                     |
| CPU/memory             | `docker stats`                             | Yes, history/trend and alerting                          |
| Logs                   | `docker compose logs`                      | Yes, for retention/search and error-rate alerting        |
| Backup success         | Manual checklist                           | Yes, a job that fails loudly; none is committed          |
| Certificate renewal    | Manual calendar                            | Yes, an owner and a 30/14/7-day escalation path          |
| Database performance   | No slow-query log configured               | Yes, if the organization requires query-level visibility |

The external tool, alert channel, and owner are open IT decisions. Do not add a new always-on service
to the Production Compose file for monitoring without a documented need and an ADR.

## 8. Incident response

Common rules for every incident:

1. **Declare and freeze.** Name an incident lead, record UTC time, stop unrelated changes and
   deployments.
2. **Contain before repairing.** Stop traffic (`stop caddy`) or stop writers (`stop api web`) rather
   than deleting data. Keep the failing container and its logs.
3. **Collect evidence without secrets.** `docker compose ps`, `logs --since`, selected `docker inspect`
   fields, `df`, `docker system df`, `pg_isready`, `alembic current`. Never paste secret files,
   `docker inspect` environment, cookies, Authorization headers, or full database URLs.
4. **Back up before destructive recovery.** If data is readable, take a dump. If the volume is
   corrupt, copy what is readable before removing anything.
5. **Recover one layer at a time.** Database → API → web → Caddy. Verify each gate before moving on.
6. **Verify and record.** Repeat the startup/login/HTTPS checks, then record impact, timeline, root
   cause, data-loss window, and follow-ups.

### Database unavailable

**Detect:** `ps db` not `healthy`; `/ready` fails; API logs show connection errors.
**Contain:** stop `caddy` if requests could produce misleading writes; do not restart in a loop.
**Evidence:** `ps db`, `logs db`, `docker inspect` state/exit/OOM, `df -h`, `df -i`, `free -h`,
`pg_isready`, host `dmesg` if permitted.
**Recover:** fix disk/memory/config; restart `db` once and wait for `healthy`; if the volume is
corrupt, follow [backup-and-recovery.md](backup-and-recovery.md) section 7.
**Verify:** `pg_isready`, `SELECT 1`, `/ready`, login, write/read smoke test.
**Do not:** remove `pgdata`, run `initdb` over it, or run `down -v`.

### API crash loop

**Detect:** `ps api` restarting or `unhealthy`; `web` returns 502; logs repeat a startup error.
**Contain:** leave Caddy/DB up; stop repeated restart attempts; preserve logs.
**Evidence:** `logs --tail=300 api`, exit code and `OOMKilled` from selected `docker inspect` fields,
secret file `stat` (not contents), `pg_isready`, `/ready`.
**Recover:** fix configuration/secret permissions/database reachability; recreate (`up -d --no-deps
--force-recreate api`) only after the cause is known.
**Verify:** `healthy`, `/health`, `/ready`, login.
**Do not:** run `alembic downgrade`, delete the API container's filesystem, or change multiple
variables at once.

### Web crash loop

**Detect:** `ps web` restarting; Caddy returns 502; Next logs show a startup or render error.
**Contain:** keep DB/API up; stop Caddy if the error page is misleading users.
**Evidence:** `logs web`, `ps web`, `docker inspect` state, `API_URL_INTERNAL` value (not a secret),
API health, `docker network inspect` for `edge`.
**Recover:** fix the API dependency or the build-time API URL, rebuild if the URL changed, recreate
`web`, then restart `caddy`.
**Verify:** `/login` < 500, browser login, `/api/v1/health`.
**Do not:** point the browser directly at `api:8000` or publish `web` on a host port.

### Caddy failure

**Detect:** `ps caddy` not running; browser connection refused; logs show config/certificate/listener
errors.
**Contain:** keep `web`/`api`/`db` running.
**Evidence:** `logs caddy`, `make prod-caddy-validate`, `docker compose config --quiet`, `ss -ltnp`
for 80/443, `stat` of the config/cert mounts, `caddy_data` writability.
**Recover:** fix the Caddyfile/mount/environment/certificate; `restart caddy` for a certificate or
process fix, `up -d --no-deps caddy` for an environment/config change.
**Verify:** HTTPS status, HSTS, redirect, served fingerprint, access log.
**Do not:** delete `caddy_data`/`caddy_config`, disable TLS, or switch to a placeholder certificate.

### Certificate expiration

**Detect:** browser warning; `openssl s_client` shows `notAfter` in the past; `make tls-validate`
fails the 30-day threshold.
**Contain:** treat as an outage; do not bypass validation or tell users to click through.
**Evidence:** served certificate dates/SAN/fingerprint, `tls-validate`, current/previous version
directories, renewal ticket.
**Recover:** install and activate the renewed pair through
[tls-certificate-lifecycle.md](tls-certificate-lifecycle.md), validate, restart Caddy, verify the
served fingerprint. If no valid material exists, plan a maintenance window with IT; do not run HTTP.
**Do not:** disable HSTS, use `curl -k` as acceptance, or install an unvalidated pair.

### Disk full

**Detect:** `df -h` at 100%; PostgreSQL write errors; containers exit; Caddy cannot write state.
**Contain:** stop non-essential writes; do not delete volumes or the database.
**Evidence:** `df -h`, `df -i`, `docker system df`, `du -xh /var/lib/docker | sort -h | tail`,
per-container log sizes, PostgreSQL log errors.
**Recover:** free space safely: remove dangling images (`docker image prune`), unused build cache
(`docker builder prune`), and old stopped non-data containers after collecting their logs; rotate or
recreate containers to apply log limits; if `pgdata` filled the disk, free space, restart `db`, verify.
**Do not:** run `docker system prune --volumes`, `docker volume prune`, delete `pgdata`, or truncate a
live database file.

### Failed migration

**Detect:** `make prod-migrate` exits non-zero; `api` was not recreated; logs show a SQL/permission/lock
error.
**Contain:** do not start the new API; keep the old API if it is still running; stop writes if the
schema is in an unknown state.
**Evidence:** migration output (the primary evidence for a `run --rm` container), `logs migrate` if
started by `prod-up`, `alembic current`, `alembic heads`, `alembic_version` row, `pg_locks` for
advisory locks, role ownership.
**Recover:** fix the revision or role and re-run `make prod-migrate`; if the migration was destructive
or partially applied outside a transaction, restore the pre-change dump into a scratch database,
verify, then restore Production per the backup runbook.
**Verify:** `alembic current` equals head; `/ready`; read/write smoke test.
**Do not:** edit `alembic_version`, run `alembic downgrade` blindly, or start the API to “see if it
works”.

### Failed provisioning

**Detect:** `make prod-provision` exits non-zero; `migrate`/`api` never start; logs name a role,
permission, or ownership failure.
**Contain:** leave the database running; do not start API against unprovisioned roles.
**Evidence:** provisioning output (it is redacted and is the primary evidence for a `run --rm`
container), `logs provision` if started by `prod-up`, `stat` of the three secret files, `\du` and
`\dn+` as admin (no passwords), whether both URLs target the same database with different roles.
**Recover:** fix ownership/mode or the URL role names, then re-run `make prod-provision`. If an object
is owned by an unexpected role, stop and investigate; do not mass-`ALTER OWNER`.
**Verify:** output says both roles ready; `migrate` succeeds; API `/ready` works.
**Do not:** grant superuser to the app role, reuse one URL for both roles, or make
`postgres_password` world-readable.

### Web cannot reach the API

**Detect:** browser gets 502/500 from `/api/*`; web logs show `ECONNREFUSED api:8000`; login fails.
**Contain:** keep Caddy up; do not expose the API directly.
**Evidence:** `docker compose exec -T web node -e "..."` to `http://api:8000/health`, `ps api`,
`logs api`, `docker network inspect` for `edge`, `API_URL_INTERNAL`, Next rewrite config.
**Recover:** start/fix `api`; ensure both are on `edge`; if `API_URL_INTERNAL` changed, rebuild `web`
(the value is baked at build time) and recreate it; restart `caddy` if `web` was recreated.
**Verify:** `/api/v1/health` and `/api/v1/ready` through the site, then login.
**Do not:** add `api` to the `proxy` network or publish `api:8000`.

### Caddy will not start

**Detect:** `ps caddy` exited/restarting; logs show a config, certificate, mount, or bind error.
**Contain:** keep the rest of the stack running.
**Evidence:** `logs caddy`, `make prod-caddy-validate`, `docker compose config --quiet`, `ss -ltnp`,
`readlink -f "$CHARSOOQ_TLS_DIR/current"`, `stat` of config/cert paths.
**Recover:** fix the failed input; use `up -d --no-deps caddy` for env/mount changes and `restart
caddy` for a certificate swap. If `caddy_data` is lost, treat it as a security incident and follow the
TLS runbook; do not silently create a new CA.
**Verify:** `Valid configuration`, HTTPS status, HSTS, redirect, served fingerprint.
**Do not:** remove volumes, bind `0.0.0.0`, disable TLS, or start with a placeholder certificate.

### Service will not start after a restart

**Detect:** one service is `exited` or `restarting` after a host/daemon restart; dependent services
return 502.
**Contain:** start from the bottom (db → api → web → caddy), not all at once.
**Evidence:** `ps -a`, `logs --tail=200`, selected `docker inspect` exit/OOM fields, `df`, image
presence, env/secret `stat`, dependency health.
**Recover:** start `db`, wait `healthy`; run `provision`/`migrate` if this is a new volume; start
`api`, wait; start `web`; start `caddy`. Use `up -d --no-deps` for each layer.
**Verify:** the same gates as the first startup.
**Do not:** `down -v`, recreate the database volume, or start Caddy before web is healthy.

### Compromised secret

**Detect:** confirmed or suspected exposure of a secret file, database URL, owner password, session
secret, Parsina password, certificate key, or host access.
**Contain:** revoke the credential if the source supports it; stop external access if needed; preserve
evidence without printing the value; open a security incident.
**Evidence:** which file/credential, how and when it leaked, affected hosts/services, logs around the
window (redacted), current role list (no passwords).
**Recover:**

- **Application/migration DB password:** update the corresponding URL file atomically, run
  `make prod-provision` (it rotates the role password to the URL value), recreate `api` and/or run the
  next `migrate`; verify the old password fails and the new one works.
- **Owner password:** update `owner_password`, run `make prod-bootstrap-owner`; it re-hashes. To
  invalidate existing sessions, delete `admin_sessions` rows with an approved, backed-up SQL action;
  otherwise old sessions remain until expiry.
- **Session secret:** replace the file and recreate `api`. Note: sessions are opaque tokens stored as
  hashes; `SESSION_SECRET` is validated but not currently used to sign them, so rotating it alone does
  not invalidate sessions. Delete `admin_sessions` rows for a true logout-all.
- **Administrative PostgreSQL password:** follow [section 9.4](#94-administrative-postgresql-password-rotation).
  A file edit plus restart does **not** rotate the role password on an existing volume; use
  `psql`'s `\password` path, verify the new credential over TCP, then atomically replace the secret
  file and run `make prod-provision`. Keep the old secret until the new one is verified.
- **Parsina password:** update `parsina_password`, recreate `api`; disable the integration if it
  cannot be rotated immediately.
- **TLS private key / CA key:** follow the TLS incident and restore procedures; a leaked internal CA
  root key requires reissuing trust, not a silent CA replacement.

**Verify:** the old credential fails, the new one works, login/API/DB are healthy, logs show no further
use of the old value.
**Do not:** print the secret in a ticket/chat, commit a replacement, reuse the same value across
environments, or “temporarily” disable authentication/TLS.

### Corrupted database volume

**Detect:** PostgreSQL will not start; `pg_isready` fails; logs show checksum, I/O, or `initdb` errors.
**Contain:** stop `api`, `web`, and `caddy`; leave `db` stopped; do not run `initdb`, `pg_resetwal`, or
`down -v`.
**Evidence:** `logs db`, `df`, `dmesg` (if permitted), volume mount state, last successful backup and
its checksum, current `alembic_version` if readable.
**Recover:** preserve a read-only copy of the volume if possible, then follow
[backup-and-recovery.md](backup-and-recovery.md) section 7. Restore into a scratch volume/database
first; only then replace Production data. If no verified backup exists, declare data loss and involve
the owner; do not improvise.
**Verify:** `pg_isready`, revision, row counts, sequence sanity, `/ready`, login, spot-check records.
**Do not:** delete the volume before evidence is preserved, or restore directly over the only copy.

### Lost Caddy internal CA data

**Detect:** HTTPS clients suddenly distrust the site; `caddy_data` is missing/empty; Caddy generated a
new root; logs show a new CA.
**Contain:** treat as a security incident. Keep `caddy_data` stopped and preserve what remains; do not
distribute a new root silently.
**Evidence:** current served certificate and root fingerprint, `caddy_data` listing (public certs
only), backup availability, last recorded root fingerprint, client error details.
**Recover:** restore `caddy_data` from the encrypted backup and verify the root fingerprint before
starting Caddy; if no valid backup exists, generate a new CA, distribute the new root through IT,
expect client warnings until distribution completes, and record the incident. See
[tls-certificate-lifecycle.md](tls-certificate-lifecycle.md) sections 4.4 and 7.5.
**Verify:** handshake with the expected root, served leaf, HSTS, login.
**Do not:** bypass TLS validation, disable HSTS, or copy `root.key` anywhere.

### Failed deployment

**Detect:** a release step exits non-zero; API/web are half-updated; health or login verification
fails.
**Contain:** stop further steps; stop Caddy if users would see an inconsistent UI; keep the old
containers/images and the database.
**Evidence:** release record, step output, `ps`, logs, image digests, `alembic current`, backup
checksum, time of first failure.
**Recover:** if the migration succeeded and is backward-compatible, roll back API/web digests and
restart Caddy; if the migration is incompatible, restore the pre-change dump per the backup runbook,
then start the previous images; forward-fix only with a reviewed change.
**Verify:** full HTTPS/login/API/DB matrix; record data-loss window.
**Do not:** delete the database volume to “start clean”, deploy an untracked rebuild, or mix a new API
with an old web build.

## 9. Security and operational safety

### 9.1 Makefile targets with side effects

| Target                                                                                    | Effect                                                                 | Safe for Production?   | Never run when                                               |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------ |
| `db-up`, `db-migrate`, `db-bootstrap-owner`, `db-seed`, `db-seed-parsina`, `db-seed-demo` | Dev database setup/migration/seeding; `db-seed` also uses `create_all` | No                     | `DATABASE_URL` could point at Staging/Production             |
| `db-clear-products`                                                                       | **Deletes** products and competitor listings in the dev database       | No                     | Any non-development database; no backup                      |
| `db-sync-dev-to-staging`, `db-seed-demo-staging`                                          | Writes Staging Neon; reads `backend/api/.env.staging`                  | Staging only           | A Production destination; a shared credential                |
| `db-migrate-prod`, `db-seed-prod`, `db-sync-dev-to-prod`, `sync-prod`, `dev-to-prod`      | Disabled; print a reason and exit non-zero                             | No (fail closed)       | Re-enabling without an approved ADR and backup gate          |
| `docker-up`, `docker-down`, `docker-logs`                                                 | Development Compose stack                                              | No                     | On the Production host                                       |
| `clean-cache`, `clean-build`                                                              | Remove local build/test caches                                         | Not applicable         | On the Production host unless the path is understood         |
| `prod-config`                                                                             | Compose structure check; no secret contents read                       | Yes                    | —                                                            |
| `prod-build`                                                                              | Builds API/web images from the current checkout                        | Only from approved SHA | Dirty tree, unapproved branch, or ad-hoc rebuild             |
| `prod-pull`                                                                               | Pulls the released API/web images by digest                            | Controlled window      | Without the release digests recorded                         |
| `prod-image-revision`                                                                     | Prints the commit in each image's `revision` label                     | Yes (read-only)        | —                                                            |
| `prod-up`                                                                                 | Starts the full stack from the released images; runs provision/migrate | Controlled window      | Without a backup, without real values, during an incident    |
| `prod-provision`                                                                          | Idempotent roles/grants; may rotate role passwords                     | Controlled window      | API traffic if a URL changed and consumers are not recreated |
| `prod-migrate`                                                                            | Applies pending schema/data migrations                                 | Controlled window      | Without a verified backup for non-additive changes           |
| `prod-bootstrap-owner`                                                                    | Creates/updates the owner; may start `db`/`migrate` dependencies       | Controlled window      | An unmigrated database; an unreviewed owner password change  |
| `prod-down`                                                                               | Stops/removes containers and networks; keeps volumes                   | Planned outage         | As a crash fix; during writes without a plan                 |
| `tls-activate`, `tls-rollback`                                                            | Atomically switches the active certificate pair                        | Controlled window      | Unvalidated material; without a recorded previous version    |
| `prod-caddy-validate`                                                                     | Runs `caddy validate` in the pinned image                              | Yes (read-only)        | Without real TLS material in `organization` mode             |
| `deploy-api`                                                                              | Deploys Staging to FastAPI Cloud                                       | No (Staging)           | For Production                                               |

No target in this repository runs `down -v`, removes a named volume, or deletes `pgdata`. If a future
change adds one, it needs an explicit approval and a backup/restore runbook update.

### 9.2 Access boundaries

- **Docker socket:** no container mounts `/var/run/docker.sock`. The host operator's membership in the
  `docker` group is root-equivalent; restrict it to named operators and audit membership.
- **Networks:** `backend` is `internal: true`; `db` has no route out. `caddy` is only on `proxy` and
  cannot reach `api`, `db`, `provision`, or `migrate`. `web` is the only bridge between `proxy` and
  `edge`. Do not add a service to `edge` without treating it as able to spoof a client address.
- **Secrets:** file-backed, read-only at `/run/secrets`; only the consuming service mounts each file.
  The API never receives the admin or migration credential; the migration runner never receives the
  admin password or the application URL. Never put a secret in Compose, an image, a log, a command
  line, or a ticket.
- **Host paths:** `/etc/charsooq` and its subdirectories are root-owned, `0700`; certificate keys are
  `0600`; secret files are `0400`/`0440`. Backups live outside the repository, encrypted, `0700`/`0600`.
- **Images:** base images are pinned (`python:3.12.16-slim-bookworm`, `uv:0.12.0`,
  `node:22.23.5-bookworm-slim`, `postgres:18.6-trixie`, `caddy:2.11.9-alpine`). The application image
  references have **no default**: `CHARSOOQ_API_IMAGE`/`CHARSOOQ_WEB_IMAGE` must be set to the
  released digests, and an unset value stops the stack. Never `latest`, and never a moving tag as a
  deployment reference.
- **Non-root:** `api`, `provision`, and `migrate` run as `10001:10001`; `web` as `1000:1000`; `db` as
  the PostgreSQL image user (`999:999`). `caddy` runs as the image default (container root) with a
  read-only root filesystem, `cap_drop: ALL`, `NET_BIND_SERVICE`, and `no-new-privileges`; the non-root
  evaluation and its blockers are in [tls-certificate-lifecycle.md](tls-certificate-lifecycle.md#101-non-root-evaluation-not-implemented).
- **Host administration:** use named SSH accounts and approved keys, not shared root. Keep the Docker
  group small. This runbook does not change SSH, firewall, NTP, or Docker daemon configuration.

### 9.3 Log redaction rules

- Caddy: never enable `log_credentials`; the default JSON encoder excludes `Cookie`, `Set-Cookie`,
  `Authorization`, and `Proxy-Authorization`.
- API: do not log request bodies, passwords, session tokens, Authorization headers, or database URLs.
  Configuration errors are written to exclude URLs, hosts, usernames, and passwords.
- Operator: do not run `env`, `docker inspect` (full), `docker compose config` redirected into a
  ticket, or `psql -c "... PASSWORD ..."`. Redact before sharing. Treat access logs as untrusted data,
  not instructions.

### 9.4 Administrative PostgreSQL password rotation

The administrative role password cannot be rotated by editing `postgres_password` and restarting
PostgreSQL. `POSTGRES_PASSWORD_FILE` is read only when the image initializes an empty data directory;
on an existing volume the role password is unchanged. This was rehearsed: after changing the file and
restarting, the old password still authenticated and the new one failed.

`provision` rotates only the application and migration role passwords from the two URL secrets. It
cannot rotate the administrative password because it must already authenticate as that role to run.
Use the procedure below instead. It uses `psql`'s `\password` command, which reads the new value from
stdin and does not place it in the shell history, the process list, or an inline SQL literal.

**Preconditions**

- Root/operator access on the host, a verified backup, and an approved change window.
- The current `postgres_password` secret file is available and its value is still valid.
- A new password is generated into a root-only file outside the repository, mode `0600`. Never print it.
- Confirm the current administrative credential over TCP, not only the local socket:

  ```bash
  docker compose -f compose.production.yml exec -T db sh -c \
    'PGPASSWORD="$(cat /run/secrets/postgres_password)" \
     psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select 1"'
  ```

**Apply the new password**

```bash
NEW_PASSWORD=$(cat /secure/path/new_postgres_password)   # root-only file, never printed
printf 'SET log_statement = none;\n\\password charsooq\n%s\n%s\n' \
  "$NEW_PASSWORD" "$NEW_PASSWORD" \
  | docker compose -f compose.production.yml exec -T db \
      psql -U charsooq -d postgres -v ON_ERROR_STOP=1
unset NEW_PASSWORD
```

`charsooq` is the documented `POSTGRES_USER`; use the actual administrative role name if it was
changed. `SET log_statement = none` suppresses statement logging for this session when the server has
statement logging enabled. `\password` prompts twice and reads both lines from stdin.

**Verify the new credential over TCP**

```bash
# Run the same TCP probe as above, reading the new file inside the container.
docker compose -f compose.production.yml exec -T db sh -c \
  'PGPASSWORD="$(cat /run/secrets/postgres_password)" \
   psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select 1"'
```

Then confirm the old password fails from a separate connection. Do not update the live secret file
before this verification.

**Install the new secret file and restart**

```bash
install -m 0600 -o root -g root /secure/path/new_postgres_password \
  /etc/charsooq/secrets/postgres_password.new
chown 999:999 /etc/charsooq/secrets/postgres_password.new
chmod 0440 /etc/charsooq/secrets/postgres_password.new
mv -f /etc/charsooq/secrets/postgres_password.new /etc/charsooq/secrets/postgres_password
docker compose -f compose.production.yml restart db
```

Keep the old password available until the new one is verified. The restart does not re-apply the file
to an existing volume; it only proves the role password persists.

**Confirm the stack and roll back if needed**

```bash
make prod-provision
docker compose -f compose.production.yml ps db api
```

`make prod-provision` connects with the new administrative password and converges the application and
migration grants. If the new password fails after `ALTER ROLE` was applied, do not rely on the file:
re-apply the old password with `\password` (the old secret must be retained or recovered from the
secret custodian), restore the old file atomically, restart `db`, and run `make prod-provision`. If the
old secret is gone, restore it from the custodian before proceeding; do not restart and hope the image
re-applies the file.

## 10. Required before go-live (IT and owners)

Every item is a blocker, not a default. The full list is in
[deployment.md](../architecture/deployment.md#open-decisions-owned-by-it); this is the operational
subset.

| #   | Input                                                      | Needed for                                              |
| --- | ---------------------------------------------------------- | ------------------------------------------------------- |
| 1   | Approved fixed internal IP                                 | `CHARSOOQ_PROXY_BIND_IP`                                |
| 2   | Internal DNS name or approved IP SAN                       | `CHARSOOQ_SITE_HOST` and the certificate SAN            |
| 3   | Ports 80/443 free and permitted inbound                    | HTTPS and the redirect                                  |
| 4   | IPv6 decision                                              | Firewall/listener expectations                          |
| 5   | Docker address pools and conflict-free `edge` subnet       | `CHARSOOQ_EDGE_SUBNET`, `CHARSOOQ_WEB_EDGE_IP`          |
| 6   | Firewall/VLAN policy for clients                           | Reachability                                            |
| 7   | CA type, issuance, renewal, and root distribution          | TLS mode, renewal owner, client trust                   |
| 8   | NTP source and owner                                       | Certificate/session validity and log correlation        |
| 9   | Registry, artifact promotion, and deploy access            | Immutable image digests and a controlled release        |
| 10  | Backup destination, tool, encryption, key custody, RPO/RTO | Backup and restore                                      |
| 11  | Monitoring/alert channel and owner                         | Paging, history, expiry and backup failure alerts       |
| 12  | Secret custodian and rotation schedule                     | Secret provisioning and incident response               |
| 13  | Migration approval and backup gate                         | Who may run `prod-migrate` and when                     |
| 14  | Administrative password rotation procedure                 | The image does not rotate it on restart (see section 8) |
| 15  | Maintenance window and rollback authority                  | Any release or certificate change                       |

If any item is unknown, the safe state is **not started**, not a guessed configuration.

## 11. Verification performed for this task

All checks were offline or read-only. No connection was made to `market-linux`, no Production stack
was started, no database was opened, and no secret or `.env` file was read.

| Check                                                     | Result                                                                                                                                |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `make prod-config` after adding log rotation              | Pass: structure valid (documentation values only)                                                                                     |
| Targeted Compose/proxy tests                              | 23 passed (coverage gate fails only because the subset is not the full suite)                                                         |
| Isolated backup/restore rehearsal                         | Pass on synthetic data; restore-before-provision, ownership, grants, and default privileges verified (see backup-and-recovery.md 7.5) |
| Administrative password rotation rehearsal                | Pass: file change + restart did not rotate; `psql \password` did; new credential verified over TCP and across restart                 |
| Command/path audit against Makefile, Compose, Dockerfiles | Targets, service names, volumes, and script paths verified                                                                            |
| Secret exposure scan of new docs                          | No secret values; placeholders only                                                                                                   |
| Dangerous-command scan                                    | No routine `down -v`, prune, or volume removal; only the clearly gated drill cleanup and the incident-only corrupt-volume path        |

Release-specific checks (see [release-management.md](release-management.md)):

| Check                                                  | Result                                                                                                                                                                                   |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make prod-build`                                      | Pass: both images built from this checkout and stamped with the commit SHA                                                                                                               |
| `docker image inspect` on both built images            | The `revision` label equals the commit that built them; `make prod-image-revision` prints it                                                                                             |
| `docker compose config` with the image variables unset | Fails closed with a named error instead of defaulting to a mutable local tag                                                                                                             |
| `docker compose config` with digest references         | API, `provision`, `migrate`, and web resolve to the same published image                                                                                                                 |
| Release-path build with `--provenance=mode=max --sbom` | Both images are built with the provenance and SPDX SBOM attestations enabled. The attestations inside a _published_ index have not been observed yet, because nothing has been published |
| Workflow YAML parsed; every `run:` script checked      | No syntax error; the release-body update was exercised against a stubbed `gh` and is idempotent                                                                                          |

Not run, and why:

- `make prod-up`, `prod-provision`, `prod-migrate`, `prod-bootstrap-owner`, `prod-caddy-validate`: would
  start or configure the Production stack / read real material.
- `make tls-validate`/`tls-activate`: would read real certificate/private-key material.
- Any `docker compose` command against `market-linux`: the host was not contacted.
- A live login, HTTPS handshake, or database query: no real environment exists in this task.
- Publishing a release or pushing an image: the release workflow was never executed, and no image
  was pushed to any registry.
