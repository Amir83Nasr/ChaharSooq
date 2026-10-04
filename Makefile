# charsooq — shortcuts for the documented pnpm/uv/compose workflow.
SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: build check db-migrate db-migrate-prod db-seed db-seed-prod db-seed-products db-up deploy-api dev-all dev-api dev-web docker-down docker-logs docker-up help install lint test typecheck

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
ADMIN_USER ?= admin ## Dev admin username for seed target
ADMIN_PASSWORD ?= secret123 ## Dev admin password for seed target

# ─── INSTALL / SETUP ──────────────────────────────────────
install: ## Install frontend and backend dependencies
	pnpm install
	uv sync

# ─── DEV / RUN ────────────────────────────────────────────
dev-web: ## Start frontend dev server (turbo)
	pnpm dev

dev-api: ## Start backend API with reload (expects postgres up)
	uv run --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload

dev-all: db-up migrate ## Start backend + frontend together (Ctrl-C stops both)
	uv run --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload & \
	pnpm dev & \
	wait

# ─── DATABASE: DEV ────────────────────────────────────────
db-up: ## Start dev postgres (own container, port 5433)
	docker compose -f $(COMPOSE_FILE) up -d postgres

db-migrate: db-up ## Apply Alembic migrations to dev database
	cd backend/api && uv run alembic upgrade head

db-seed: db-up ## Create dev admin user (ADMIN_USER / ADMIN_PASSWORD)
	ADMIN_USER="$(strip $(ADMIN_USER))" ADMIN_PASSWORD="$(strip $(ADMIN_PASSWORD))" \
	uv run --project backend/api python backend/api/scripts/seed_admin.py

# ─── DATABASE: PROD (NEON) ────────────────────────────────
db-migrate-prod: ## Apply Alembic migrations to prod Neon (reads .env.production)
	set -a; . ./.env.production; set +a; \
	cd backend/api && uv run alembic upgrade head

db-seed-prod: ## Create prod admin user from ADMIN_USER / ADMIN_PASSWORD
	set -a; . ./.env.production; set +a; \
	ADMIN_USER="$(strip $(ADMIN_USER))" ADMIN_PASSWORD="$(strip $(ADMIN_PASSWORD))" \
	uv run --project backend/api python backend/api/scripts/seed_admin.py

# ─── DOCKER ───────────────────────────────────────────────
docker-up: ## Start services with Docker Compose
	docker compose -f $(COMPOSE_FILE) up -d

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
	uv run --project backend/api ruff check .
	uv run --project backend/api ruff format --check .

typecheck: ## Run frontend typecheck and backend pyright
	pnpm typecheck
	uv run --project backend/api pyright

test: ## Run frontend and backend tests
	pnpm --filter @workspace/ui test
	uv run --project backend/api pytest -q

build: ## Build web app for production
	pnpm --filter web build

check: lint typecheck test ## Run lint + typecheck + test
