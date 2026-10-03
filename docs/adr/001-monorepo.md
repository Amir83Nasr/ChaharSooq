# ADR 001 — Monorepo (pnpm workspaces + Turborepo + uv)

Date: 2026-10-04 · Status: accepted

## Context

Charsooq needs a Next.js frontend and a FastAPI backend in one repo with shared quality gates and docs.

## Decision

- pnpm workspaces (`apps/*`, `packages/*`) + Turborepo pipelines for lint/typecheck/test/build.
- uv workspace (`pyproject.toml` root + `backend/api`) with committed `uv.lock`; `pnpm-lock.yaml` committed.
- No extra packages/workspaces without architectural reason.

## Alternatives

- Separate repos: rejected — doubles CI/docs drift for one product.
- npm/pip: rejected — spec mandates pnpm/uv.

## Consequences

- Single `pnpm lint|typecheck|build` + `uv run` backend commands; CI mirrors them.
- Lockfiles must stay in sync on every dependency change.
