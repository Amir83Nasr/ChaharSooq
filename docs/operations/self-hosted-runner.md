# Self-hosted runner — ChaharSooq Production deploy

Status: **preparation and procedure only**. Nothing in this repository installs
or registers a runner, no runner has been registered, no GitHub secret was
created, and no Production host was modified. Execute the steps in this document
only during an approved change window on the designated host
(`market-linux`/Production) by an authorized operator.

Related: [release-management.md](release-management.md) ·
[production-runbook.md](production-runbook.md) ·
[deployment.md](../architecture/deployment.md) ·
[infrastructure-readiness.md](infrastructure-readiness.md) ·
[ADR 016](../adr/016-ci-cd-deploy-job.md) ·
[ADR 017](../adr/017-blue-green-deployment.md) ·
[`deploy/runner/`](../../deploy/runner/) ·
[`deploy/scripts/deploy.sh`](../../deploy/scripts/deploy.sh)

## 1. Purpose and trust boundary

The self-hosted runner exists only to run the **Production deploy job** in
[`.github/workflows/release.yml`](../../.github/workflows/release.yml):

- Trigger: `release.published` (stable, non-draft, non-prerelease) or an
  explicit manual dispatch with `deploy=true` for an existing stable published
  release.
- Target: `runs-on: [self-hosted, Linux, charsooq-production]`, environment
  `production`, minimal permissions (`contents: read`), no GitHub secrets.
- Work performed: checkout the released commit and run
  `bash deploy/scripts/deploy.sh` with digest-only image references. Non-secret
  host values come from `/etc/charsooq/production.env`; secrets remain as
  host-managed files under `CHARSOOQ_SECRETS_DIR`.

**Trust boundary:** any job that runs on this runner can execute arbitrary code
on the host as the runner account (and, if granted Docker access, can gain
effective control of the host/container stack). Therefore this runner must be
treated as Production infrastructure, not as a general CI runner.

## 2. Requirements (must be satisfied)

| Requirement                                    | How it is enforced / documented                                                                                                                                                  |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Repository-specific runner                     | Register the runner in the ChaharSooq repository (not org-level shared pool).                                                                                                    |
| Dedicated label `charsooq-production`          | Configure the label at registration; workflow already requires it. Do not add generic labels that untrusted workflows might target.                                              |
| Only trusted deployment jobs run on it         | No `pull_request` workflow targets this label; release workflow has no PR trigger; use GitHub runner groups and/or environment protection/review rules as available (section 6). |
| No access for PRs/untrusted code               | Keep repository Actions settings restrictive, do not allow fork PR workflows to use self-hosted runners, and do not target this label from PR/CI workflows.                      |
| Install/register documented                    | Sections 4–5 and runbook in section 10.                                                                                                                                          |
| Service and auto-start after reboot documented | Section 5.4.                                                                                                                                                                     |
| Least-privilege Docker access                  | Section 7.                                                                                                                                                                       |
| Limited access to Production files/secrets     | Section 8.                                                                                                                                                                       |
| Runner connection/status checkable             | Section 9.                                                                                                                                                                       |

## 3. Host prerequisites (before installation)

Perform these checks during preparation; do not guess values owned by IT.

- **Host:** Production server inside company private network, outbound access to
  GitHub/GHCR available, no inbound port opened for runner control.
- **OS/tools:** supported Linux (Ubuntu 24.04 on `market-linux` per existing
  docs), `systemd`, `bash`, `tar`, `curl`, `git` (optional but useful), and a
  SHA-256 verification tool (`sha256sum` or `shasum`).
- **Docker:** Docker Engine and Compose v2 installed and functional for
  Production operations; deploy script and Compose expect them.
- **Accounts:** a dedicated, non-root local user for the runner (example:
  `charsooq-runner`) and a controlled deployment checkout/service layout. Avoid
  running the runner as `root`.
- **Paths (expected):**
  - Runner install: `/opt/actions-runner-charsooq` (outside the repo checkout)
  - Deployment checkout: `/opt/charsooq` (approved path; must contain released
    `compose.production.yml`, `deploy/scripts/deploy.sh`,
    `deploy/caddy/active-upstream.caddy` and be writable where deploy requires:
    state/upstream file updates happen via configured paths)
  - Non-secret deploy env: `/etc/charsooq/production.env` (mode restrictive,
    readable by runner as needed, **not** a secret store)
  - State dir: `/etc/charsooq/state`
  - Secrets dir: `/etc/charsooq/secrets` (existing Production secret files;
    runner must not be able to read secret contents unless a specific, reviewed
    exception is required — deploy script does not read them)
- **Preflight helper:** run the read-only check from the repo checkout on the
  host (or copy the script): `bash deploy/runner/preflight.sh [runner.env]`.

## 4. Installation (do not register yet)

> **Do not run on Production now unless this change is approved.** The steps
> below describe the supported procedure. Registration requires a short-lived
> token generated in GitHub and must be performed interactively by an authorized
> operator.

### 4.1 Create the runner user and directories

Example (adjust to IT policy; review before execution):

```bash
# Host / root — state-changing (accounts and directories)
sudo useradd --create-home --system --shell /usr/sbin/nologin charsooq-runner || true
sudo install -d -m 0750 -o charsooq-runner -g charsooq-runner /opt/actions-runner-charsooq
sudo install -d -m 0750 -o root -g root /etc/charsooq-runner
# Place non-secret runner.env outside repo; never store tokens here.
```

- Do not place the runner inside `/etc/charsooq/secrets` or grant it read access
  to secret file contents.
- Keep `/etc/charsooq-runner/runner.env` mode `0640` or stricter and root-owned
  if it only contains non-secret values.

### 4.2 Download the GitHub Actions runner package

1. In GitHub: **Repository → Settings → Actions → Runners → New self-hosted
   runner**.
2. Select **Linux** and the correct architecture (`x64` or `arm64`) for
   `market-linux`.
3. On the host (as `charsooq-runner` in the runner directory), follow GitHub's
   displayed download commands for the **current** runner version. Do not copy a
   hard-coded version from this document without checking GitHub.
4. **Verify integrity:** GitHub provides checksums/signing guidance with the
   download instructions; verify the downloaded archive before extraction.

Example shape (replace version/arch/checksum with values from GitHub UI):

```bash
# Host / runner user — state-changing (downloads and extracts runner)
cd /opt/actions-runner-charsooq
curl -o actions-runner-linux-x64-<VERSION>.tar.gz -L https://github.com/actions/runner/releases/download/v<VERSION>/actions-runner-linux-x64-<VERSION>.tar.gz
# Verify checksum as instructed by GitHub, then:
tar xzf ./actions-runner-linux-x64-<VERSION>.tar.gz
```

### 4.3 Install dependencies (if required)

The runner package may require host dependencies:

```bash
# Host / root — state-changing
sudo /opt/actions-runner-charsooq/bin/installdependencies.sh
```

Review the script and run it only on the approved host.

## 5. Registration and service configuration

### 5.1 Obtain a registration token (ephemeral)

- Generate the token in **Repository → Settings → Actions → Runners → New
  self-hosted runner** (or the repository runner registration API by an
  authorized admin). The token is **short-lived** and must be used immediately.
- **Never** commit the token, store it in `runner.env`, write it to logs, or
  paste it into tickets/chat. Do not request or share real tokens in this repo.

### 5.2 Configure the runner (repository-specific, dedicated label)

Run configuration as the runner user in the runner directory:

```bash
# Host / runner user — state-changing (writes runner configuration)
cd /opt/actions-runner-charsooq
./config.sh \
  --url https://github.com/<owner>/ChaharSooq \
  --token '<EPHEMERAL_REGISTRATION_TOKEN>' \
  --name market-linux-charsooq-production \
  --labels charsooq-production \
  --work _work \
  --unattended \
  --replace
```

Notes:

- Use the **exact** dedicated label `charsooq-production`. Add OS labels only if
  needed and safe; the workflow already matches `[self-hosted, Linux,
charsooq-production]`.
- Do **not** add this runner to a broad/shared runner group that other
  repositories or untrusted workflows can select.
- `--replace` is only for re-registering the same runner identity when intended;
  understand its effect before use.
- For ephemeral/JIT/runner-group based controls, follow current GitHub
  documentation and organizational policy; prefer the most restrictive mode that
  still supports the release deploy flow.

### 5.3 Restrict workflow access (critical)

To ensure "only trusted deployment jobs run on it":

1. **Workflow design (already in repo):** only `release.yml` targets
   `charsooq-production`; no `pull_request` trigger exists in `release.yml`; CI
   uses GitHub-hosted runners.
2. **Repository Actions settings:** require admin review as appropriate, disable
   running workflows from forks on self-hosted runners, and restrict who can
   create/modify workflows and releases.
3. **Environment protection:** use the `production` environment (already
   referenced by the deploy job) with required reviewers/branch-tag rules as
   approved by policy so only authorized releases/tags can reach deployment.
4. **Runner groups (if available):** limit the runner/group to this repository
   and to selected workflows where GitHub supports it.
5. **Branch/tag protections:** protect `main` and release tags; only trusted
   maintainers should be able to publish releases.

No technical control here makes arbitrary code safe; these controls reduce who
can cause code to run on the Production host.

### 5.4 Install and start the service (auto-start after reboot)

GitHub's runner includes service scripts for `systemd`:

```bash
# Host / root or as instructed — state-changing (installs/enables service)
cd /opt/actions-runner-charsooq
sudo ./svc.sh install charsooq-runner
sudo ./svc.sh start
sudo ./svc.sh status
```

Enable and verify auto-start after reboot:

```bash
# Host — read-only/status checks
sudo systemctl status actions.runner.*.service --no-pager
sudo systemctl is-enabled actions.runner.*.service
```

(The exact unit name depends on repository/runner naming; confirm with
`systemctl list-units 'actions.runner*'`.)

After an approved reboot test (separate maintenance action, not performed now),
confirm the runner returns to **Idle/Online** in GitHub and the service is
active.

### 5.5 Configure job environment access

The deploy job expects host-provided non-secret values and writable paths:

- `/etc/charsooq/production.env` must exist and contain required
  `CHARSOOQ_*` values (including Blue/Green edge variables and protocol/TLS
  configuration: `CHARSOOQ_PUBLIC_SCHEME`, `CHARSOOQ_TLS_MODE`,
  `CHARSOOQ_CADDY_AUTO_HTTPS`, and `CHARSOOQ_CA_FILE` when HTTPS). Do not store
  GitHub secrets/tokens there and do not auto-generate Production values.
- `/etc/charsooq/state` (`CHARSOOQ_STATE_DIR`) must be a directory writable by
  the runner/deploy account so `deploy-state.env` can be persisted.
- `${CHARSOOQ_ACTIVE_UPSTREAM_FILE:-<checkout>/deploy/caddy/active-upstream.caddy}`
  must exist and be writable by the runner/deploy account; `deploy.sh` rewrites
  it atomically before Caddy reload. Keep write access limited to this file and
  the state directory only.
- The checkout used by the workflow (`GITHUB_WORKSPACE`) must contain the
  released `compose.production.yml` and `deploy/scripts/deploy.sh`.
- `bash deploy/runner/preflight.sh [env]` and `deploy.sh` must fail before any
  deployment/state change when required variables (including green slot vars) or
  required writable paths/probe prerequisites are missing.
- No Docker socket is mounted into application/proxy containers; do not expose it
  to untrusted contexts. The runner must not read Production secret file contents.

## 6. Runner connection status and health

Check status from multiple angles:

| Check                              | Command / location                                                            | Expected                                                  |
| ---------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------- |
| GitHub UI                          | Repository → Settings → Actions → Runners                                     | Runner **Idle** (online) with label `charsooq-production` |
| Service state                      | `sudo systemctl status actions.runner.*.service --no-pager`                   | `active (running)`                                        |
| Enabled on boot                    | `sudo systemctl is-enabled actions.runner.*.service`                          | `enabled`                                                 |
| Recent logs                        | `sudo journalctl -u actions.runner.*.service -n 200 --no-pager`               | No repeated auth/network errors                           |
| Runner diagnostics                 | `./svc.sh status` in runner dir; runner `_diag/` logs (review before sharing) | Healthy connection                                        |
| Network reachability (host policy) | outbound HTTPS to GitHub endpoints (section 11)                               | Reachable per firewall allow-list                         |
| Deploy job evidence                | Actions run logs for `Release Images` / `deploy`                              | Job picked up by correct runner label                     |

If the runner shows **Offline**, verify outbound access, DNS/proxy settings, time
sync, service state, and whether the runner was removed/replaced in GitHub.

## 7. Docker access — least privilege (required design)

### 7.1 Why this is sensitive

Docker access is effectively **host-administrative** access on most systems:

- Membership in the `docker` group allows a user to start containers, mount host
  paths, run privileged containers, and read/write many host resources.
  Treat `docker` group membership as equivalent to root for threat modeling.
- The deploy job must pull/run/inspect containers and execute Compose
  operations; therefore some Docker access is unavoidable for automation.

### 7.2 Recommended controls

1. **Dedicated runner account:** never run the runner as `root`.
2. **Minimize supplementary groups:** avoid adding the runner user to broad
   groups. If `docker` group membership is required, document and approve it as a
   high-privilege exception.
3. **Prefer controlled access patterns where feasible:** use a restricted Docker
   socket proxy, rootless Docker, or a tightly scoped deployment helper/sudoers
   rule for only the required Compose/Docker commands. Each option has
   operational trade-offs and must be validated against `deploy/scripts/deploy.sh`
   before adoption.
4. **No Docker socket exposure beyond need:** do not mount `/var/run/docker.sock`
   into untrusted contexts. Keep the host daemon configuration hardened per IT
   baseline.
5. **Limit filesystem mounts:** ensure the runner cannot modify arbitrary host
   paths outside its work/deploy directories. Production secret files must remain
   outside runner-readable scope.
6. **Image trust:** deploy only digest-pinned images from the approved release
   (already enforced by workflow/script). Do not grant registry credentials with
   broader scope than required.
7. **Auditability:** retain host/service logs per policy and review deployment
   runs in GitHub Actions history.

If least-privilege Docker isolation is not fully achievable on the current host,
record the residual risk explicitly and compensate with strict workflow/release
controls and host monitoring.

## 8. Access to Production files and secrets

| Path / asset                            | Runner access needed                                                  | Guidance                                                                                                                                                      |
| --------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/etc/charsooq/production.env`          | Read (non-secret deployment values)                                   | Restrictive permissions; no secrets/tokens inside.                                                                                                            |
| `/etc/charsooq/state`                   | Read/write                                                            | Needed to persist deploy state.                                                                                                                               |
| `/etc/charsooq/secrets/*`               | **Not required** by deploy script                                     | Keep owned/mode per Production runbook (e.g. `postgres_password` `999:999` `0440`, app secrets `10001:10001` `0400`). Do not add runner to these UIDs/groups. |
| `/opt/charsooq` checkout (if used)      | Read and limited write as required for deploy artifacts/upstream file | Keep separate from secrets; track provenance of released files.                                                                                               |
| Runner `_work` directory                | Read/write by runner                                                  | Contains checked-out code during jobs; treat as sensitive execution workspace and clean/protect appropriately.                                                |
| TLS material under `CHARSOOQ_TLS_DIR`   | Not required for routine deploy script                                | Do not grant runner access.                                                                                                                                   |
| SSH keys, cloud creds, unrelated tokens | None                                                                  | Do not store on runner host/account.                                                                                                                          |

**Secrets in logs:** the deploy script must not print secret values; the workflow
passes no GitHub secret to the deploy job. Do not enable shell tracing (`set -x`)
in production deploy paths.

## 9. Removal and decommissioning

Perform only during an approved maintenance/change window.

1. **Stop new deployments:** disable or remove the runner in GitHub (Repository →
   Settings → Actions → Runners) so no jobs are scheduled.
2. **On the host, stop and uninstall the service:**
   ```bash
   # Host / root — state-changing
   cd /opt/actions-runner-charsooq
   sudo ./svc.sh stop
   sudo ./svc.sh uninstall
   ```
3. **Remove runner registration from GitHub config:** obtain a removal token in
   GitHub if required and run:
   ```bash
   # Host / runner user — state-changing
   ./config.sh remove --token '<EPHEMERAL_REMOVE_TOKEN>'
   ```
4. **Clean up files:** remove `/opt/actions-runner-charsooq` and
   `/etc/charsooq-runner` only after confirming no needed logs/artifacts remain
   and per retention policy. Do **not** delete `/etc/charsooq/secrets`,
   `/etc/charsooq/production.env`, `/etc/charsooq/state`, database volumes, or
   deployment state required for rollback unless explicitly approved.
5. **Revoke access:** remove the runner user from privileged groups, rotate any
   credentials that may have been exposed (if applicable), and update
   documentation/inventory.
6. **Validate:** confirm the runner no longer appears online in GitHub and that
   Production services remain healthy.

## 10. Activation runbook (server-side, approved execution only)

Use this checklist when IT approves activation. Mark each step with date,
operator, and evidence. **Do not perform now.**

1. **Approve scope:** confirm host, maintenance window, rollback contact, and
   that no untrusted workflows can target the runner.
2. **Preflight:** run `bash deploy/runner/preflight.sh` and resolve hard
   failures (Docker/Compose, systemd, required paths, user layout).
3. **Prepare non-secret config:** create `/etc/charsooq-runner/runner.env` from
   `deploy/runner/runner.env.example` (no tokens/secrets).
4. **Verify deploy prerequisites:** `/etc/charsooq/production.env` exists with
   required Blue/Green values; `/etc/charsooq/state` exists with correct
   permissions; deployment checkout/release files and
   `deploy/caddy/active-upstream.caddy` are in place and writable as needed;
   outbound access to GitHub/GHCR confirmed (section 11).
5. **Install runner package:** download current version for host arch, verify
   checksum/signature, extract to runner dir, install dependencies if required.
6. **Register (ephemeral token):** run `config.sh` with
   `--url https://github.com/<owner>/ChaharSooq`,
   `--labels charsooq-production`, unique name, unattended mode as approved.
7. **Install/start service:** `svc.sh install/start/status`; confirm systemd
   enabled for reboot.
8. **Validate in GitHub:** runner shows **Idle** with correct labels; confirm
   repository/environment protections and that PR workflows cannot use it.
9. **Controlled deployment test:** trigger a safe, approved release deploy
   (or `workflow_dispatch` with `deploy=true` on a known-good published release)
   during a window; verify job runs on `charsooq-production`, Blue/Green
   script succeeds, health checks pass, and no secrets appear in logs.
10. **Post-activation:** record runner name, version, labels, service unit,
    account/groups, Docker access model, and evidence locations in operations
    records.

## 11. Required outbound network access (egress)

The host is outbound-only; allow HTTPS (TCP 443) egress as required. Exact
endpoints may change with GitHub features/regions; use GitHub's current
"Self-hosted runners" and "About GitHub's IP addresses/domains" guidance and
prefer domain-based allow-listing where possible.

| Purpose                                            | Destinations (typical)                                                                                                             | Notes                                                                                     |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Runner registration, job polling, control          | `github.com`, `api.github.com`                                                                                                     | Long-poll/HTTPS connections from runner to GitHub.                                        |
| Actions runtime/services                           | `*.actions.githubusercontent.com` (and subdomains used by Actions), `results-receiver.actions.githubusercontent.com` as applicable | Required for runner communication and job services; confirm current GitHub documentation. |
| Actions/artifacts/downloads used by runner/actions | `objects.githubusercontent.com`, `github-releases.githubusercontent.com`, and other GitHub content domains as needed               | `actions/checkout` and actions may fetch content.                                         |
| Container image pulls (deploy)                     | `ghcr.io`, `pkg-containers.githubusercontent.com`, auth/token endpoints as redirected                                              | Images are pulled by digest; public GHCR may still involve token/redirect endpoints.      |
| Time sync / DNS / package repos (host ops)         | Organization-approved NTP, DNS, OS/package mirrors                                                                                 | Not runner-specific but required for reliable operation.                                  |

**Not required:** inbound connectivity from GitHub to the host, public IP, port
forwarding, webhooks, or opening ports 80/443 to the internet for the runner.

## 12. Security risks — Docker access and workflows on a Production server

### 12.1 Docker access risks

- **Host compromise equivalence:** access to the Docker daemon/socket (directly
  or via `docker` group) typically allows mounting the host filesystem, starting
  privileged containers, loading kernel modules in some configurations, reading
  environment/secrets exposed to containers, and manipulating Production
  containers/volumes. Treat as root-equivalent unless a proven isolation boundary
  exists.
- **Production impact:** a mistaken or malicious `docker`/Compose command can
  stop services, replace images, alter networks, or (outside this script's
  safeguards) destroy data. The deploy script avoids destructive prune/down
  flags, but the runner account's capabilities still define the blast radius.
- **Lateral movement:** images/containers may contain credentials or trust
  relationships; compromising the runner can expose the deployment pipeline and
  anything the host account can reach.
- **Mitigations:** dedicated account, minimal groups, restricted socket/helper
  mechanisms where feasible, digest-only deploys, immutable reviewed workflows,
  limited writable paths, no access to secret files, and strong host auditing.

### 12.2 Running GitHub Actions workflows on Production

- **Arbitrary code execution:** workflow steps and checked-out repository content
  execute on the Production host. A malicious or compromised workflow/release
  process can run any command available to the runner account.
- **Supply-chain exposure:** actions (even pinned), downloaded tools, and
  container images are dependencies; compromise upstream can compromise the host.
  Pin actions (already practiced), review changes to release/deploy workflows,
  and protect who can publish releases/tags.
- **Secret and data exposure:** although this deploy job uses no GitHub secrets,
  the host contains production data paths and network access to the live system.
  Misconfiguration could expose sensitive state via logs, artifacts, or modified
  scripts.
- **Availability/reliability:** long or failed jobs, resource exhaustion, or
  concurrent misuse can affect Production operations. Concurrency controls and a
  dedicated runner reduce but do not eliminate this risk.
- **PR/fork abuse scenarios:** if a PR or untrusted workflow were ever routed to
  this runner, attacker-controlled code would run on Production. This must be
  prevented by trigger design, runner targeting, repository settings, and runner
  group/environment policies.
- **Mitigations:** repository-scoped dedicated runner, unique label, no PR
  triggers, protected releases/tags, `production` environment approvals as
  policy, minimal permissions, no stored GitHub production secrets, reviewed
  deploy script, and rapid removal procedure (section 9).

### 12.3 Residual risk statement

Even with the controls above, a self-hosted runner on the Production host
retains **high inherent risk** because deployment automation requires powerful
access. Acceptance of this design must be explicit, documented by the owning
team/IT, and paired with monitoring, least privilege, and strict change control.
