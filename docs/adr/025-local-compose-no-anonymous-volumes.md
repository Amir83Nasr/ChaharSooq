# ADR 025 — No anonymous volumes in the local stack

Date: 2026-11-21 · Status: accepted · Supersedes the web mount strategy in
[ADR 024](024-local-compose-hot-reload.md)

## Context

ADR 024 mounted the whole repository at `/app` in the local `web` container and
covered each `node_modules` directory and `.next` with an anonymous volume, so
host binaries could not shadow the Linux dependencies in the image. That works,
but every `docker compose up` leaves six hash-named anonymous volumes in Docker's
volume list. They are indistinguishable from real data and were mistaken for
orphaned files; they contain only regenerable dependency and build-cache copies.

The local stack's only volumes that hold state are `pgdata` (the PostgreSQL
cluster) and `backups` (logical archives). Production additionally uses
`caddy_data` and `caddy_config`; those are unchanged by this decision.

## Decision

- **Mount source directories, not the repository root.** `compose.local.yml`
  binds `apps/web/{app,components,fonts,lib,public}` and `packages/ui/src` into
  the dev image. Dependencies and `.next` stay in the image/container filesystem.
- **No anonymous volumes.** The local stack declares exactly two named volumes:
  `pgdata` and `backups`. No `volume` entry in the file omits a source.
- **Config and dependency edits require a rebuild.** Changes to package files,
  lockfiles, `next.config.ts`, `postcss.config.mjs`, or Dockerfiles need
  `make docker-build`; source edits still hot-reload. A new top-level source
  directory under `apps/web` or `packages/ui` must be added to the mount list.

## Consequences

Docker's volume list shows only the two stateful local volumes, so nothing needs
periodic cleanup. The web container no longer sees host `.env*` files or other
repository root files, which is safer than the previous whole-repo mount. The
mount list must be kept in step with new source directories, and config changes
are no longer picked up without an image rebuild.
