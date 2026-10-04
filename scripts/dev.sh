#!/bin/bash
# Charsooq helpers — keep in sync with README/CONTRIBUTING.
set -euo pipefail
cd "$(dirname "$0")/.."

cmd="${1:-help}"
case "$cmd" in
  dev) pnpm dev ;;
  check) pnpm lint && pnpm typecheck && pnpm --filter @workspace/ui test ;;
  backend-check)
    uv run --project backend/api ruff check .
    uv run --project backend/api ruff format --check .
    uv run --project backend/api pyright
    uv run --project backend/api pytest -q
    ;;
  openapi) uv run --project backend/api python backend/api/scripts/export_openapi.py ;;
  *) echo "usage: scripts/dev.sh {dev|check|backend-check|openapi}" ;;
esac
