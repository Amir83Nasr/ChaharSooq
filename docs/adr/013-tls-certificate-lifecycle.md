# ADR 013 — TLS certificate lifecycle, rotation, and recovery

Date: 2026-11-13 · Status: accepted

## Context

[ADR 012](012-internal-reverse-proxy-and-tls.md) established Caddy as the only TLS terminator and
defined two modes: a certificate issued by the organization (`organization`) and Caddy's local CA
(`internal-ca`). It deliberately stopped at "TLS is configured but not enabled": no certificate,
renewal procedure, backup, rollback, or expiration check existed.

Production is internal-only, has one Caddy instance, and runs with `admin off`. The organization's
CA capabilities, renewal automation, backup tooling, monitoring channel, and certificate policy are
unknown and must not be assumed. A safe lifecycle has to work without them, fail closed when a
certificate is wrong, and stay operable if the CA key is lost.

## Decision

- **Certificate files are versioned and activated through one symlink.** `fullchain.pem` (leaf first,
  then every issuing intermediate) and `privkey.pem` live outside the repository in
  `CHARSOOQ_TLS_DIR`, under `versions/<stamp>/`, and Caddy reads only
  `current/fullchain.pem` + `current/privkey.pem`, where `current` is a symlink to one version.
  [`deploy/tls/activate_certificate.py`](../../deploy/tls/activate_certificate.py) stages and
  validates a pair, then replaces that single symlink with `os.replace`; one atomic rename swaps the
  pair, so Caddy can never start from a half-switched certificate/key combination. The mounted
  directory itself is never replaced (that would detach the Docker bind mount).
- **No renewal automation is assumed.** Organization certificates use a manual, calendar-driven
  rotation with a 30-day lead, a staged validation gate, a recorded previous fingerprint, and an
  explicit rollback. If IT later confirms an automated CA mechanism, it must still write version
  directories and pass the same validation and activation steps.
- **`caddy validate` and the offline validation tool are mandatory gates.** The new
  [`deploy/tls/validate_certificate.py`](../../deploy/tls/validate_certificate.py) checks file
  presence, PEM structure, key match, chain order/completeness, trust-anchor verification when a root
  is supplied, expiration with a threshold, SAN/host match, and private-key permissions. It prints no
  key material, performs no network access, and issues or renews nothing. It is committed under
  `deploy/` because that directory is host/runtime material and is excluded from Docker builds.
- **Restart is the supported apply path; `SIGUSR1` is an optional, tested-before-use improvement.**
  With `admin off`, `caddy reload` is impossible. Certificate changes use
  `docker compose restart caddy`; environment or config changes use
  `docker compose up -d --no-deps caddy`. A `SIGUSR1` signal to the container can reload in-process
  (verified with the 2.11.9 binary started exactly like the image), but it is not the baseline until
  it is rehearsed against the container in Staging.
- **`caddy_data` is authoritative state, not cache.** It holds the internal CA private keys, issued
  leaf keys, and OCSP state. `caddy_config` holds the autosaved config. Both are backed up, encrypted,
  off-host, with the encryption key held separately; a backup is only trusted after a restore drill.
  Deleting or recreating a volume is never a repair. Loss of the internal CA private key is a security
  incident that requires reissuing trust, not a silent CA replacement.
- **Only the public root is distributed for `internal-ca`.** `root.key` and `intermediate.key` never
  leave `caddy_data`. Every client that trusts the root depends on that key staying private.
- **Expiration monitoring stays manual until IT decides the tooling and the alert owner.** The
  thresholds are 30/14/7 days and expired. For `internal-ca`, leaf expiry is not monitored (12-hour
  certificates renew automatically); the served handshake, the served leaf's validity/SAN, the
  root's 10-year lifetime, the intermediate's health, data-volume writability, and issuance logs are.
  Outside checks use `openssl s_client`; inside checks use `docker compose cp` plus the host's
  OpenSSL because the Caddy image has no `openssl` binary.
- **Non-root was evaluated but is not adopted in this iteration.** A real 2.11.9 process ran as
  UID 65534 with dropped capabilities, `no-new-privileges`, a read-only rootfs, low ports, and an
  internal CA, so the capability model is not the blocker. The pinned image has no non-root user,
  and an existing `caddy_data` volume is root-owned including the CA keys; a safe switch needs a
  UID/GID decision, a verified host sysctl, and a rehearsed chown of the CA volume. The current
  container-root posture (read-only rootfs, `cap_drop: ALL`, `no-new-privileges`) remains accepted
  for now.
- **TLS material must not reach Git or an image.** Certificate/key extensions stay in `.gitignore`;
  `deploy/` and certificate/key extensions are excluded by `.dockerignore`; no Dockerfile copies
  them; only Caddy mounts the certificate directory and CA volumes. Static tests guard these rules.
- **Operational runbooks live in `docs/operations/`.** That new docs subfolder separates procedures
  from architecture notes; [tls-certificate-lifecycle.md](../operations/tls-certificate-lifecycle.md)
  is the first one. No top-level workspace or application folder is added.

## Alternatives

- **Enable the admin API and use `caddy reload`.** Rejected: it would add a local control plane that
  the threat model does not need, and ADR 012 explicitly disabled it. A restart is acceptable for a
  single internal instance.
- **Automate renewal now with ACME.** Rejected: it assumes a public DNS name, inbound validation, or
  an ACME-capable CA, none of which is known. Adding it would silently change the trust model.
- **Replace the certificate directory instead of the files inside it.** Rejected: Docker bind-mounts
  the directory inode; replacing the directory leaves the container reading the old files. The
  `current` symlink is inside the mounted directory and is the thing that changes.
- **Rename `fullchain.pem` and `privkey.pem` separately.** Rejected: each rename is atomic on its own,
  but the pair is not. A failure between the two renames can leave a new certificate with an old key,
  and a restart at that moment fails to serve TLS. One symlink rename removes the window.
- **Keep old certificates only in the backup system.** Rejected: rollback must work within seconds
  without depending on an off-host restore. Previous version directories stay next to the active one
  until retention removes them deliberately.
- **Delete `caddy_data` to "reset" TLS.** Rejected: for `internal-ca` it replaces the CA and breaks
  every trusting client; for both modes it destroys state that a restore may need.
- **Commit a self-signed development certificate for tests.** Rejected: it normalizes material in the
  repository and can be mistaken for a real deployment. Tests generate throwaway material under
  pytest's temporary directory.
- **Add a monitoring agent in this task.** Rejected: no alert channel, owner, or platform is decided;
  the runbook provides deterministic manual commands and exit codes until those exist.

## Consequences

- Organization certificates rotate manually. The 30-day entry is an operational obligation, not an
  automated property; a missed calendar entry leads to expiry.
- A certificate change is a short outage because the proxy restarts. The API, web, and database stay
  up; in-flight proxy requests fail. `SIGUSR1` can remove that outage once approved and rehearsed.
- Rollback requires the previous version directory to be kept and its fingerprint recorded. Restoring
  from backup is the fallback, not the first step.
- Losing the internal CA key without a verified backup means a new CA, a new root distribution, and
  an incident; there is no transparent recovery.
- Validation depends on OpenSSL 3.x on the operator host; the container's own `caddy validate` is the
  second, independent gate.
- Non-root remains a future hardening item with a migration cost on the CA volume and key ownership.
- If the admin API is ever enabled, this decision must be revisited: `caddy reload` would become
  available and the restart-based procedure would no longer be the only path.
