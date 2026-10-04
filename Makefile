# charsooq — shortcuts for the documented pnpm/uv/compose workflow.
SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: api build check db-up dev dev-all down help install lint logs migrate seed seed-products test typecheck up

# ─── HELP ─────────────────────────────────────────────────
help: ## Show this help message
	@bo=""; g=""; bl=""; d=""; r=""; \
	if [ -z "$${NO_COLOR:-}" ] && [ -t 1 ]; then \
		bo=$$'\033[1m\033[32m'; g=$$'\033[32m'; bl=$$'\033[34m'; d=$$'\033[2m'; r=$$'\033[0m'; \
	fi; \
	printf "%sChaharSooq%s%s — Persian-first admin panel (Next.js + FastAPI)%s\n\n" "$$bo" "$$r" "$$d" "$$r"; \
	printf "Usage:  make %s[VARIABLE=value]%s %s<TARGET>%s\n\n" "$$bl" "$$r" "$$bl" "$$r"; \
	printf "%sCommands:%s\n" "$$g" "$$r"; \
	awk -v bl="$$bl" -v r="$$r" '/^[a-z][a-z0-9_.-]*:[^=]*##/ { name=$$1; sub(/:.*/, "", name); desc=$$0; sub(/^[^#]*##[[:space:]]*/, "", desc); printf "  %s%-20s%s %s\n", bl, name, r, desc }' $(MAKEFILE_LIST); \
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
dev: ## Start frontend dev server (turbo)
	pnpm dev

api: ## Start backend API with reload (expects postgres up)
	uv run --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload

dev-all: db-up migrate ## Start backend + frontend together (Ctrl-C stops both)
	uv run --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload & \
	pnpm dev & \
	wait

# ─── DEV DATABASE ─────────────────────────────────────────
db-up: ## Start dev postgres (own container, port 5433)
	docker compose -f $(COMPOSE_FILE) up -d postgres

migrate: db-up ## Apply Alembic migrations to dev database
	cd backend/api && uv run alembic upgrade head

seed: db-up ## Create dev admin user (ADMIN_USER / ADMIN_PASSWORD)
	ADMIN_USER="$(strip $(ADMIN_USER))" ADMIN_PASSWORD="$(strip $(ADMIN_PASSWORD))" \
	uv run --project backend/api python backend/api/scripts/seed_admin.py

seed-products: db-up ## Insert demo products (idempotent, safe to re-run)
	uv run --project backend/api python backend/api/scripts/seed_products.py

up: ## Start services with Docker Compose
	docker compose -f $(COMPOSE_FILE) up -d

down: ## Stop Docker Compose services
	docker compose -f $(COMPOSE_FILE) down

logs: ## Follow Docker Compose logs
	docker compose -f $(COMPOSE_FILE) logs -f

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
