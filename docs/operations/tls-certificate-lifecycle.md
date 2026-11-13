# TLS certificate lifecycle and first-deployment runbook

Status: **design and offline verification only**. Nothing in this document has been run against
`market-linux`, no real certificate or private key exists in the repository, and no secret was read.
Every command below is written for the operator who performs the change; the repository does not run
them.

Architecture and rationale live in [ADR 012](../adr/012-internal-reverse-proxy-and-tls.md) and
[deployment.md](../architecture/deployment.md#reverse-proxy-tls-and-exposure). This file is the
procedure: install, validate, rotate, roll back, back up, restore, monitor, and verify the first
Production start.

## 1. What exists today

| Component         | Location                                                                         | Notes                                                |
| ----------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Proxy / TLS       | `caddy:2.11.9-alpine` (`caddy` service)                                          | The only published ports; the only TLS terminator    |
| Caddy config      | [`deploy/caddy/`](../../deploy/caddy/)                                           | Committed; mounted read-only at `/etc/caddy`         |
| Organization TLS  | `${CHARSOOQ_TLS_DIR}` (default `/etc/charsooq/tls`)                              | Outside Git; mounted read-only at `/etc/caddy/certs` |
| CA + issued certs | named volume `charsooq-production_caddy_data`                                    | `/data` in the container; sensitive state            |
| Autosaved config  | named volume `charsooq-production_caddy_config`                                  | `/config`; `/config/caddy/autosave.json`             |
| Validation tool   | [`deploy/tls/validate_certificate.py`](../../deploy/tls/validate_certificate.py) | Offline; no secrets printed; no issuance             |
| Activation tool   | [`deploy/tls/activate_certificate.py`](../../deploy/tls/activate_certificate.py) | Stages, validates, and atomically switches `current` |
| Compose           | [`compose.production.yml`](../../compose.production.yml)                         | Caddy is on `proxy` only; no route to API/database   |

The request path is `client → Caddy → web → /api/* → api → db`. Caddy has no route to FastAPI or
PostgreSQL, no Docker socket, a read-only root filesystem, all capabilities dropped except
`NET_BIND_SERVICE`, and `admin off`.

### 1.1 Two TLS modes

| Mode            | `CHARSOOQ_TLS_MODE`      | Material                                                             | Client trust                                      | Owner of renewal                     |
| --------------- | ------------------------ | -------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------ |
| Organization CA | `organization` (default) | `fullchain.pem` + `privkey.pem` from the organization or a public CA | The issuing CA must already be trusted by clients | The organization (manual by default) |
| Caddy local CA  | `internal-ca`            | Generated and stored in `caddy_data`                                 | Caddy's root CA must be installed on every client | Caddy (automatic)                    |

Mode A (organization) is preferred when an internal CA exists. Mode B (internal CA) exists so TLS is
possible without one, at the cost of distributing a private root CA to every client.

## 2. Caddy 2.11.9 behavior this runbook relies on

These points were verified offline with the official 2.11.9 binary (SHA-512 checked against the
release checksums) in a temporary directory. They are not assumptions.

| Fact                                  | Verified behavior                                                                                       |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Data layout (internal CA)             | `/data/caddy/pki/authorities/local/root.crt`, `root.key`, `intermediate.crt`, `intermediate.key`        |
| Issued leaves (internal CA)           | `/data/caddy/certificates/local/<host>/<host>.crt`, `.key`, `.json`                                     |
| Root CA lifetime                      | 10 years (`3600d`)                                                                                      |
| Intermediate lifetime                 | 7 days (`7d`), rotated by Caddy                                                                         |
| Internal leaf lifetime                | 12 hours, renewed automatically by Caddy                                                                |
| Autosave                              | `/config/caddy/autosave.json` is written even with `admin off`                                          |
| `caddy reload` with `admin off`       | Refused: `dial tcp [::1]:2019: connect: connection refused`                                             |
| `SIGUSR1` with `caddy run --config …` | Reloads the config in-process without a restart                                                         |
| `caddy validate`                      | Fails on a missing certificate/key file and on a key mismatch (`private key does not match public key`) |
| HTTP→HTTPS redirect                   | `308 Permanent Redirect` with `Location: https://<host>/`                                               |

`caddy_data` is **state, not cache**. It holds private keys and issued certificates. Deleting it is
not a repair; for `internal-ca` it replaces the CA and breaks every trusting client.

## 3. Mode A — organization-issued certificate

### 3.1 Material, layout, and permissions

The directory is bind-mounted read-only and contains versioned pairs behind **one** symlink:

```text
/etc/charsooq/tls/                  root:root 0700, outside Git
├── current -> versions/<stamp>     the only pointer Caddy reads
├── versions/
│   ├── <older-stamp>/fullchain.pem + privkey.pem   kept for rollback
│   └── <current-stamp>/fullchain.pem + privkey.pem
└── org-root.crt                    organization root, public, for validation only
```

| Host path (default)                                | Container path                                    | Content                                     | Owner/mode                   |
| -------------------------------------------------- | ------------------------------------------------- | ------------------------------------------- | ---------------------------- |
| `/etc/charsooq/tls/versions/<stamp>/fullchain.pem` | `/etc/caddy/certs/versions/<stamp>/fullchain.pem` | leaf first, then every issuing intermediate | `root:root`, `0644` (public) |
| `/etc/charsooq/tls/versions/<stamp>/privkey.pem`   | `/etc/caddy/certs/versions/<stamp>/privkey.pem`   | matching private key                        | `root:root`, `0600`          |
| `/etc/charsooq/tls/current`                        | `/etc/caddy/certs/current`                        | symlink to exactly one version directory    | `root:root`                  |
| `/etc/charsooq/tls/org-root.crt`                   | not mounted by default                            | organization root CA, offline validation    | `root:root`, `0644`          |

Caddy is configured for `/etc/caddy/certs/current/fullchain.pem` and
`/etc/caddy/certs/current/privkey.pem`. Because the whole parent directory is mounted, the relative
symlink resolves inside the mount. **Replacing `current` with `os.replace` is a single atomic rename:
Caddy can never observe a new certificate with an old key, or the reverse.** Editing files inside an
active version directory is forbidden; a change means a new version directory.

The Caddy image runs as root by default (no `user:` in Compose), so root-owned `0600` is readable by
the service and by nobody else on the host. A non-root switch is a separate decision (section 10.1).

`CHARSOOQ_TLS_CERT_FILE` and `CHARSOOQ_TLS_KEY_FILE` override the paths **inside the container**.
They are read by the Caddyfile, not by Compose: the Compose service does not forward them, because an
empty value would leave the `tls` directive without arguments. Use them with
`make prod-caddy-validate CERT_FILE=… KEY_FILE=…` (which passes `docker compose run -e`) or when
running Caddy directly. They are not host paths and do not contain secret values.

### 3.2 Intake checklist (before anything is installed)

Obtain the material only through the organization's approved channel (CA portal, PKI team, ticket).
Do not generate a substitute.

1. Record the source (ticket/request ID), issuer, serial number, and SHA-256 fingerprint.
2. Confirm the SAN contains the **exact** `CHARSOOQ_SITE_HOST`: a DNS name for a DNS SAN, or the
   literal address for an IP SAN. A certificate for a different name is not usable.
3. Confirm `fullchain.pem` contains the leaf **and every issuing intermediate**, in order
   (leaf → intermediate(s)). A leaf-only file is rejected by the validation tool.
4. Confirm the validity window covers the deployment date and renews at least 30 days before expiry.
5. Confirm the private key belongs to the leaf and is not encrypted (Caddy's file loader cannot
   prompt for a passphrase).
6. Never place the files in the repository, an image, a chat message, a ticket attachment, or a
   Compose variable.

### 3.3 First installation (host, as root)

```bash
# Directory only. `tls-activate` creates versions/<stamp>/ with the right modes.
sudo install -d -m 0700 -o root -g root /etc/charsooq/tls
sudo install -m 0644 -o root -g root <approved-source>/org-root.crt /etc/charsooq/tls/org-root.crt

# Stage, validate, and activate the pair with one atomic symlink switch.
sudo python3 deploy/tls/activate_certificate.py \
  --tls-dir /etc/charsooq/tls \
  --cert <approved-source>/fullchain.pem \
  --key <approved-source>/privkey.pem \
  --host <site-host> \
  --ca-file /etc/charsooq/tls/org-root.crt

# The equivalent make target (run from the deployment checkout):
# sudo make tls-activate CERT=<approved-source>/fullchain.pem \
#   KEY=<approved-source>/privkey.pem HOST=<site-host> \
#   CA_FILE=/etc/charsooq/tls/org-root.crt

# Validate the live configuration in the pinned image, then start/reload the proxy.
make prod-caddy-validate
docker compose -f compose.production.yml restart caddy
```

`CA_FILE` is the organization root (or the public root for a public CA). Without it the tool checks
structure and signatures only and says so; with it the chain must terminate at that anchor. A
non-zero exit changes nothing: the new version directory is removed and `current` is untouched.

The activation tool never copies the source pair into the live paths before validation. It creates
`versions/<timestamp>/`, installs the files (`0644` certificate, `0600` key), runs the full validation
against those installed paths, and only then replaces `current`. It prints the previous version for
rollback and never deletes old versions.

**Migrating a directory from the earlier flat layout** (`fullchain.pem` and `privkey.pem` directly
in `CHARSOOQ_TLS_DIR`): do not restart Caddy yet, because the new default path expects `current`.
Run `tls-activate` once with those two files as `--cert`/`--key`; it creates the first version and
the symlink. Keep the flat files until the restart and HTTPS check pass, then remove them
deliberately.

### 3.4 Validate the Caddy configuration

Validate with the pinned image, not with a different local build:

```bash
make prod-caddy-validate
```

This runs `caddy validate` inside `caddy:2.11.9-alpine` with the deployment environment's
`CHARSOOQ_SITE_HOST`, `CHARSOOQ_TLS_MODE`, and the read-only certificate mount. It fails when a file
is missing, unreadable, or the key does not match. `docker compose run` resolves the required
deployment variables, so they must be set in the deployment environment (they are required for every
Compose command anyway).

### 3.5 Apply

With `admin off` there is no reload API. Certificate file changes are picked up by restarting the
container:

```bash
docker compose -f compose.production.yml restart caddy
```

A restart stops and starts only the proxy container. `web`, `api`, and `db` keep running; requests
that arrive during the restart fail. See section 6.6 for restart vs. reload vs. `SIGUSR1`.

### 3.6 Verify after any certificate change

```bash
SITE_HOST=<site-host>          # exactly the certificate SAN
CA_FILE=/etc/charsooq/tls/org-root.crt

# HTTPS, chain, and HTTP status through the real site.
curl -sS --cacert "$CA_FILE" -o /dev/null -w '%{http_code}\n' "https://$SITE_HOST/login"

# Served certificate: dates, SAN, and fingerprint. Compare the fingerprint with 3.2.
openssl s_client -connect "$SITE_HOST:443" -servername "$SITE_HOST" -CAfile "$CA_FILE" \
  </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -fingerprint -sha256 -ext subjectAltName

# HSTS is sent by the HTTPS site only, one year, without includeSubDomains/preload.
curl -sSI --cacert "$CA_FILE" "https://$SITE_HOST/login" | grep -i '^strict-transport-security'

# HTTP redirects to HTTPS (308).
curl -sSI "http://$SITE_HOST/" | sed -n '1p;/^[Ll]ocation:/p'

# No certificate or key errors, and no credentials in the access log.
docker compose -f compose.production.yml logs --since 10m caddy
```

For an **IP SAN**, omit `-servername` (SNI is for DNS names) and let OpenSSL verify the address from
the certificate:

```bash
openssl s_client -connect "<ip>:443" -CAfile "$CA_FILE" -verify_ip "<ip>" </dev/null
```

### 3.7 Rollback after a failed change

Every activation keeps the previous version directory and prints it. Roll back by pointing the same
symlink at it; do not copy files by hand:

```bash
sudo python3 deploy/tls/activate_certificate.py \
  --tls-dir /etc/charsooq/tls \
  --rollback-to <previous-stamp> \
  --host <site-host> \
  --ca-file /etc/charsooq/tls/org-root.crt
# or: sudo make tls-rollback STAMP=<previous-stamp> HOST=<site-host> \
#       CA_FILE=/etc/charsooq/tls/org-root.crt

make prod-caddy-validate
docker compose -f compose.production.yml restart caddy
```

Rollback re-validates the kept pair (structure, key match, SAN, not expired) but does not enforce the
30-day renewal threshold, so an older certificate can be used in an incident. Verify the served
fingerprint afterwards (3.6); it must equal the pre-rotation value.

### 3.8 Renewal policy

Do **not** assume the organization CA supports ACME, SCEP, auto-enrollment, or a renewal API. None
of that is known.

- Default assumption: **manual renewal**, owned by the operator on call for Production, tracked in
  the team's calendar/ITSM with a 30-day lead.
- At 30 days before expiry: open the renewal request with IT/CA.
- At 14 days: escalate; if material has not arrived, plan a maintenance window and a fallback
  decision with IT.
- At 7 days: treat as an incident. A Production certificate must not reach expiry.
- When the new certificate arrives, follow section 6. It is not installed before it passes
  validation.
- If IT confirms an automated renewal mechanism later, it must write to the same two paths and still
  go through validation, Caddy validation, restart/reload, and verification. Automation does not
  replace the rollback step.
- A **public** CA in `organization` mode would normally use ACME, but this Caddyfile deliberately
  loads files and has no ACME configuration. Do not add ACME without a separate decision; the
  internal-only requirement makes public CAs unusual here.

## 4. Mode B — Caddy internal CA

Use this only when the organization has no internal CA and IT accepts distributing Caddy's root to
every client. It is not a temporary self-signed leaf.

### 4.1 What is stored where

| Path in container                                        | Volume         | Content                                | Sensitivity                   |
| -------------------------------------------------------- | -------------- | -------------------------------------- | ----------------------------- |
| `/data/caddy/pki/authorities/local/root.crt`             | `caddy_data`   | Root CA certificate (public)           | Distribute to clients         |
| `/data/caddy/pki/authorities/local/root.key`             | `caddy_data`   | **Root CA private key**                | Highest: never distribute     |
| `/data/caddy/pki/authorities/local/intermediate.crt`     | `caddy_data`   | Intermediate CA certificate            | Internal                      |
| `/data/caddy/pki/authorities/local/intermediate.key`     | `caddy_data`   | Intermediate CA private key            | Secret                        |
| `/data/caddy/certificates/local/<host>/…`                | `caddy_data`   | Issued leaf certificate, key, metadata | Secret (key)                  |
| `/data/caddy/instance.uuid`, `locks/`, `last_clean.json` | `caddy_data`   | Instance state                         | Internal                      |
| `/config/caddy/autosave.json`                            | `caddy_config` | Last loaded config                     | Internal (hostnames, no keys) |

**Data vs. config:** `caddy_data` is authoritative security state (CA keys, issued certificates,
OCSP). `caddy_config` is the persisted config used by `caddy run --resume`; losing it does not change
the CA, and this deployment starts from the committed Caddyfile, so it is recoverable. Back up both
anyway, but the CA key exists only in `caddy_data`.

### 4.2 Distributing the root

1. Extract **only** the public root certificate, read-only, from the running container:

   ```bash
   docker compose -f compose.production.yml exec -T caddy \
     cat /data/caddy/pki/authorities/local/root.crt > /tmp/charsooq-root.crt
   ```

   Move it to the location IT uses for trust distribution. Treat `/tmp` as a temporary hand-off and
   remove it afterwards. Keep a copy of this **public** root at a path the operator controls, for
   example `/etc/charsooq/tls/caddy-root.crt` (mode `0644`), so the outside checks in 8.4 do not
   depend on the container; never copy `root.key`.

2. Record its SHA-256 fingerprint in the operations log.
3. IT distributes it through the approved mechanism (for example Group Policy, MDM, or the
   organization's certificate management tool). **Do not assume any of those exist.**
4. Never copy `root.key` or `intermediate.key` anywhere. A copy of the root key lets its holder mint
   certificates that every trusting client accepts.
5. Do not enable strict validation or remove browser warnings for the site until the root is
   installed on the clients that will use it.

### 4.3 Renewal behavior

- Leaves are valid for 12 hours and renewed automatically by Caddy. There is no operator renewal and
  no calendar entry for the leaf.
- The intermediate is valid for 7 days and rotated by Caddy.
- The root is valid for 10 years. Review its expiry yearly and record it.
- The meaningful monitoring is therefore "does the HTTPS handshake succeed with the expected root"
  and "when does the root expire", not leaf file expiry.
- Caddy's internal CA keeps its state across container restarts and recreations **as long as the
  named volumes are preserved**. `docker compose down` keeps them; `docker compose down -v` removes
  them. Never use volume removal as a repair.

### 4.4 Losing the CA private key

If `caddy_data` is lost, corrupted, or restored without its keys:

- **Security incident.** The old root key may still be trusted by clients; treat it as compromised
  until proven otherwise.
- Caddy generates a new CA on the next start. Every client that trusted the old root now sees an
  untrusted certificate; the panel is effectively unavailable over HTTPS until the new root is
  distributed.
- Recover from the encrypted backup and verify the root fingerprint before starting the proxy
  (section 7.5). If no valid backup exists, the only path is a new CA, a new distribution round, and
  a recorded incident.
- Do not bypass TLS validation, install the new root silently, or leave HSTS active while clients
  cannot validate the certificate.

## 5. Certificate validation tool

[`deploy/tls/validate_certificate.py`](../../deploy/tls/validate_certificate.py) is the gate before
any install or restart. It is read-only and offline.

### 5.1 What it checks

1. Both files exist, are regular files, are readable, and are not empty.
2. The certificate file is PEM and the first block is the leaf.
3. The key parses, is not encrypted, and its public key matches the leaf.
4. The leaf is valid now and has at least `--min-remaining-days` (default 30) left.
5. The chain is ordered, complete, and every signature verifies.
6. The leaf SAN covers `--host` exactly (wildcards match one label only; IP SANs are compared as
   addresses).
7. The key is not accessible to group/other. Group access is a warning; world access fails.

### 5.2 What it never does

- It never prints private-key material or file contents.
- It never connects to the network, issues, renews, installs, or deletes anything.
- It does not check revocation (OCSP/CRL). That requires network access and a policy decision.
- Without `--ca-file`, it verifies structure and signatures against the last certificate in the file
  and labels the result "structure only". Pass the organization root to verify the trust anchor.
- It requires OpenSSL 3.x on `PATH`.

### 5.3 Usage

```bash
make tls-validate CERT=/path/fullchain.pem KEY=/path/privkey.pem HOST=<name-or-ip> \
  [CA_FILE=/path/root.crt] [MIN_DAYS=30]

# Equivalent, without make:
python3 deploy/tls/validate_certificate.py \
  --cert /path/fullchain.pem --key /path/privkey.pem \
  --host <name-or-ip> --ca-file /path/root.crt
```

Exit status: `0` pass, `1` validation failure, `2` usage error. A failing run prints each failure;
it stops at the first hard failure of a stage but still reports the summary.

### 5.4 Activation tool

[`deploy/tls/activate_certificate.py`](../../deploy/tls/activate_certificate.py) turns a validated
pair into the active one. It creates `versions/<stamp>/`, installs the certificate (`0644`) and key
(`0600`), runs the validation above against the installed paths, and only then replaces the single
`current` symlink with `os.replace` (one atomic rename). The pair is validated once more through
`current`; if that fails, the previous symlink is restored. A failure leaves the active pair
unchanged.

- It never restarts Caddy and never uses the admin API; run `docker compose … restart caddy` after a
  successful activation.
- It never prints key material and never contacts the network.
- A rollback target is validated without the 30-day renewal threshold, but still must parse, match,
  cover the host, and not be expired.
- It prints the version it activated and the previous version to use for rollback.

## 6. Rotation and rollback (organization certificates)

Rotation applies to mode A. Mode B renews itself; its "rotation" is CA replacement, which is an
incident/recovery procedure, not routine.

### 6.1 Preconditions

- New material passed the intake checklist (3.2).
- A maintenance window or explicit approval exists; a restart is brief but not zero-downtime.
- The current fingerprint, expiry, and SANs are recorded.
- The backup of current material is fresh and encrypted (section 7).
- The operator has `sudo` on the host and access to the deployment environment's variables.

### 6.2 Stage and validate with the activation tool

The source pair is any approved staging location (for example `/root/incoming/`). Never copy it over
the live paths by hand.

```bash
TLS_DIR=${CHARSOOQ_TLS_DIR:-/etc/charsooq/tls}

sudo python3 deploy/tls/activate_certificate.py \
  --tls-dir "$TLS_DIR" \
  --cert /root/incoming/fullchain.pem \
  --key /root/incoming/privkey.pem \
  --host <site-host> \
  --ca-file "$TLS_DIR/org-root.crt"
```

What happens, in order:

1. a new `versions/<UTC stamp>/` is created (`0700`); the pair is installed as `fullchain.pem` `0644`
   and `privkey.pem` `0600`, so source permissions never leak through;
2. the full validation (files, key match, chain, expiry, SAN, permissions) runs against the installed
   paths;
3. only if it passes, the single `current` symlink is replaced with `os.replace` — one atomic
   rename, so Caddy can never see a new certificate with an old key or the reverse;
4. the pair is validated again through `current`; if that unexpectedly fails, the previous symlink
   is restored automatically;
5. the activated and previous version names are printed for the record and rollback.

On any failure nothing is activated, the new version directory is removed, and the previously active
version keeps serving. The tool prints no key material.

`sudo make tls-activate CERT=… KEY=… HOST=… CA_FILE=…` is the same operation. `MIN_DAYS` (default 30)
applies to a new installation: a certificate that expires sooner is rejected; renew it with the CA
instead of lowering the threshold.

### 6.3 Back up before switching

Take the encrypted TLS backup (7.3) before activating new material. Version directories are a fast
rollback, not a backup: they live on the same host and the same directory. Record the current
fingerprint and target first:

```bash
readlink -f "$TLS_DIR/current"
openssl x509 -in "$TLS_DIR/current/fullchain.pem" -noout -fingerprint -sha256 -dates
```

### 6.4 Validate the live configuration and apply

```bash
make prod-caddy-validate
docker compose -f compose.production.yml restart caddy
```

`prod-caddy-validate` runs the pinned image's binary against the committed Caddyfile; it resolves
`current` and fails if the pair is missing or mismatched. The restart is the only way to load it
(`admin off`).

### 6.5 Verify

Run 3.6. The served fingerprint must equal the new fingerprint; the SAN and expiry must match the
new certificate.

**Mount semantics:** the Compose file mounts the parent directory; the `current` symlink and its
`versions/` target are both inside it, so replacing the symlink is visible to the container. Never
replace the mounted directory itself (that detaches the bind mount), and never edit files inside an
active version directory.

### 6.6 Restart vs. reload vs. signal — availability

| Method                                  | Works with `admin off`?                     | Availability                                                                        | Use                                                                |
| --------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `docker compose restart caddy`          | Yes                                         | Listener stops for a few seconds; in-flight requests fail; browser sessions survive | Default for certificate changes                                    |
| `docker compose up -d --no-deps caddy`  | Yes                                         | Recreates the container; same brief outage                                          | Environment/config changes (`CHARSOOQ_TLS_MODE`, site host)        |
| `docker kill -s USR1 <caddy-container>` | Yes: signal-based reload, not the admin API | No restart; the running process reloads the config                                  | Optional zero-downtime path, only after it is exercised in Staging |
| `caddy reload`                          | **No**                                      | —                                                                                   | Never in this architecture; it needs the admin API                 |

`restart` reuses the existing container configuration. It does **not** pick up new environment
variables; use `up -d --no-deps caddy` for those. The certificate paths are `current/...` inside the
bind-mounted directory, so a restart re-resolves the symlink and loads the active version.

The `SIGUSR1` path was verified locally with the 2.11.9 binary started exactly as the official image
starts it (`caddy run --config /etc/caddy/Caddyfile --adapter caddyfile`), including with
`admin off`. It was not verified against the running container in this task because the image could
not be pulled in the task environment. Treat it as an approved improvement only after a Staging
rehearsal: confirm the new certificate is served after the signal, and confirm that a broken staged
certificate leaves the old one serving.

### 6.7 Rollback

Point `current` back to the previous version; the activation tool revalidates that pair and swaps the
same single symlink:

```bash
TLS_DIR=${CHARSOOQ_TLS_DIR:-/etc/charsooq/tls}

sudo python3 deploy/tls/activate_certificate.py \
  --tls-dir "$TLS_DIR" \
  --rollback-to <previous-stamp> \
  --host <site-host> \
  --ca-file "$TLS_DIR/org-root.crt"
# or: sudo make tls-rollback STAMP=<previous-stamp> HOST=<site-host> \
#       CA_FILE="$TLS_DIR/org-root.crt"

make prod-caddy-validate
docker compose -f compose.production.yml restart caddy
```

Verify the served fingerprint equals the pre-rotation value (3.6). Rollback validation does not
enforce the 30-day threshold, so an older certificate is usable during an incident, but it still
rejects an expired certificate, a mismatched key, or a wrong SAN.

If the version directory is gone, restore the TLS directory from the encrypted backup (7.5), then
activate the restored version. Never point `current` at a path that does not exist: Caddy would fail
to start and the panel would stay offline.

### 6.8 Record the operation

Write one entry to the operations log (outside the repository) with:

- timestamp (UTC), operator, ticket/change ID;
- old and new SHA-256 fingerprints, issuer, serial, SANs, notAfter;
- activated version (`current` target) and the previous version kept for rollback;
- validation tool result and `caddy validate` result;
- whether the apply was restart, recreate, or `SIGUSR1`;
- verification results (HTTPS status, HSTS, redirect, served fingerprint);
- rollback performed (yes/no) and the reason.

Never record key material, passphrases, session identifiers, or secret file contents.

## 7. Backup and restore

### 7.1 Scope

| Item                     | Where                                            | Contains private keys?                  | Backup requirement                        |
| ------------------------ | ------------------------------------------------ | --------------------------------------- | ----------------------------------------- |
| `caddy_data`             | Docker volume `charsooq-production_caddy_data`   | Yes (internal CA keys, leaf keys, OCSP) | Encrypted, off-host                       |
| `caddy_config`           | Docker volume `charsooq-production_caddy_config` | No keys; internal config                | Encrypted, off-host                       |
| Organization TLS         | `${CHARSOOQ_TLS_DIR}` (`/etc/charsooq/tls`)      | Yes (`privkey.pem`)                     | Encrypted, off-host                       |
| Caddy config and Compose | Git (`deploy/caddy/`, `compose.production.yml`)  | No                                      | Git + release commit SHA                  |
| CA root (public)         | `caddy_data` (mode B) or the organization CA     | No (public part only)                   | Included above; distribute separately     |
| CA private keys (mode B) | `caddy_data`                                     | Yes                                     | Encrypted, off-host, separate key custody |

No backup may live in this repository. No backup may exist only on the same volume or the same host.
No production backup is created by this task.

### 7.2 Rules

1. Encrypt every archive that contains a private key. Use the organization's approved tool and key
   custody; `age`, `gpg`, and `restic` are common, but none is assumed to be installed or approved.

   ```bash
   # Examples only, and only with the organization's approved tool and recipient/key:
   age --encrypt --recipient <approved-recipient> --output archive.tar.gz.age archive.tar.gz
   gpg --encrypt --recipient <approved-key-id> archive.tar.gz
   ```

   `openssl enc` was used only for the offline restore drill (it is unauthenticated); do not adopt it
   as the production format without an explicit decision.

2. Store archives outside the repository and outside the production host, with `0700` directories and
   `0600` files.
3. Keep the encryption key/custodian separate from the backup location. A backup and its key in the
   same place is not a backup.
4. Verify each backup by decrypting it into a scratch location and comparing the recorded CA/leaf
   fingerprints. A backup that has never been restored is unverified.
5. Do not treat volume deletion or recreation as a repair method.
6. Retention and RPO/RTO are **open decisions** (section 11). Do not invent a schedule.

### 7.3 Back up the volumes

Stop the proxy for a consistent copy, or use a filesystem snapshot that guarantees consistency. On a
single host with a single Caddy process, the stop is short and is the simplest correct option.

```bash
BACKUP_ROOT=/secure/charsooq-tls-backups     # outside the repo, 0700, encrypted storage
TLS_DIR=${CHARSOOQ_TLS_DIR:-/etc/charsooq/tls}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
VOLUMES="charsooq-production_caddy_data charsooq-production_caddy_config"

docker compose -f compose.production.yml stop caddy

for volume in $VOLUMES; do
  docker run --rm \
    --volume "$volume":/source:ro \
    --volume "$BACKUP_ROOT":/backup \
    caddy:2.11.9-alpine \
    tar -C /source -czf "/backup/$volume-$STAMP.tar.gz" .
  # Replace this with the approved encryption tool and key custody.
  <approved-encryption-command> "$BACKUP_ROOT/$volume-$STAMP.tar.gz"
  sha256sum "$BACKUP_ROOT/$volume-$STAMP.tar.gz"* > "$BACKUP_ROOT/$volume-$STAMP.sha256"
  rm -f "$BACKUP_ROOT/$volume-$STAMP.tar.gz"   # keep only the encrypted archive
done

docker compose -f compose.production.yml start caddy
```

The helper uses the pinned Caddy image already present on the host (busybox `tar`), so no extra image
is required. If the organization's backup agent snapshots Docker volumes directly, use it instead and
still verify and encrypt the result.

Also back up the organization TLS directory. Run as root and let `tar` store `current` as a symlink
(do not dereference it):

```bash
sudo tar -C "$(dirname "$TLS_DIR")" -czf "$BACKUP_ROOT/charsooq-tls-$STAMP.tar.gz" \
  "$(basename "$TLS_DIR")"
# Then encrypt with the approved tool and remove the plaintext archive.
tar -tvzf "$BACKUP_ROOT/charsooq-tls-$STAMP.tar.gz" | grep -E 'current|versions/'
```

The listing must show `current -> versions/<stamp>` and the version directories. Record the Git
commit SHA of the deployed Compose/config. If organization policy forbids exporting the private key,
back up the certificate and the CA root, and record how the key is reissued; never store the key in a
weaker place just to have a backup.

### 7.4 Verify a backup

```bash
# List contents without extracting (after decryption into a scratch dir).
tar -tzf <decrypted-archive> | head

# For caddy_data, the CA must still be the same one clients trust.
openssl x509 -in <scratch>/caddy/pki/authorities/local/root.crt \
  -noout -subject -dates -fingerprint -sha256

# For organization material, validate the restored version pair exactly as in 3.3.
```

Record the fingerprint and the verification date. A mismatch with the recorded value is a restore
failure, not a new CA.

### 7.5 Restore

Restoring volumes in place is destructive to the current contents. Preserve the current state first.

1. **Stop the proxy** and keep the rest of the stack running (or stop the stack if policy requires).
   `docker compose -f compose.production.yml stop caddy`.
2. **Snapshot the current volume** (encrypted) with the same procedure as 7.3. Even a broken state is
   evidence; do not delete it before the new restore is verified.
3. **Clear the target volume** only after step 2:

   ```bash
   docker run --rm --volume charsooq-production_caddy_data:/target \
     caddy:2.11.9-alpine \
     sh -c 'rm -rf /target/* /target/.[!.]* /target/..?*'
   ```

4. **Extract the chosen archive** into the volume:

   ```bash
   <approved-decryption-command> <archive> \
     | docker run --rm -i --volume charsooq-production_caddy_data:/target \
         caddy:2.11.9-alpine tar -C /target -xzf -
   ```

5. **Verify before starting**: list the volume and compare the CA root fingerprint with the recorded
   value. For `internal-ca`, a different root fingerprint means every client will break; do not start
   the proxy as if the restore succeeded.
6. **Start and verify**:
   `docker compose -f compose.production.yml start caddy`, then run 3.6 (HTTPS, served certificate,
   HSTS, redirect, logs). For organization material, confirm that `current` exists and points at a
   version directory; if the archive did not preserve the symlink, activate the intended version with
   `tls-activate`/`tls-rollback` before starting, and confirm the served leaf fingerprint.
7. **Record** the restore in the operations log, including which archive was used and the
   fingerprints before/after.

If the proxy does not start, read `docker compose logs caddy`, verify file modes and paths, and
restore the pre-restore snapshot. Do not "fix" it by deleting volumes or disabling TLS.

### 7.6 Restore drill

A drill is required before Production and then at the cadence IT approves.

- Use a **separate throwaway project/volume**, never the Production volume.
- Restore a recent archive, run the pinned Caddy image with the committed Caddyfile (mount the
  restored data as `/data`, the config as `/config`, and the config snippets read-only), and verify
  the CA fingerprint and an HTTPS handshake from a local client.
- For mode A, verify the restored certificate/key pair with the validation tool and confirm the
  served certificate.
- Delete the drill volume, container, and decrypted scratch files afterwards.
- Record the drill result and the time to restore.

### 7.7 Losing the Caddy CA private key

See 4.4. A lost root key is a security event, not a routine renewal. Restoring the encrypted backup
is the only way to preserve client trust; otherwise plan a new CA, a new root distribution, and an
incident record.

## 8. Monitoring and expiration

No monitoring agent or automation is added. The checks below are manual until IT approves a tool,
an alert channel, and an owner. The repository tool never contacts the server; only the explicit
client checks in this section open a connection to the panel.

### 8.1 Thresholds

Operator-managed certificates (mode A, and the mode B root CA):

| Remaining lifetime | Level      | Action                                                                         |
| ------------------ | ---------- | ------------------------------------------------------------------------------ |
| ≤ 30 days          | Task       | Open the renewal request; confirm the CA lead time                             |
| ≤ 14 days          | Escalation | Escalate to the service owner; book the maintenance window                     |
| ≤ 7 days           | Incident   | Replace now; prepare rollback; notify users if needed                          |
| Expired            | Outage     | Incident response; users see certificate errors; do not disable TLS validation |

The Caddy internal **leaf** is exempt: it is valid for 12 hours and renewed automatically. Never
alert on its expiry; an expired leaf already means the handshake check fails. The intermediate
(7 days) is maintained by Caddy too; do not alert on its file age.

### 8.2 Outside vs. inside

| Check                                 | From outside the service              | Requires inside access          |
| ------------------------------------- | ------------------------------------- | ------------------------------- |
| HTTPS handshake succeeds              | Yes: `curl` / `openssl s_client`      | —                               |
| Served certificate validity           | Yes: pipe `s_client` into `x509`      | —                               |
| Served SAN matches the site host      | Yes: `-verify_hostname`/`-checkhost`  | —                               |
| Full chain trusted by the client root | Yes: `-CAfile … -verify_return_error` | —                               |
| Root CA file, expiry, fingerprint     | No (the root is normally not sent)    | Yes: read `caddy_data`          |
| Intermediate file and expiry          | No                                    | Yes: read `caddy_data`          |
| Renewal / issuance success            | Partly: served serial and `notBefore` | Yes: logs and certificate files |
| Data volume writable / free space     | No                                    | Yes: `docker compose exec`      |
| Caddy process and listener health     | Yes: published port + `compose ps`    | Logs explain failures           |
| CA key still present and readable     | No                                    | Yes (existence only)            |

"Inside access" means `docker compose exec`/`cp` on the host. The Caddy image does **not** include
the `openssl` CLI, so copy certificate files out with `docker compose cp` and inspect them on the
host; never `exec openssl`.

### 8.3 Organization certificate (mode A)

Daily, offline on the host (the tool follows the `current` symlink):

```bash
make tls-validate \
  CERT=/etc/charsooq/tls/current/fullchain.pem \
  KEY=/etc/charsooq/tls/current/privkey.pem \
  HOST=<site-host> \
  CA_FILE=/etc/charsooq/tls/org-root.crt \
  MIN_DAYS=30
```

A non-zero exit is the alert. Also check the served certificate, because the file does not prove what
Caddy loaded:

```bash
openssl s_client -connect "<site-host>:443" -servername "<site-host>" \
  -CAfile /etc/charsooq/tls/org-root.crt -verify_return_error \
  -verify_hostname "<site-host>" </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -ext subjectAltName -fingerprint -sha256 -checkhost "<site-host>"
```

Compare the fingerprint with the last recorded activation. A difference means the material changed
without a log entry.

### 8.4 Caddy internal CA (mode B) — outside checks

These need no shell inside the container and are the primary signals:

```bash
ROOT=/etc/charsooq/tls/caddy-root.crt   # public root distributed to clients, kept for checks
SITE=<site-host>

# 1. Handshake, chain, hostname. Non-zero exit = alert.
openssl s_client -connect "$SITE:443" -servername "$SITE" \
  -CAfile "$ROOT" -verify_return_error -verify_hostname "$SITE" </dev/null >/dev/null

# 2. What the server actually presents (validity, SAN, fingerprint).
openssl s_client -connect "$SITE:443" -servername "$SITE" </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName -checkhost "$SITE"

# 3. HTTPS application response (also proves the proxy routes to web).
curl -sS --cacert "$ROOT" -o /dev/null -w '%{http_code}\n' "https://$SITE/login"
```

The served leaf should be valid now, with about 12 hours of lifetime and a recent `notBefore`; an old
serial or a leaf close to expiry is the renewal-failure signal. The root itself is not sent, so its
file is checked inside (8.5). A changed or expired root makes every client fail; compare its
fingerprint weekly and after every restore or upgrade.

If `<SITE>` is an IP, use `-verify_ip "$SITE"` / `-checkip "$SITE"` instead of the hostname options.

### 8.5 Caddy internal CA (mode B) — inside checks

The image has no `openssl`; copy the **public** certificates out and inspect them on the host. This
never copies or prints private keys.

```bash
docker compose -f compose.production.yml cp \
  caddy:/data/caddy/pki/authorities/local/root.crt /tmp/charsooq-root.crt
docker compose -f compose.production.yml cp \
  caddy:/data/caddy/pki/authorities/local/intermediate.crt /tmp/charsooq-intermediate.crt

openssl x509 -in /tmp/charsooq-root.crt -noout -subject -dates -fingerprint -sha256
openssl x509 -in /tmp/charsooq-intermediate.crt -noout -subject -dates
rm -f /tmp/charsooq-root.crt /tmp/charsooq-intermediate.crt   # after recording the values
```

| Check                            | Command                                                                                                 | Expected                                        | Cadence                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ----------------------------- |
| Root fingerprint matches clients | copy `root.crt`, compare `-fingerprint -sha256`                                                         | identical to the value recorded at distribution | weekly, after restore/upgrade |
| Root expiry                      | `-dates` on the root                                                                                    | far future; review at 365/90/30 days            | yearly, then 8.1              |
| Intermediate exists, not expired | `-dates` on the intermediate                                                                            | currently valid; Caddy maintains it             | only when the handshake fails |
| Data volume writable             | `docker compose exec -T caddy sh -c 'touch /data/caddy/.write-check && rm -f /data/caddy/.write-check'` | exit 0                                          | weekly                        |
| Free space                       | `docker compose exec -T caddy df -h /data`                                                              | threshold decided by IT                         | weekly                        |
| CA key present and non-empty     | `docker compose exec -T caddy sh -c 'test -s /data/caddy/pki/authorities/local/root.key'`               | exit 0 (never print it)                         | weekly                        |
| Renewal / issuance errors        | `docker compose logs --since 24h caddy \| grep -Ei 'error\|certificate\|tls'`                           | no repeated issuance or TLS errors              | daily                         |
| Leaf renewal evidence            | served `notBefore`/serial from 8.4                                                                      | changes within a day                            | daily                         |

Do not add file-expiry alerts for the 12-hour leaf or the 7-day intermediate. A failed renewal
eventually appears as a failing handshake or an expired served leaf, which 8.4 catches; the logs show
the cause. Under the current root runtime the key check proves presence and non-emptiness; effective
readability by a service UID only becomes a real check if the container is switched to non-root.

### 8.6 Service health and connection checks

```bash
# Process/listener state. caddy has no Compose healthcheck; this plus the TLS probe is the check.
docker compose -f compose.production.yml ps caddy
docker compose -f compose.production.yml logs --since 10m caddy

# TLS policy: 1.2/1.3 only (Caddy default minimum); old protocols must fail.
openssl s_client -connect "<site-host>:443" -servername "<site-host>" -tls1_1 </dev/null
```

A Compose healthcheck was deliberately not added. A non-verifying probe (`curl -k`) would only show
that the listener is alive, while a verifying probe needs mode-specific trust material and would
duplicate the outside check above; the TLS probe plus `compose ps` covers liveness and certificate
health without adding a second mechanism.

HTTP-level checks (status, HSTS, redirect) are in 3.6. Access logs are Caddy's default JSON on
stdout; credentials are excluded unless `log_credentials` is enabled, which the committed snippets
never do.

**Not covered by a check yet:** alert delivery, retention of results, and a dashboard. Those need the
IT-owned monitoring channel (section 11). Until then, record each manual run in the operations log.

## 9. First Production deployment runbook

> Every step below is for the operator on `market-linux`. None of it was executed in this task.

### 9.1 Prerequisites owned by IT

Do not start until each item has an approved value. The detailed list is
[deployment.md § Open decisions owned by IT](../architecture/deployment.md#open-decisions-owned-by-it).

| Item                                                     | Needed for                                                 |
| -------------------------------------------------------- | ---------------------------------------------------------- |
| Fixed, approved internal IP                              | `CHARSOOQ_PROXY_BIND_IP`                                   |
| Internal DNS name, or approved decision to use an IP SAN | `CHARSOOQ_SITE_HOST` and the certificate SAN               |
| TCP 80 and 443 free and permitted inbound                | HTTPS and the HTTP redirect                                |
| IPv6 status (no IPv6 is configured)                      | Firewall and listener expectations                         |
| Docker address pools and a conflict-free `edge` subnet   | `CHARSOOQ_EDGE_SUBNET`, `CHARSOOQ_WEB_EDGE_IP`             |
| Firewall/VLAN policy for the panel                       | Client reachability                                        |
| CA type and issuance/renewal policy                      | Mode A vs. mode B; renewal owner                           |
| Root CA distribution method                              | Mode B, or mode A when clients do not already trust the CA |
| NTP/time sync on the host                                | Certificate validity checks and log correlation            |
| Certificate file access path and ownership               | Install procedure                                          |
| Backup destination, encryption tool, key custody         | Section 7                                                  |
| Monitoring/alert channel and owner                       | Section 8                                                  |

If any of these is unknown, stop. Guessing a bind address, subnet, or hostname produces a broken or
over-exposed deployment.

### 9.2 Host preparation

```bash
# Clock and timezone: certificate validation fails when the clock is wrong.
timedatectl status

# Confirm the approved address exists on this host and that 80/443 are not already bound.
ip -brief address
ss -ltnp '( sport = :80 or sport = :443 )'

# Certificate directories (mode A).
sudo install -d -m 0700 -o root -g root /etc/charsooq/tls
```

If ports are occupied, stop and resolve the conflict with IT; do not move Caddy to a nonstandard port
without revisiting the redirect and firewall design.

### 9.3 Install TLS material

- **Mode A:** follow 3.3. `tls-activate` stages and validates the pair and switches `current`; then
  `make prod-caddy-validate` must pass before the proxy starts. Do not start with an unactivated
  directory (no `current`) or with a pair that has not passed validation.
- **Mode B:** set `CHARSOOQ_TLS_MODE=internal-ca`, leave the certificate directory without a
  `current` pair, and plan root distribution. The CA is created on the first start; extract only the
  public root, hand it to IT, and keep the public copy used by the checks (for example
  `/etc/charsooq/tls/caddy-root.crt`). Do not start user traffic before the root is installed where
  it is needed.

### 9.4 Deployment environment variables

Set these in the deployment environment (not in Git, not in a committed `.env` file):

| Variable                                           | Value                                                                                                                         |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `CHARSOOQ_PROXY_BIND_IP`                           | Approved internal IP                                                                                                          |
| `CHARSOOQ_SITE_HOST`                               | Approved DNS name or IP, exactly the certificate SAN                                                                          |
| `CHARSOOQ_EDGE_SUBNET`                             | Conflict-checked CIDR                                                                                                         |
| `CHARSOOQ_WEB_EDGE_IP`                             | `web`'s fixed address in that CIDR                                                                                            |
| `CHARSOOQ_TLS_MODE`                                | `organization` (default) or `internal-ca`                                                                                     |
| `CHARSOOQ_TLS_DIR`                                 | Host certificate directory; holds `current`/`versions/` in mode A and the public `caddy-root.crt` used by checks in mode B    |
| `CHARSOOQ_TLS_CERT_FILE` / `CHARSOOQ_TLS_KEY_FILE` | Only with `make prod-caddy-validate CERT_FILE=… KEY_FILE=…`; not forwarded by Compose (empty would break the `tls` directive) |
| `CHARSOOQ_SECRETS_DIR`                             | Host directory of the six secret files (default `/etc/charsooq/secrets`)                                                      |

No secret value belongs in any of these variables. Certificate paths are not secrets; the key
content never appears in Compose interpolation, logs, or `docker compose config` output.

### 9.5 Pre-flight validation

```bash
make prod-config            # Compose structure with the real environment values
make prod-caddy-validate    # pinned Caddy binary against the committed config + material
```

`make prod-config` with real values must pass, not only the documentation-address variant.

### 9.6 Database provisioning and migration

Follow the existing Production order; TLS does not change it:

```bash
make prod-provision        # one-shot role/grant provisioning
make prod-migrate          # one-shot locked migrations to head
make prod-bootstrap-owner  # explicit owner bootstrap, when required
```

These need the secret files and the verified backup gate from
[deployment.md](../architecture/deployment.md#production-secrets). Do not start `api` or `web` before
they succeed.

### 9.7 Start

```bash
make prod-up
make prod-ps
docker compose -f compose.production.yml logs --since 10m caddy
```

`caddy` starts only after `web` is healthy. Confirm that it is the only service with published ports.

### 9.8 Verification matrix

| Check                   | Command                                                                                     | Expected                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| HTTPS + chain           | `curl -sS --cacert <root> -o /dev/null -w '%{http_code}\n' https://<host>/login`            | `200` (or the login redirect), no TLS error                       |
| Served certificate      | `openssl s_client … \| openssl x509 -noout -dates -ext subjectAltName -fingerprint -sha256` | SAN equals `<host>`, dates as recorded, fingerprint as installed  |
| HSTS                    | `curl -sSI --cacert <root> https://<host>/login \| grep -i strict-transport-security`       | `max-age=31536000`, no `includeSubDomains`, no `preload`          |
| HTTP redirect           | `curl -sSI http://<host>/`                                                                  | `308`, `Location: https://<host>/`                                |
| Login                   | Open `https://<host>/login` in a browser that trusts the CA                                 | Persian RTL login loads; owner login works                        |
| Session cookie          | Browser devtools → Cookies                                                                  | `charsooq_session`: `Secure`, `HttpOnly`, `SameSite=Lax`          |
| API through the rewrite | `curl -sS --cacert <root> https://<host>/api/v1/health`                                     | `{"status":"ok"}`                                                 |
| Readiness               | `curl -sS --cacert <root> https://<host>/api/v1/ready`                                      | `{"status":"ready"}`                                              |
| Exposure                | `docker compose -f compose.production.yml ps`                                               | Only `caddy` shows published ports                                |
| No direct API/DB        | From another host: connect to `<host>:8000`, `:3000`, `:5432`                               | Connection refused/unreachable                                    |
| Logs                    | `docker compose logs caddy`                                                                 | No certificate, TLS handshake, or upstream errors; no credentials |

If a check fails, do not open the panel to users and do not relax TLS. Fix the certificate,
validation, or routing and restart only `caddy`; the database and application stay untouched.

### 9.9 Record and hand over

Record the deployed commit SHA, image references, certificate fingerprints, SANs, expiry dates, the
CA mode, the backup location (not its key), and the monitoring owner. Add the renewal entry to the
calendar/ITSM at least 30 days before expiry. Hand the operations log and this runbook to the on-call
operator.

## 10. Least privilege audit

| Concern                           | Current state                                                                                                                                                                                                         |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Who can read the organization key | Host `root` only (`0600`); the Caddy container runs as root and is the only service with the mount                                                                                                                    |
| API/web access to keys            | No. Neither service mounts `${CHARSOOQ_TLS_DIR}` or the Caddy volumes; a static test asserts this                                                                                                                     |
| Caddy access                      | Config and certificates are read-only mounts; `/data` and `/config` are the only writable state; no Docker socket; read-only root filesystem; all capabilities dropped except `NET_BIND_SERVICE`; `no-new-privileges` |
| CA root key (mode B)              | Lives only in `caddy_data`; never leaves it, never copied into Git or an image; only the public `root.crt` is distributed                                                                                             |
| Git                               | `.gitignore` blocks `*.pem`, `*.key`, `*.crt`, `*.cer`, `*.der`, `*.p12`, `*.pfx`, `*.csr`, `*.srl`; no certificate file is tracked; a test fails if one appears                                                      |
| Docker build context              | `.dockerignore` excludes `deploy`, `.env*`, `secrets`, and certificate/key extensions; Dockerfiles never copy TLS material; a test guards this                                                                        |
| Compose interpolation             | No key or passphrase is passed as an environment variable; only paths and the site host                                                                                                                               |
| Logs                              | Caddy's default JSON access log; `log_credentials` is never enabled; the API does not log secrets; a static test guards the snippets                                                                                  |
| Backups                           | Outside the repository, encrypted, `0700`/`0600`, off-host, with the key held separately                                                                                                                              |

Residual risks (accepted or open):

- The Caddy container runs as the image default user (root inside the container). The read-only
  filesystem, dropped capabilities, and `no-new-privileges` bound the impact. A non-root switch is
  feasible but not implemented; see 10.1.
- One Caddy instance: no HA, and a restart is a short outage.
- `admin off`: no API, no hot reload; changes are file + restart (or the tested `SIGUSR1` path).
- No OCSP stapling/CRL policy, no HTTP/3, no IPv6, no WAF.
- HSTS is cached for one year after the first HTTPS response; do not expose users to a host with
  unverified TLS during the first deployment.
- No monitoring/alert automation yet; section 8 is manual until IT decides.

### 10.1 Non-root evaluation (not implemented)

Findings from the pinned image and local Docker probes:

| Question                                                                | Finding                                                                                                                                                                                                            |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Does the image define a non-root user?                                  | No. `CMD` runs Caddy as root; there is no `USER` line.                                                                                                                                                             |
| Can a non-root process bind 80/443?                                     | Yes under Docker's default `net.ipv4.ip_unprivileged_port_start=0`: UID 65534 bound `:80` with `cap-drop ALL` and `no-new-privileges` in a local probe.                                                            |
| Did the real Caddy 2.11.9 binary run as non-root?                       | Yes. The Linux binary ran as UID 65534 with `--cap-drop ALL`, `no-new-privileges`, a read-only rootfs, and writable `/data`/`/config`: it bound 80/443, issued its internal CA, served HTTPS, and redirected HTTP. |
| Does `cap_add: NET_BIND_SERVICE` help a non-root user?                  | Not with `no-new-privileges`: with the sysctl forced to `1024`, binding `:443` failed even with `cap_add: NET_BIND_SERVICE`. The image's `setcap` on the binary is also neutralized by `no-new-privileges`.        |
| What must be writable?                                                  | `/data` (CA private keys, issued certificates, OCSP) and `/config` (autosave). `/tmp` is a tmpfs; the root filesystem stays read-only.                                                                             |
| What breaks on an existing volume?                                      | `caddy_data` holds root-owned `0600` CA keys. A non-root UID cannot read them until the whole volume is chowned, including `root.key`; the host `privkey.pem` must also be owned/readable by that UID.             |
| Is read-only rootfs + `cap_drop: ALL` + `no-new-privileges` compatible? | Yes, provided low-port binding uses the Docker sysctl and the volume/key ownership is migrated.                                                                                                                    |

**Decision:** do not change the runtime user in this task. Non-root operation is proven feasible;
the blocker is the safe ownership migration and the policy decision, not a missing capability.

Reasons:

1. The pinned image has no non-root user, so Compose would have to pick an arbitrary UID/GID and
   every existing volume and key file would need a deliberate ownership migration.
2. That migration touches the internal CA private key. A partial or wrong `chown` makes the CA
   unreadable and takes HTTPS down; it must be rehearsed on a copy of the volume, not improvised.
3. Low-port binding depends on the host Docker daemon's `ip_unprivileged_port_start`; it must be
   verified on `market-linux` (and re-checked after Docker upgrades). `cap_add: NET_BIND_SERVICE`
   is not a fallback while `no-new-privileges` is set.
4. The actual image could not be pulled in this environment (`403` from Docker Hub), so an
   end-to-end non-root start of the image itself was not tested; only the release binary was.
5. Existing CA material is root-owned `0600`. A wrong or partial chown is an outage and a
   security-sensitive operation, so it needs a change window, a verified backup, and a rehearsal on
   a copy — not a side effect of this review.

Before adopting non-root: choose the UID/GID, verify the sysctl on the host, chown a **copy** of
`caddy_data`/`caddy_config` and the certificate key, start a throwaway proxy with that UID (the
release-binary probe already shows this works), verify the served certificate and a CA-signed
handshake, then switch Compose's `user:` during a window with a verified encrypted backup. Until
then, container-root with read-only rootfs, dropped capabilities, and `no-new-privileges` is the
accepted risk.

## 11. Open decisions specific to TLS operations

These are additions to the IT list in
[deployment.md](../architecture/deployment.md#open-decisions-owned-by-it):

1. Who owns certificate renewal, and what is the CA's lead time and issuance channel?
2. Does the CA support automation (ACME/SCEP/other)? If yes, to which paths, and who approves the
   change? Do not assume it does.
3. What is the approved backup tool, encryption method, key custodian, off-site destination,
   retention, RPO, and RTO?
4. Who receives expiration alerts, and through which channel? What is the escalation path?
5. Is a non-root Caddy container required? See 10.1: it needs a UID/GID decision, a verified
   low-port sysctl, and a rehearsed chown of the CA volumes and key before it can be approved.
6. Is OCSP/CRL validation required, and does the network allow it?
7. Is the `SIGUSR1` reload approved after a Staging rehearsal, or is restart the only permitted path?
8. Is the host clock synchronized to an approved NTP source, and who monitors it?
9. For mode B, who approves distributing a private root CA to clients, and how is it revoked if the
   CA key is lost?

## 12. Verification performed for this task

All checks were offline or against a local temporary directory. No connection was made to
`market-linux`, no real certificate/CA was created, and no `.env` or secret file was opened.

| Check                                                       | Result                                                                                                                                                                         |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Caddy 2.11.9 official binary, SHA-512 vs. release checksums | Match                                                                                                                                                                          |
| `caddy adapt` (organization mode, fixture certs)            | Valid JSON, expected HSTS/proxy config                                                                                                                                         |
| `caddy validate` (organization, valid fixture)              | `Valid configuration`                                                                                                                                                          |
| `caddy validate` (missing key file)                         | Fails with `no such file or directory`                                                                                                                                         |
| `caddy validate` (mismatched key)                           | Fails with `private key does not match public key`                                                                                                                             |
| `caddy validate` (internal-ca)                              | `Valid configuration`; CA created in the temporary data dir                                                                                                                    |
| Internal CA paths and lifetimes                             | Root 10y, intermediate 7d, leaf 12h; paths as documented                                                                                                                       |
| `caddy reload` with `admin off`                             | Refused (admin endpoint disabled)                                                                                                                                              |
| `SIGUSR1` reload with `caddy run --config`                  | Config changed v1 → v2 without a restart                                                                                                                                       |
| HTTP → HTTPS redirect                                       | `308` with `Location: https://…/`                                                                                                                                              |
| Rotation rehearsal (temp dir)                               | Pair staged in `versions/<stamp>`, validation passed, `current` switched; served fingerprint changed to the new leaf                                                           |
| Rollback rehearsal (temp dir)                               | `current` repointed to the kept version, validated; served fingerprint returned to the original                                                                                |
| Backup/restore rehearsal (temp dir)                         | Encrypted archive restored; root CA fingerprint unchanged; HTTPS served with the restored CA                                                                                   |
| Validation tests                                            | 21 passed (SAN, expiry, mismatch, chain, permissions, empty/corrupt files, hygiene)                                                                                            |
| Activation tests                                            | 7 passed (install, mismatch, wrong host, rotation, missing rollback target, permissions, non-symlink `current`)                                                                |
| Non-root low-port probe                                     | UID 65534 bound `:80` with `cap-drop ALL` and `no-new-privileges` under Docker's default sysctl; failed with the sysctl forced to `1024`, including `cap_add NET_BIND_SERVICE` |
| Non-root Caddy probe                                        | Real 2.11.9 Linux binary as UID 65534, `cap-drop ALL`, `no-new-privileges`, read-only rootfs: bound 80/443, issued the internal CA, served HTTPS, redirected HTTP              |
| `ruff check` / `ruff format --check` (repo-wide)            | Pass                                                                                                                                                                           |
| `pyright` (new tools and tests)                             | 0 errors                                                                                                                                                                       |

Not run, and why:

- The Caddy container image could not be pulled (`docker.io` returned `403 Forbidden` in this
  environment), so container-level `docker compose run caddy caddy validate`, a container restart,
  and a real non-root Caddy start were not executed. The same binary/version was used for
  adapt/validate/reload/rotation behavior locally, and low-port behavior was probed with an already
  present image.
- No Production command was run: no SSH, no Compose up, no migration, no database connection.
- No organization CA, DNS, firewall, or NTP endpoint was contacted.

## 13. Operation log template

Keep this outside the repository (ITSM ticket or an ops log with restricted access):

```text
Date (UTC):
Operator:
Change/ticket:
Mode: organization | internal-ca
Action: install | rotate | rollback | restore | drill
Old fingerprint (SHA-256):
New fingerprint (SHA-256):
Activated version (current target):
Previous version (kept for rollback):
Issuer / serial:
SANs:
notAfter:
Validation tool: PASS/FAIL (notes)
caddy validate: PASS/FAIL (notes)
Apply method: restart | recreate | SIGUSR1
Verification: HTTPS ___, HSTS ___, redirect ___, served fingerprint ___
Rollback: no | yes (reason)
Follow-ups:
```
