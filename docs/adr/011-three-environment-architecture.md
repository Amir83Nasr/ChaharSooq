# ADR 011 — Three independent deployment environments

Date: 2026-11-12 · Status: accepted

## Context

Charsooq had one deployed stack — Vercel + FastAPI Cloud + Neon — documented as Production.
There was no separate environment to verify a release against Production behavior before real
data and users were affected. The organization now runs the operational application on its own
Ubuntu server (`market-linux`, `172.30.2.2`), while the managed cloud stack is still the fastest
way to rehearse a release.

Production data and secrets must not leak into development or testing, and a Production release
must be controlled and reversible.

## Decision

- Charsooq has exactly three environments:
  - **Development** — the developer MacBook; Next.js, FastAPI, and a local PostgreSQL database.
  - **Staging** — Vercel frontend, FastAPI Cloud backend, Neon database. It verifies new versions
    and frontend/backend integration before release.
  - **Production** — Docker Engine + Docker Compose on `market-linux`; Next.js, FastAPI, and an
    independently managed PostgreSQL.
- Each environment owns its configuration, secrets, and database. No secret or `DATABASE_URL` is
  shared. `.env.example` files list names and non-secret samples only.
- Migrations run only against their own environment's database. Production uses a controlled,
  single-runner migration step before the new API version starts.
- No automatic Production → Staging/Development data transfer. Any real data used outside
  Production requires a controlled, sanitized process.
- Release flow is Development → GitHub/CI → Staging → approval → Production. Production promotion
  is explicit; a push to `main` is not a Production release.
- Version traceability across the two infrastructures is based on the Git commit SHA. Production
  deploys a single image built from the approved commit and pinned by digest. A single Docker image
  digest is not assumed to be usable on Vercel/FastAPI Cloud; if artifact equivalence cannot be
  proven, the commit-to-artifact mapping is recorded.
- Staging keeps the current Vercel, FastAPI Cloud, and Neon setup until a replacement is designed
  and approved.
- Production exposes only the reverse proxy publicly, terminates TLS there, keeps PostgreSQL and
  the API on the internal network, and has scheduled, tested backups. Details still unknown are
  recorded as open decisions in the deployment document, not guessed.
- [docs/architecture/deployment.md](../architecture/deployment.md) is the operational source of
  truth; this ADR records the decision and links to it rather than duplicating the runbook.

## Alternatives

- **Keep the cloud stack as Production:** rejected — operational data and its database must be
  controlled on the organization's Ubuntu server.
- **Two environments (Development + Production):** rejected — no isolated place to verify a
  release, so every mistake would reach live data.
- **Use Vercel/FastAPI Cloud for Production:** rejected for the same reason as above; the stack is
  retained as Staging.
- **Assume one Docker image digest is portable between Staging and Production:** rejected — the
  build systems differ and the assumption is unproven.

## Consequences

- "Production" in older notes sometimes meant the managed cloud stack. It now means
  `market-linux`; the cloud stack is Staging. Documentation and runbooks must use the new terms.
- Existing `*-prod` Make targets, `.env.production`, and dev-to-prod sync scripts were written for
  the Neon-era production database. They need rework before they may touch `market-linux`.
- The application currently auto-migrates on boot. That remains acceptable for Development and
  Staging but must be replaced by a controlled Production migration step before Production is
  considered ready.
- `compose.yml` remains the development stack; Production needs a separate compose file.
- Several operational decisions remain open (registry, TLS, secrets, backups, deploy access,
  observability); they are tracked in the deployment document and must be resolved before go-live.
- Staging and Production share behavior, not infrastructure or configuration. A change that passes
  Staging still needs its Production-only concerns (migration timing, secrets, network, rollback)
  checked.
