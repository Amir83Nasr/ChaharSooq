# ADR 024 — Local compose hot reload

Date: 2026-11-20 · Status: accepted · Supersedes the development file name in
[ADR 011](011-three-environment-architecture.md) · Web mount strategy superseded by
[ADR 025](025-local-compose-no-anonymous-volumes.md)

## Context

The local stack used `compose.yml` and ran the same production-style images as released artifacts:
a compiled Next.js standalone server and a multi-worker uvicorn process. Every source edit required
`docker compose build`, which made the local loop slow and blurred the line between development
and Production images. ADR 011 requires a separate development stack; the file name did not make
that separation obvious.

## Decision

- **Rename the development file to `compose.local.yml`.** It is the only local Compose file;
  `compose.production.yml` stays independent and unchanged in behavior. `make docker-*` targets
  use the renamed file through `COMPOSE_FILE`.
- **Add explicit development image stages.** `Dockerfile.api` gains `api-dev` (uvicorn with
  `--reload`, one process, same runtime tools) and `Dockerfile.web` gains `web-dev` (dependency
  layer plus `next dev`). The production stages and release builds are untouched.
- **Bind-mount source, keep dependencies in the image.** The API mounts `backend/api/{app,
migrations,scripts}`; the web service mounts the repository at `/app` with anonymous volumes
  over each `node_modules` and `.next`, so host binaries and host build output never replace the
  image's dependencies. Changes to source appear live without a rebuild.
- **Build on dependency changes only.** `make docker-up` no longer rebuilds on every start; Compose
  builds an image if it is missing, otherwise the existing dev image is reused. Changes to
  lockfiles, Dockerfiles, or installed system packages still require `make docker-build`.

## Consequences

Development edits are visible immediately in both apps, and the local stack can no longer be
mistaken for the released image set. The whole repository is visible inside the local web
container, so local `.env*` files must contain development-only values. Polling or filesystem
events depend on the host's Docker file-sharing implementation; a rebuild is never needed for
source edits, but a stale dependency layer can still require `make docker-build`.
