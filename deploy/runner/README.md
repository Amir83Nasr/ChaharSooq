# Production self-hosted runner (preparation)

This directory contains **preparation material only** for the GitHub Actions
self-hosted runner used by ChaharSooq's Production deploy job. Nothing here
installs or registers a runner, and no file here may contain a secret,
registration token, private key, or Production credential.

## Contents

- `runner.env.example` — non-secret template for runner identity and paths.
  Copy it **outside** the repository (for example `/etc/charsooq-runner/runner.env`).
- `preflight.sh` — read-only host checks (Docker/Compose/systemd/tooling/path
  hints). It does not change state and does not read secret values.

## Scope

- Runner scope: **repository-specific** runner for the ChaharSooq repository.
- Dedicated label: `charsooq-production` (must match
  [`.github/workflows/release.yml`](../../.github/workflows/release.yml)).
- Purpose: run the **trusted release deploy job only**. Pull requests and other
  untrusted workflows must never execute on this runner.

## Before activation

1. The runner is repository-scoped, labeled `charsooq-production`, and must run only trusted
   release deploy jobs — never pull requests or other untrusted workflows. Keep it outbound-only,
   with no access to secret files, and use a dedicated non-root account (the `docker` group is
   root-equivalent).
2. Complete installation, registration, service setup, access control, and removal on the approved
   host. Obtain the registration token at registration time; never store it in this repository.
3. Obtain the registration token from GitHub at registration time; do not store
   it in files committed to this repository.
4. Do not run any install/register command against Production until the change
   is approved and the prerequisites are satisfied.

## Status

No runner is installed or registered by this repository state. The Production
host has not been modified.
