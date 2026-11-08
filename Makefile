# charsooq — shortcuts for the documented pnpm/uv/compose workflow.
SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: build check clean-build clean-cache db-clear-products db-migrate db-migrate-prod db-seed db-seed-demo db-seed-parsina db-seed-prod db-sync-dev-to-prod sync-dev-to-prod sync-prod dev-to-prod db-up db-validate db-wait deploy-api dev-all dev-api dev-web docker-build docker-down docker-logs docker-up doctor help install lint openapi-check test test-e2e typecheck

# ─── HELP ─────────────────────────────────────────────────
help: ## Show this help message
	@bo=""; g=""; bl=""; d=""; r=""; \
	if [ -z "$${NO_COLOR:-}" ] && [ -t 1 ]; then \
		bo=$$'\033[1m\033[32m'; g=$$'\033[32m'; bl=$$'\033[34m'; d=$$'\033[2m'; r=$$'\033[0m'; \
	fi; \
	printf "%sChaharSooq%s%s — Persian-first admin panel (Next.js + FastAPI)%s\n\n" "$$bo" "$$r" "$$d" "$$r"; \
	printf "Usage:  make %s[VARIABLE=value]%s %s<TARGET>%s\n\n" "$$bl" "$$r" "$$bl" "$$r"; \
	printf "%sCommands:%s\n" "$$g" "$$r"; \
	awk -v g="$$g" -v bl="$$bl" -v r="$$r" '/^# ─── / { sec=$$0; sub(/^# ─── /, "", sec); sub(/ ─*$$/, "", sec); cur=sec; next } /^[a-z][a-z0-9_.-]*:[^=]*##/ { name=$$1; sub(/:.*/, "", name); if (name == "help") next; if (cur != "" && cur != last) { printf "  %s%s:%s\n", g, cur, r; last=cur } desc=$$0; sub(/^[^#]*##[[:space:]]*/, "", desc); printf "    %s%-22s%s %s\n", bl, name, r, desc }' $(MAKEFILE_LIST); \
	printf "\n%sOptions:%s\n" "$$g" "$$r"; \
	awk -v bl="$$bl" -v r="$$r" '/^[A-Z][A-Z0-9_]*[[:space:]]*\?=.*##/ { desc=$$0; sub(/^[^#]*##[[:space:]]*/, "", desc); printf "  %s%s=%s%s %s\n", bl, $$1, $$3, r, desc }' $(MAKEFILE_LIST)

# ─── CONFIG / VARIABLES ───────────────────────────────────
COMPOSE_FILE ?= compose.yml ## Compose file used by up/down/logs
ADMIN_USER ?= admin ## Admin username for db-seed and db-seed-prod
DEV_ADMIN_PASSWORD ?= secret123 ## Dev-only admin password for db-seed (never used in prod)
DB_PORT ?= 5433 ## Host port of the dev postgres db-wait/dev-api expect
YES ?= 0 ## Set YES=1 to skip the confirmation prompt for db-sync-dev-to-prod

# ─── INSTALL / SETUP ──────────────────────────────────────
install: ## Install frontend and backend dependencies and git hooks
	pnpm install --frozen-lockfile
	uv sync --locked
	pnpm exec lefthook install

# Caches are always regenerable and gitignored: removing them never loses source.
clean-cache: ## Remove regenerable tool caches (turbo, ruff, pytest, __pycache__)
	rm -rf .turbo apps/web/.turbo .ruff_cache backend/api/.ruff_cache .pytest_cache backend/api/.pytest_cache
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +

clean-build: ## Remove build output and test artifacts (.next, playwright)
	rm -rf apps/web/.next apps/web/test-results apps/web/playwright-report

# ─── DEV / RUN ────────────────────────────────────────────
dev-web: ## Start frontend dev server (turbo)
	pnpm dev

dev-api: db-wait ## Start backend API with reload (waits for postgres first)
	# --no-sync: reuse the installed venv offline (`make install` re-syncs).
	uv run --no-sync --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload

dev-all: db-migrate ## Start backend + frontend together (stops both if either exits)
	@uv run --no-sync --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload & \
	api=$$!; \
	pnpm dev & \
	web=$$!; \
	trap 'kill $$api $$web 2>/dev/null' INT TERM EXIT; \
	while kill -0 $$api 2>/dev/null && kill -0 $$web 2>/dev/null; do sleep 1; done; \
	echo "dev-all: one server exited - stopping the other"

# ─── DATABASE: DEV ────────────────────────────────────────
db-up: ## Start dev postgres (own container, port 5433)
	docker compose -f $(COMPOSE_FILE) up -d postgres

db-wait: ## Wait up to 20s for dev postgres to accept connections (no DB needed otherwise)
	@for i in $$(seq 1 20); do \
		python3 -c "import socket; s = socket.create_connection(('127.0.0.1', $(DB_PORT)), timeout=2); s.close()" 2>/dev/null \
		&& { echo "postgres: accepting connections on 127.0.0.1:$(DB_PORT)"; exit 0; } \
		|| sleep 1; \
	done; \
	echo "postgres is not reachable on 127.0.0.1:$(DB_PORT) - run make db-up" >&2; exit 1

db-migrate: db-up ## Apply Alembic migrations to dev database
	cd backend/api && uv run --no-sync alembic upgrade head

db-seed: db-migrate ## Create dev admin user (ADMIN_USER, ADMIN_PASSWORD or DEV_ADMIN_PASSWORD)
	ADMIN_USER="$(strip $(ADMIN_USER))" ADMIN_PASSWORD="$(strip $(or $(ADMIN_PASSWORD),$(DEV_ADMIN_PASSWORD)))" \
	uv run --no-sync --project backend/api python backend/api/scripts/seed_admin.py

db-seed-parsina: db-migrate ## Upsert data/parsina.csv into dev DB (keeps product ids + links)
	uv run --no-sync --project backend/api python backend/api/scripts/seed_parsina_products.py

db-seed-demo: db-seed-parsina ## Fill dev demo competitor prices, daily changes, weights and price bounds
	uv run --no-sync --project backend/api python backend/api/scripts/seed_demo_competitors.py

db-clear-products: db-migrate ## Delete all products + competitor listings from dev DB (refuses production)
	uv run --no-sync --project backend/api python backend/api/scripts/clear_products.py

# ─── DATABASE: PROD (NEON) ────────────────────────────────
# NOTE: never `set -a; . .env` here — DATABASE_URL contains `&` and shell
# sourcing dies with `parse error near '&'`, silently falling back to the
# local dev database. `uv --env-file` parses dotenv safely instead.
db-migrate-prod: ## Manually apply migrations to prod Neon (fallback; deploys auto-migrate on boot)
	cd backend/api && uv run --no-sync --env-file $(CURDIR)/.env.production alembic upgrade head

db-seed-prod: ## Create prod admin user (requires ADMIN_PASSWORD=... on the command line)
	@test -n "$(strip $(ADMIN_PASSWORD))" || { echo "ADMIN_PASSWORD is required for db-seed-prod" >&2; exit 1; }
	ADMIN_USER="$(strip $(ADMIN_USER))" ADMIN_PASSWORD="$(strip $(ADMIN_PASSWORD))" \
	uv run --no-sync --project backend/api --env-file $(CURDIR)/.env.production python backend/api/scripts/seed_admin.py

# ─── DATABASE: SYNC DEV → PROD ─────────────────────────────
db-sync-dev-to-prod: ## Upsert dev data + missing competitor links into prod Neon (never deletes; reads .env.production)
	@test -f $(CURDIR)/.env.production || { echo ".env.production is required" >&2; exit 1; }
	uv run --no-sync --project backend/api --env-file $(CURDIR)/.env.production python backend/api/scripts/sync_dev_to_prod.py $(if $(filter 1,$(YES)),--yes,)

# ─── Aliases (dev → prod sync) ───────────────────────────
sync-dev-to-prod sync-prod dev-to-prod: db-sync-dev-to-prod ## Alias for db-sync-dev-to-prod

# ─── DATABASE: VALIDATE (NO DB NEEDED) ───────────────────
db-validate: ## Validate migrations offline: single head + SQL renders cleanly
	cd backend/api && uv run --no-sync alembic heads
	cd backend/api && uv run --no-sync alembic upgrade head --sql > /dev/null
	@echo "migrations validate: single head, offline SQL OK"

# ─── DOCTOR ───────────────────────────────────────────────
doctor: ## Check toolchain, env files, and service reachability
	@node --version && pnpm --version
	@python3 --version && uv --version
	@docker info > /dev/null 2>&1 && echo "docker: ok" || echo "docker: NOT RUNNING"
	@test -f backend/api/.env.local || echo "missing backend/api/.env.local (copy from .env.example)"
	@test -f apps/web/.env.local || echo "missing apps/web/.env.local (copy from .env.example)"
	@cd backend/api && uv run --no-sync alembic heads
	@docker compose -f $(COMPOSE_FILE) ps postgres 2>/dev/null | grep -q healthy && echo "postgres: healthy" || echo "postgres: not healthy (run make db-up)"

# ─── DOCKER ───────────────────────────────────────────────
docker-build: ## Build Docker images (web + api)
	docker compose -f $(COMPOSE_FILE) build

docker-up: ## Start services with Docker Compose (rebuild images)
	docker compose -f $(COMPOSE_FILE) up -d --build

docker-down: ## Stop Docker Compose services
	docker compose -f $(COMPOSE_FILE) down

docker-logs: ## Follow Docker Compose logs
	docker compose -f $(COMPOSE_FILE) logs -f

# ─── DEPLOY ───────────────────────────────────────────────
deploy-api: ## Deploy backend API to FastAPI Cloud (run from backend/api)
	cd backend/api && uvx --with 'fastapi[standard]' fastapi deploy

# ─── QUALITY / CHECKS ─────────────────────────────────────
lint: ## Run frontend lint and backend ruff checks
	pnpm lint
	pnpm format:check
	uv run --no-sync --project backend/api ruff check .
	uv run --no-sync --project backend/api ruff format --check .

typecheck: ## Run frontend typecheck and backend pyright
	pnpm typecheck
	uv run --no-sync --project backend/api pyright

test: ## Run frontend and backend tests
	pnpm test
	# Run from backend/api so pytest reads its pyproject (testpaths, coverage gate).
	cd backend/api && uv run --no-sync pytest -q

test-e2e: build ## Run Playwright e2e against the production build
	pnpm --filter web test:e2e

openapi-check: ## Fail if backend/api/openapi.json is stale (read-only, no DB needed)
	uv run --no-sync --project backend/api python backend/api/scripts/check_openapi_fresh.py

build: ## Build web app for production
	pnpm --filter web build

check: lint typecheck test db-validate openapi-check ## Run lint + typecheck + test + offline migration and OpenAPI validation