# ADR 033 — Automatic Production deploy via release polling

Date: 2026-11-24 · Status: accepted

## Context

[ADR 018](018-simple-production-deploy.md) established a single-slot, digest-pinned,
health-gated Production deploy that an operator runs manually with `make prod-deploy`
on the host. [ADR 021](021-github-release-deploy-discovery.md) made the published
GitHub Release the single discovery signal. This works, but every release still
requires a human to log into the server and run the command.

The Production host lives on an internal network: inbound SSH from the public
internet is impossible. The host itself does have outbound internet access, so it
can reach the GitHub API. A GitHub Actions runner on the host is explicitly
rejected by ADR 018 (no untrusted workflow on the host).

## Decision

- A small **outbound-only polling agent** runs on the Production host as a
  systemd timer (default every 5 minutes). It reads `releases/latest` from the
  GitHub API and compares the tag with the last successfully deployed release
  recorded in a host-local state file.
- When a newer **published, non-draft, non-prerelease** Release appears, the
  agent calls the existing `deploy/scripts/deploy.sh` with the two digest
  references from that release body. The deploy script is the **only** deploy
  path; the agent adds no new deployment logic, no image building, and no
  workflow execution on the host.
- The state file (`/var/lib/charsooq/last-deployed-release`, root-only) is updated
  **only after** `deploy.sh` exits successfully. On failure the agent logs the
  error and retries on the next tick, so a transient GitHub/network/image-pull
  failure heals itself.
- No credentials are required for a public repository. For a private repository
  a minimally-scoped `GITHUB_TOKEN` may be exported in `production.env`; it is
  never written to disk by the agent and is passed through a `0600` header file,
  as in `deploy.sh`.
- The agent never starts during a PostgreSQL major-version mismatch: `deploy.sh`
  keeps its fail-closed cluster check. An 18→19 data cutover remains a manual,
  operator-supervised step ([ADR 028](028-postgresql-19-upgrade-readiness.md)).
- Installation is explicit: `make prod-watch-install` on the host. Until an
  operator installs the timer, behaviour is unchanged (manual deploy only).

## Alternatives

- **GitHub Actions with SSH into the host.** Rejected: no inbound connectivity and
  it would move deploy control off the host.
- **Self-hosted Actions runner on the host.** Rejected by ADR 018: it executes
  untrusted workflow code on the Production host.
- **Webhook + cloud relay.** Rejected: needs extra public infrastructure and an
  inbound path; polling over outbound-only connectivity is simpler and matches
  the existing release-discovery design.

## Consequences

- A release becomes visible on Production within one poll interval (5 minutes)
  instead of requiring manual intervention.
- The Release workflow in [ADR 019](019-release-publication-after-image-verification.md)
  stays authoritative: CI still verifies images before publishing the Release,
  and the agent only ever deploys a published, verified Release.
- The state file is host-local state outside the repository; it is never committed
  or baked into an image.
- The agent's log is written to the host's journal (`journalctl -u charsooq-release-watch`).
- Rollback is unchanged: the operator pins an earlier release with
  `./deploy/scripts/deploy.sh vX.Y.Z` and writes that tag to the state file to
  stop the agent from immediately re-deploying the newer release.
