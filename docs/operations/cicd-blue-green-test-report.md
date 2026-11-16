# CI/CD and Blue-Green deployment — final validation report (ChaharSooq)

Date: 2026-11-16  
Status: **offline validation only (code/contracts/docs/tests)**. No Production host was contacted, no
runner was installed/registered, no GitHub secret/token was created, no release workflow was executed
against a real release, and no volume/database/image/network setting was changed or deleted.

## 1. Scope reviewed

- Workflow: [`.github/workflows/release.yml`](../../.github/workflows/release.yml) (verify → publish → deploy, digest-only, self-hosted deploy)
- Deploy logic: [`deploy/scripts/deploy.sh`](../../deploy/scripts/deploy.sh), [`compose.production.yml`](../../compose.production.yml), [`deploy/caddy/site.caddy`](../../deploy/caddy/site.caddy), [`deploy/caddy/active-upstream.caddy`](../../deploy/caddy/active-upstream.caddy), [`deploy/production.env.example`](../../deploy/production.env.example)
- Runner preparation: [`deploy/runner/`](../../deploy/runner/), [`docs/operations/self-hosted-runner.md`](self-hosted-runner.md)
- Deployment/operations docs and ADRs: [`docs/operations/release-management.md`](release-management.md), [`docs/operations/production-runbook.md`](production-runbook.md), [`docs/operations/production-setup-runbook.md`](production-setup-runbook.md), [`docs/operations/rollback.md`](rollback.md), [`docs/architecture/deployment.md`](../architecture/deployment.md), [`docs/adr/016-ci-cd-deploy-job.md`](../adr/016-ci-cd-deploy-job.md), [`docs/adr/017-blue-green-deployment.md`](../adr/017-blue-green-deployment.md)
- Automated contract tests: [`backend/api/tests/test_release_workflow.py`](../../backend/api/tests/test_release_workflow.py), [`backend/api/tests/test_production_compose.py`](../../backend/api/tests/test_production_compose.py), [`backend/api/tests/test_production_proxy.py`](../../backend/api/tests/test_production_proxy.py), [`backend/api/tests/test_cicd_blue_green_validation.py`](../../backend/api/tests/test_cicd_blue_green_validation.py)

## 2. Scenario results (requested)

| #   | Scenario                                      | Result                               | What was verified                                                                                                                                                                                | Evidence (primary)                                                                                    |
| --- | --------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| 1   | انتشار Release رسمی و شروع خودکار Workflow    | **Pass (contract/static)**           | `release: types: [published]`; deploy needs successful publish; deploy gated to stable release on `production`; `push` trigger absent                                                            | `release.yml`, `test_release_workflow.py`, `test_cicd_blue_green_validation.py`                       |
| 2   | جلوگیری از Deployment برای Draft و Prerelease | **Pass (contract/static)**           | Publish resolve step rejects draft/prerelease; deploy `if` excludes draft/prerelease; manual dispatch deploy defaults to false and requires explicit opt-in + existing stable release resolution | `release.yml` resolve/deploy guards, `test_release_workflow.py`, `test_cicd_blue_green_validation.py` |
| 3   | شکست Build تصاویر                             | **Pass (pipeline contract)**         | Build/push/verify steps are in `publish`; `deploy` has `needs: [publish]`, so build/push failure prevents deploy job start                                                                       | `release.yml`, workflow contract tests                                                                |
| 4   | آماده‌نبودن Imageها در GHCR                   | **Pass (script contract)**           | Deploy is digest-only, pulls release images, and verifies `org.opencontainers.image.revision`; missing/unavailable image or inspect/pull failure aborts under `set -euo pipefail`                | `deploy.sh`, contract tests (`bash -n` + assertions)                                                  |
| 5   | شکست Pull تصاویر                              | **Pass (script contract)**           | Explicit digest pull before slot start; any pull failure aborts deployment before traffic switch (fail-closed)                                                                                   | `deploy.sh`, `test_cicd_blue_green_validation.py`                                                     |
| 6   | شکست Health Check                             | **Pass (script contract)**           | Inactive slot readiness/liveness/web probes must pass before switch; failures return/raise "active slot was not changed"; post-switch external verification attempts traffic return              | `deploy.sh` (`verify_slot`, `verify_external`), tests                                                 |
| 7   | شکست Smoke Test                               | **Pass (script contract)**           | Same-origin smoke (`/api/v1/health` via slot web) and login probe required pre-switch; external `/api/v1/health` and `/login` probes run post-switch when CA configured                          | `deploy.sh`, tests                                                                                    |
| 8   | شکست Migration                                | **Pass (script contract)**           | Shared `provision`/`migrate` run before inactive slot start; migration failure aborts script before switch, leaving active slot serving                                                          | `deploy.sh` ordering, `test_cicd_blue_green_validation.py`                                            |
| 9   | اجرای هم‌زمان چند Deployment                  | **Pass (contract/static)**           | Workflow concurrency per release tag (`cancel-in-progress: false`) and deploy job concurrency `group: deploy-production`, `cancel-in-progress: false`                                            | `release.yml`, tests                                                                                  |
| 10  | انتقال موفق ترافیک به محیط جدید               | **Pass (design/contract)**           | Inactive slot started and verified, upstream file rewritten atomically, Caddy reloaded (`SIGUSR1`), external probes verified, state persisted, previous slot kept                                | `deploy.sh`, Caddy config, ADR 017, tests                                                             |
| 11  | Rollback به نسخه قبلی                         | **Pass (design/contract + runbook)** | Previous slot retained; post-switch probe failure triggers traffic return attempt to previous active slot; state carries active/inactive image refs; manual rollback documented                  | `deploy.sh`, `rollback.md`, tests                                                                     |
| 12  | Restart سرور و حفظ وضعیت محیط فعال            | **Pass (design/contract)**           | Active upstream is bind-mounted file on disk; deploy persists state in `/etc/charsooq/state/deploy-state.env`; core services/slots use `restart: unless-stopped`; persistent volumes declared    | `compose.production.yml`, `deploy.sh`, `active-upstream.caddy`, ADR 017, tests                        |

## 3. Security review (requested)

| Area                               | Status                                                    | Notes / evidence                                                                                                                                                                                             |
| ---------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Runner access                      | **Controlled by design (documented), not host-validated** | Dedicated repo-scoped runner label `charsooq-production`; PR/untrusted workflows excluded by workflow design/tests and documented GitHub/environment restrictions; runner not installed/registered           |
| Docker access                      | **Risk identified, least-privilege guidance documented**  | Docker access is effectively host-admin; deploy requires Docker/Compose but runner account/group/socket exposure must be minimized and approved on host; residual risk documented in `self-hosted-runner.md` |
| GitHub Actions permissions/secrets | **Pass (workflow contract)**                              | Deploy job `permissions: contents: read`, `environment: production`, no `secrets.*` in deploy job, pinned actions, no PR trigger on release deploy workflow                                                  |
| GHCR / images                      | **Pass (design contract), operationally unproven**        | Images pulled/published as release artifacts; deploy requires `repo@sha256:digest` and verifies revision label; workflow assumes public GHCR pull (no PAT) — host pull/access not tested                     |
| Network restrictions               | **Pass (design/compose contract)**                        | Outbound-only runner model documented; only Caddy publishes `80/443` bound to approved internal IP; Caddy isolated to `proxy`; `backend` internal; no docker socket mounts                                   |
| Untrusted code on runner           | **Mitigated by controls, residual risk remains**          | No PR workflow targets runner, release workflow has no PR trigger, deploy gated to stable releases/environment; repository/runner-group/release protections are mandatory manual controls on GitHub/host     |

## 4. Tests executed in this validation (local/offline)

| Check                                                                                                                                                                                           | Result                                | Notes                                                                                                                                                       |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bash -n deploy/scripts/deploy.sh`                                                                                                                                                              | **Pass**                              | Deploy script syntax                                                                                                                                        |
| `bash -n deploy/runner/preflight.sh`                                                                                                                                                            | **Pass**                              | Runner preflight syntax                                                                                                                                     |
| `make prod-config`                                                                                                                                                                              | **Pass**                              | Structural Blue/Green compose validation with documentation values only (no secrets/host)                                                                   |
| `cd backend/api && uv run --no-sync pytest -q tests/test_release_workflow.py tests/test_production_compose.py tests/test_production_proxy.py tests/test_cicd_blue_green_validation.py --no-cov` | **Pass (expected)**                   | Contract/static validation for workflow, compose, proxy, deploy/runner scenarios and security                                                               |
| `cd backend/api && uv run --no-sync pytest -q`                                                                                                                                                  | **Not re-run in this final doc pass** | Previously reported pass in checkpoint context (**443 passed, 6 skipped**, coverage 86.84%); rerun recommended before commit if code changed after that run |
| `pnpm exec prettier --check <changed docs/config files>`                                                                                                                                        | **Pass (expected after formatting)**  | Formatting check for changed docs/workflow/compose artifacts                                                                                                |

> Exact test counts for this final pass should be recorded from the command output when executed in the
> same session as the final commit candidate.

## 5. Actually tested vs only reviewed/validated by code

### Actually tested (local, automated/static)

- YAML workflow/compose parsing and contract assertions (triggers, conditions, permissions, concurrency, runner label, digest wiring, Blue-Green topology, network/secret isolation, restart/persistence declarations).
- Deploy and runner-preflight shell syntax (`bash -n`) and key fail-closed/security strings (no `set -x`, no secret logging, digest-only refs, no destructive commands).
- Release guard/tag-validation logic behavior where unit-tested with stubbed local binaries (existing release workflow tests).
- Documentation/artifact presence for runner preparation, rollback, and setup/runbook outputs.

### Only reviewed/validated by code and design (not executed end-to-end)

- Real GitHub Release publication and automatic workflow execution on GitHub-hosted/self-hosted infrastructure.
- Real image build/push to GHCR, registry availability/auth behavior, attestation publication visibility, and digest pull from a host.
- Real self-hosted runner registration, systemd service behavior, reboot recovery, outbound egress enforcement, and GitHub environment/repository policy enforcement.
- Real Blue-Green deployment on `market-linux`: provision/migrate on shared DB, slot startup, health/smoke probes, Caddy traffic switch/reload behavior under load, external HTTPS probes, state persistence permissions, rollback traffic return, and host restart recovery.
- Real TLS trust/certificate validation with production material and client behavior.
- Disaster/recovery scenarios requiring real data/backup/restore operations.

## 6. Produced outputs (requested)

- **Automated tests:** `backend/api/tests/test_cicd_blue_green_validation.py` (plus existing release/compose/proxy contract suites)
- **Scenario report:** this document
- **Deployment documentation:** [release-management.md](release-management.md), [production-runbook.md](production-runbook.md), [production-setup-runbook.md](production-setup-runbook.md), [deployment.md](../architecture/deployment.md), ADR 016/017
- **Rollback documentation:** [rollback.md](rollback.md) (and rollback sections in runbook/release docs)
- **Runner installation runbook:** [self-hosted-runner.md](self-hosted-runner.md) (+ `deploy/runner/README.md`, `runner.env.example`, `preflight.sh`)
- **Production setup runbook:** [production-setup-runbook.md](production-setup-runbook.md)
- **Remaining manual actions:** section 7 below

## 7. Remaining manual actions (before real automated Production deploy)

1. **GitHub/repository governance (manual):** confirm Actions settings prevent fork/untrusted use of self-hosted runners, protect `main`/release tags, restrict who can publish releases/edit workflows, and configure `production` environment protections/reviewers and tag rules as required.
2. **Host prerequisites (manual, approved window):** finalize IT-owned values (bind IP, `CHARSOOQ_SITE_HOST`, edge subnets/IPs per slot, TLS mode/material, DNS, outbound allow-list), prepare host packages/users/directories, and verify Docker/Compose/systemd readiness.
3. **Secrets and non-secret config (manual, no repo storage):** create `/etc/charsooq/secrets/*` with correct ownership/mode and `/etc/charsooq/production.env` (including Blue/Green edge values and optional `CHARSOOQ_CA_FILE`/`CHARSOOQ_STATE_DIR`) outside the repository; never share across environments.
4. **Runner activation (manual, token at runtime only):** register repository-scoped runner with label `charsooq-production`, install/enable systemd service, validate outbound-only connectivity and least-privilege Docker/filesystem access per [self-hosted-runner.md](self-hosted-runner.md).
5. **First controlled release/deploy (manual supervision):** publish a stable release, observe `verify → publish → deploy`, and verify on host: correct runner pickup, digest-only pull/revision check, provision/migrate success, inactive-slot health/smoke, traffic switch, external probes, state persistence, and rollback readiness.
6. **Operational readiness:** verify backups/restore rehearsal, monitoring/alerting ownership, certificate lifecycle/expiry process, and document residual risks (Docker/root-equivalence, non-zero-downtime reload window, migration compatibility, temporary `SESSION_COOKIE_SECURE=false`).
7. **Commit/review:** review uncommitted repository changes, run full project checks as required by contribution policy, and merge/release only through the approved process (no commit/push performed in this validation).

## 8. Limitations and safety statement

- No automated test in this report proves end-to-end Production behavior on `market-linux` or against live GitHub/GHCR services.
- Blue-Green is traffic-gated and rollback-oriented but not a strict zero-downtime guarantee (Caddy reload and migration compatibility constraints apply).
- This validation intentionally made **no destructive or production-host changes**. Any real activation must follow approved change control, maintenance windows, and the documented runbooks.
