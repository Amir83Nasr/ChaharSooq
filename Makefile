# charsooq — shortcuts for the documented pnpm/uv/compose workflow.
SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: build check install help help-all doctor \
	clean clean-build clean-cache format \
	dev-web dev-api dev-all \
	db-up db-down db-wait db-migrate db-bootstrap-owner db-seed db-seed-parsina db-seed-demo \
	db-clear-products db-validate db-sync-dev-to-staging db-seed-demo-staging \
	sync-dev-to-staging sync-staging dev-to-staging \
	docker-build docker-up docker-down docker-logs deploy-api \
	local-up local-down \
	prod-config prod-build prod-deploy prod-pull prod-image-revision \
	prod-provision prod-migrate prod-bootstrap-owner prod-up prod-ps prod-logs \
	prod-down prod-caddy-validate tls-validate tls-activate tls-rollback \
	lint typecheck test test-e2e openapi-check

# ─── HELP ─────────────────────────────────────────────────
# `make help` lists only targets whose description starts with @user;
# `make help-all` lists every target. The marker lives in the description
# itself, so there is no separate list of shortcuts to keep in sync.
help help-all: ## Show the short user list (help) or every target (help-all)
	@mode=all; [ "$@" = "help" ] && mode=user; \
	bo=""; g=""; bl=""; d=""; r=""; \
	if [ -z "$${NO_COLOR:-}" ] && [ -t 1 ]; then \
		bo=$$'\033[1m\033[32m'; g=$$'\033[32m'; bl=$$'\033[34m'; d=$$'\033[2m'; r=$$'\033[0m'; \
	fi; \
	printf "%sChaharSooq%s%s — Persian-first admin panel (Next.js + FastAPI)%s\n\n" "$$bo" "$$r" "$$d" "$$r"; \
	printf "Usage:  make %s[VARIABLE=value]%s %s<TARGET>%s\n\n" "$$bl" "$$r" "$$bl" "$$r"; \
	printf "%sCommands:%s\n" "$$g" "$$r"; \
	awk -v g="$$g" -v bl="$$bl" -v r="$$r" -v mode="$$mode" '/^# ─── / { sec=$$0; sub(/^# ─── /, "", sec); sub(/ ─*$$/, "", sec); cur=sec; next } /^[a-z][a-z0-9_.-]*:[^=]*##/ { name=$$1; sub(/:.*/, "", name); desc=$$0; sub(/^[^#]*##[[:space:]]*/, "", desc); user=(desc ~ /^@user[[:space:]]+/); sub(/^@user[[:space:]]+/, "", desc); if (mode == "user" && !user) next; if (mode == "user") cur="USER SHORTCUTS"; if (cur != "" && cur != last) { printf "  %s%s:%s\n", g, cur, r; last=cur } printf "    %s%-22s%s %s\n", bl, name, r, desc }' $(MAKEFILE_LIST); \
	if [ "$$mode" = "user" ]; then printf "\n  Run %smake help-all%s to see every target.\n" "$$bl" "$$r"; fi; \
	printf "\n%sOptions:%s\n" "$$g" "$$r"; \
	awk -v bl="$$bl" -v r="$$r" '/^[A-Z][A-Z0-9_]*[[:space:]]*\?=.*##/ { key=$$1; line=$$0; sub(/^[^?]*\?=[ \t]*/, "", line); n++; split(line, p, /##/); val=p[1]; gsub(/^[ \t]+|[ \t]+$$/, "", val); entry[n]=key "=" val; desc[n]=p[2]; gsub(/^[ \t]+|[ \t]+$$/, "", desc[n]); width=(length(entry[n])>width?length(entry[n]):width) } END { for (i=1;i<=n;i++) printf "  %s%-*s%s %s\n", bl, width, entry[i], r, desc[i] }' $(MAKEFILE_LIST)

# ─── CONFIG / VARIABLES ───────────────────────────────────
COMPOSE_FILE ?= compose.local.yml ## Local development compose file (hot reload)
COMPOSE_PROD_FILE ?= compose.production.yml ## Production compose file (separate from development)
CHARSOOQ_SECRETS_DIR ?= /etc/charsooq/secrets ## Host directory of production secret files (never committed)
CHARSOOQ_TLS_DIR ?= /etc/charsooq/tls ## Host directory of organization TLS material (never committed)
PROD_ENV_FILE ?= /etc/charsooq/production.env
SSH_HOST ?= ## Optional server alias; when set, prod-deploy and prod-logs run over SSH instead of locally
VERSION ?= latest## Release to deploy; "latest" means the newest published GitHub Release
DB_PORT ?= 5433 ## Host port of the dev postgres db-wait/dev-api expect
YES ?= 0 ## Set YES=1 to skip the confirmation prompt for db-sync-dev-to-staging

# Shared command prefixes: shorter recipes, identical semantics.
UV_RUN := uv run --no-sync --project backend/api
PY_SCRIPT := $(UV_RUN) python backend/api/scripts/
STAGING_ENV_FILE := $(CURDIR)/backend/api/.env.staging
UV_STAGING_PY := $(UV_RUN) --env-file $(STAGING_ENV_FILE) python backend/api/scripts/
# Keep ruff's cache under backend/api even when ruff is invoked from the repo root.
RUFF := RUFF_CACHE_DIR=$(CURDIR)/backend/api/.ruff_cache $(UV_RUN) ruff
UVICORN := $(UV_RUN) uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload
COMPOSE := docker compose -f $(COMPOSE_FILE)
COMPOSE_PROD := docker compose -f $(COMPOSE_PROD_FILE)

# ─── INSTALL / SETUP ──────────────────────────────────────
install: ## @user Install frontend and backend dependencies and git hooks
	pnpm install --frozen-lockfile
	uv sync --locked
	pnpm exec lefthook install

# Caches are always regenerable and gitignored: removing them never loses source.
clean-cache: ## Remove regenerable tool caches (turbo, ruff, pytest, __pycache__)
	rm -rf .turbo apps/web/.turbo .ruff_cache backend/api/.ruff_cache .pytest_cache backend/api/.pytest_cache
	find backend deploy -type d -name __pycache__ -prune -exec rm -rf {} +

clean-build: ## Remove build output and test artifacts (.next, playwright)
	rm -rf apps/web/.next apps/web/test-results apps/web/playwright-report

clean: clean-cache clean-build ## @user Remove regenerable caches and build output

# ─── DEV / RUN ────────────────────────────────────────────
dev-web: ## @user Start frontend dev server (turbo)
	pnpm dev

dev-api: db-wait ## @user Start backend API with reload (waits for postgres first)
	# --no-sync: reuse the installed venv offline (`make install` re-syncs).
	$(UVICORN)

dev-all: db-migrate ## @user Start backend + frontend together (stops both if either exits)
	@uv run --no-sync --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000 --reload & \
	api=$$!; \
	pnpm dev & \
	web=$$!; \
	trap 'kill $$api $$web 2>/dev/null' INT TERM EXIT; \
	while kill -0 $$api 2>/dev/null && kill -0 $$web 2>/dev/null; do sleep 1; done; \
	echo "dev-all: one server exited - stopping the other"

# ─── DATABASE: DEV ────────────────────────────────────────
db-up: ## @user Start dev postgres (own container, port 5433)
	$(COMPOSE)up -d postgres

db-down: ## @user Stop dev postgres (data volume kept)
	$(COMPOSE)stop postgres

db-wait: ## Wait up to 20s for dev postgres to accept connections (no DB needed otherwise)
	@for i in $$(seq 1 20); do \
		python3 -c "import socket; s = socket.create_connection(('127.0.0.1', $(DB_PORT)), timeout=2); s.close()" 2>/dev/null \
		&& { echo "postgres: accepting connections on 127.0.0.1:$(DB_PORT)"; exit 0; } \
		|| sleep 1; \
	done; \
	echo "postgres is not reachable on 127.0.0.1:$(DB_PORT) - run make db-up" >&2; exit 1

db-migrate: db-up ## @user Apply Alembic migrations to dev database (single advisory-locked runner)
	DEPLOYMENT_ENV=development $(PY_SCRIPT)migrate.py

db-bootstrap-owner: db-migrate ## Ensure the env-managed owner via the explicit CLI (no create_all)
	DEPLOYMENT_ENV=development $(PY_SCRIPT)bootstrap_owner.py

db-seed: db-migrate ## @user Ensure the env-managed owner (OWNER_USERNAME, OWNER_PASSWORD)
	DEPLOYMENT_ENV=development $(PY_SCRIPT)seed_admin.py

db-seed-parsina: db-migrate ## Upsert data/parsina.csv into dev DB (keeps product ids + links)
	DEPLOYMENT_ENV=development $(PY_SCRIPT)seed_parsina_products.py

db-seed-demo: db-seed-parsina ## Fill dev demo competitor prices, daily changes, weights and price bounds
	DEPLOYMENT_ENV=development $(PY_SCRIPT)seed_demo_competitors.py

db-clear-products: db-migrate ## Delete all products + competitor listings from dev DB (dev only)
	DEPLOYMENT_ENV=development $(PY_SCRIPT)clear_products.py

# ─── DATABASE: STAGING ────────────────────────────────────
db-sync-dev-to-staging: ## Upsert dev data into staging Neon, then fill demo competitor prices (reads backend/api/.env.staging)
	@test -f $(STAGING_ENV_FILE) || { echo "backend/api/.env.staging is required" >&2; exit 1; }
	DEPLOYMENT_ENV=staging $(UV_STAGING_PY)sync_dev_to_prod.py $(if $(filter 1,$(YES)),--yes,)
	DEPLOYMENT_ENV=staging $(UV_STAGING_PY)seed_demo_competitors.py --staging

db-seed-demo-staging: ## Fill staging Neon with demo competitor prices (reads backend/api/.env.staging)
	@test -f $(STAGING_ENV_FILE) || { echo "backend/api/.env.staging is required" >&2; exit 1; }
	DEPLOYMENT_ENV=staging $(UV_STAGING_PY)seed_demo_competitors.py --staging

# ─── ALIASES (STAGING SYNC) ───────────────────────────────
sync-dev-to-staging sync-staging dev-to-staging: db-sync-dev-to-staging ## Alias for db-sync-dev-to-staging

# ─── DATABASE: VALIDATE (NO DB NEEDED) ───────────────────
db-validate: ## Validate migrations offline: single head + SQL renders cleanly
	cd backend/api && uv run --no-sync alembic heads
	cd backend/api && uv run --no-sync alembic upgrade head --sql > /dev/null
	@echo "migrations validate: single head, offline SQL OK"

# ─── DOCTOR ───────────────────────────────────────────────
doctor: ## @user Check toolchain, env files, and service reachability
	@node --version && pnpm --version
	@python3 --version && uv --version
	@docker info > /dev/null 2>&1 && echo "docker: ok" || echo "docker: NOT RUNNING"
	@test -f backend/api/.env.local || echo "missing backend/api/.env.local (copy from .env.example)"
	@test -f apps/web/.env.local || echo "missing apps/web/.env.local (copy from .env.example)"
	@cd backend/api && uv run --no-sync alembic heads
	@$(COMPOSE) ps postgres 2>/dev/null | grep -q healthy && echo "postgres: healthy" || echo "postgres: not healthy (run make db-up)"

# ─── DOCKER ───────────────────────────────────────────────
docker-build: ## Build local images once (source edits hot-reload afterwards)
	$(COMPOSE)build

docker-up: ## Start hot-reloading local stack (one-shot migration auto-removed)
	$(COMPOSE)run --rm migrate
	$(COMPOSE)up -d --no-build

docker-down: ## Stop Docker Compose services
	$(COMPOSE)down

docker-logs: ## Follow Docker Compose logs
	$(COMPOSE)logs -f

# ─── LOCAL COMPOSE SHORTCUTS ──────────────────────────────
# User-facing names for the compose.local.yml stack. Behavior stays in
# docker-up/docker-down so there is only one place that invokes Compose.
local-up: docker-up ## @user Start local compose stack (postgres + api + web)
local-down: docker-down ## @user Stop local compose stack (data kept)

# ─── DOCKER: PRODUCTION (single slot) ─────────────────────
# Structural validation does not read secret files, so it works on a machine
# without production secrets. Only the run targets need the real files.
#
# Production deployment values have no defaults on purpose (a wrong bind address
# or trusted proxy must not be guessable), so structure validation supplies
# RFC 5737 documentation addresses. They prove the file is well formed; they are
# not a Production configuration. Set the real values in the deployment
# environment before any run target.
#
# The two image references are required as well, with a documentation-only
# digest: an unset image reference must fail the stack instead of running a
# stale local build. See AGENTS.md section 3.
PROD_DEPLOYMENT_ENV = \
	CHARSOOQ_PROXY_BIND_IP=192.0.2.10 \
	CHARSOOQ_SITE_HOST=charsooq.example.test \
	CHARSOOQ_EDGE_SUBNET=192.0.2.0/28 \
	CHARSOOQ_WEB_EDGE_IP=192.0.2.11 \
	CHARSOOQ_PUBLIC_SCHEME=http \
	CHARSOOQ_PUBLIC_PORT=80

PROD_IMAGE_ENV = \
	CHAHARSOQ_API_IMAGE=ghcr.io/example/chaharsooq-api@sha256:0000000000000000000000000000000000000000000000000000000000000000 \
	CHARSOOQ_WEB_IMAGE=ghcr.io/example/charsooq-web@sha256:0000000000000000000000000000000000000000000000000000000000000000

PROD_STRUCTURAL_ENV = $(PROD_DEPLOYMENT_ENV) $(PROD_IMAGE_ENV)

# Local build identity. Every value is derived from the checkout, so a local
# build carries the same OCI metadata a published image carries and the same
# commit always names the same image tag.
PROD_BUILD_REVISION ?= $(shell git rev-parse HEAD 2>/dev/null)
PROD_BUILD_TAG ?= $(shell git rev-parse --short=12 HEAD 2>/dev/null)
PROD_BUILD_DATE ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
PROD_BUILD_VERSION ?= $(PROD_BUILD_TAG)
PROD_BUILD_SOURCE ?= $(shell git config --get remote.origin.url 2>/dev/null | sed -e 's|\.git$$||' -e 's|^git@github.com:|https://github.com/|')
PROD_BUILD_ENV = \
	CHAHARSOQ_API_IMAGE=chaharsooq-api:$(PROD_BUILD_TAG) \
	CHARSOOQ_WEB_IMAGE=charsooq-web:$(PROD_BUILD_TAG) \
	CHARSOOQ_BUILD_REVISION=$(PROD_BUILD_REVISION) \
	CHARSOOQ_BUILD_DATE=$(PROD_BUILD_DATE) \
	CHARSOOQ_BUILD_VERSION=$(PROD_BUILD_VERSION) \
	CHARSOOQ_BUILD_SOURCE=$(PROD_BUILD_SOURCE)

prod-config: ## Validate the production compose file (no secrets needed)
	$(PROD_STRUCTURAL_ENV) $(COMPOSE_PROD) config --quiet
	@echo "production compose structure valid (documentation values only)"

# Offline certificate validation. Reads local files only: no network, no key
# material printed, no issuance. Supply the host that must appear in the leaf
# SAN and, to verify the chain to the organization root, CA_FILE.
tls-validate: ## Validate a certificate/key pair offline (CERT= KEY= HOST= [CA_FILE=] [MIN_DAYS=])
	@test -n "$(CERT)" && test -n "$(KEY)" && test -n "$(HOST)" || { \
		echo "usage: make tls-validate CERT=<fullchain.pem> KEY=<privkey.pem> HOST=<name-or-ip> [CA_FILE=<root.crt>] [MIN_DAYS=30]"; \
		exit 2; \
	}
	python3 deploy/tls/validate_certificate.py --cert "$(CERT)" --key "$(KEY)" --host "$(HOST)" \
		$(if $(CA_FILE),--ca-file "$(CA_FILE)") $(if $(MIN_DAYS),--min-remaining-days "$(MIN_DAYS)")

# Stages the pair under versions/<stamp>, validates it, then switches the single
# `current` symlink atomically. Run with sudo; restart caddy afterwards.
tls-activate: ## Validate and atomically activate a certificate pair (CERT= KEY= HOST= [STAMP=] [CA_FILE=])
	@test -n "$(CERT)" && test -n "$(KEY)" && test -n "$(HOST)" || { \
		echo "usage: make tls-activate CERT=<fullchain.pem> KEY=<privkey.pem> HOST=<name-or-ip> [STAMP=<version>] [CA_FILE=<root.crt>] [MIN_DAYS=30] [CHARSOOQ_TLS_DIR=/etc/charsooq/tls]"; \
		exit 2; \
	}
	@set --; \
	if [ -n "$(STAMP)" ]; then set -- "$$@" --stamp "$(STAMP)"; fi; \
	if [ -n "$(CA_FILE)" ]; then set -- "$$@" --ca-file "$(CA_FILE)"; fi; \
	if [ -n "$(MIN_DAYS)" ]; then set -- "$$@" --min-remaining-days "$(MIN_DAYS)"; fi; \
	python3 deploy/tls/activate_certificate.py \
		--tls-dir "$(strip $(CHARSOOQ_TLS_DIR))" \
		--cert "$(CERT)" --key "$(KEY)" --host "$(HOST)" "$$@"

tls-rollback: ## Atomically point current back to a kept version (STAMP= HOST= [CA_FILE=])
	@test -n "$(STAMP)" && test -n "$(HOST)" || { \
		echo "usage: make tls-rollback STAMP=<version> HOST=<name-or-ip> [CA_FILE=<root.crt>] [CHARSOOQ_TLS_DIR=/etc/charsooq/tls]"; \
		exit 2; \
	}
	@set --; \
	if [ -n "$(CA_FILE)" ]; then set -- "$$@" --ca-file "$(CA_FILE)"; fi; \
	python3 deploy/tls/activate_certificate.py \
		--tls-dir "$(strip $(CHARSOOQ_TLS_DIR))" \
		--rollback-to "$(STAMP)" --host "$(HOST)" "$$@"

# Runs the pinned image's own binary against the committed config, with the
# deployment environment's site host, TLS mode, and certificate mount. Pass
# CERT_FILE/KEY_FILE as container paths to validate a staged pair before it
# replaces the live one (compose does not forward these variables by default;
# an empty value would leave the tls directive with too few arguments).
prod-caddy-validate: ## Validate the Caddyfile in the pinned Caddy image (needs real TLS material)
	@if { [ -n "$(CERT_FILE)" ] && [ -z "$(KEY_FILE)" ]; } || { [ -z "$(CERT_FILE)" ] && [ -n "$(KEY_FILE)" ]; }; then \
		echo "CERT_FILE and KEY_FILE must be provided together"; \
		exit 2; \
	fi
	@flags=""; \
	if [ -n "$(CERT_FILE)" ]; then \
		flags="-e CHARSOOQ_TLS_CERT_FILE=$(CERT_FILE) -e CHARSOOQ_TLS_KEY_FILE=$(KEY_FILE)"; \
	fi; \
	$(COMPOSE_PROD) run --rm --no-deps $$flags caddy \
		caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

prod-build: ## Build production API and web images from this commit (host-build fallback)
	# The deployment values are documentation placeholders: Compose interpolates
	# the whole file before building, and none of them affect the image bytes.
	$(PROD_DEPLOYMENT_ENV) $(PROD_BUILD_ENV) $(COMPOSE_PROD) build
	@echo "built chaharsooq-api:$(PROD_BUILD_TAG) and charsooq-web:$(PROD_BUILD_TAG) from $(PROD_BUILD_REVISION)"

# One command to deploy on the server. Set SSH_HOST to run remotely; otherwise
# run it directly on the host. VERSION defaults to the newest published release.
prod-deploy: ## @user Deploy the newest GitHub Release on the server [VERSION=…] [SSH_HOST=…]
ifeq ($(strip $(SSH_HOST)),)
	./deploy/scripts/deploy.sh "$(VERSION)"
else
	ssh $(SSH_HOST) 'cd /opt/charsooq && ./deploy/scripts/deploy.sh "$(VERSION)"'
endif

prod-pull: ## Pull the released API and web images (needs image refs)
	$(COMPOSE_PROD) pull api web

prod-image-revision: ## Print the release commit recorded in the image references (needs the image variables)
	@test -n "$(CHAHARSOQ_API_IMAGE)" && test -n "$(CHARSOOQ_WEB_IMAGE)" || { \
		echo "usage: CHAHARSOQ_API_IMAGE=<ref> CHARSOOQ_WEB_IMAGE=<ref> make prod-image-revision"; \
		exit 2; \
	}
	docker image inspect "$(CHAHARSOQ_API_IMAGE)" --format 'api revision {{index .Config.Labels "org.opencontainers.image.revision"}}'
	docker image inspect "$(CHARSOOQ_WEB_IMAGE)" --format 'web revision {{index .Config.Labels "org.opencontainers.image.revision"}}'

prod-provision: ## Run idempotent database role provisioning once (needs real secrets)
	$(COMPOSE_PROD) run --rm provision

prod-migrate: ## Run the production migration runner once (needs real secrets)
	$(COMPOSE_PROD) run --rm migrate

prod-bootstrap-owner: ## Run the explicit production owner bootstrap once (needs real secrets)
	$(COMPOSE_PROD) run --rm api python backend/api/scripts/bootstrap_owner.py

prod-up: ## Start production services from released images (needs real secrets)
	$(COMPOSE_PROD) up -d --no-build

prod-ps: ## Show production service status
	$(COMPOSE_PROD) ps

# Compose needs the same deployment values the deploy script sources before
# running, so read the host env file in both the local and SSH variants.
prod-logs: ## @user Follow production logs [SSH_HOST=...]
ifeq ($(strip $(SSH_HOST)),)
	@test -f "$(PROD_ENV_FILE)" || { echo "missing $(PROD_ENV_FILE)" >&2; exit 1; }; \
		set -a && . "$(PROD_ENV_FILE)" && set +a && $(COMPOSE_PROD) logs -f
else
	ssh $(SSH_HOST) 'cd /opt/charsooq && test -f "$(PROD_ENV_FILE)" && set -a && . "$(PROD_ENV_FILE)" && set +a && docker compose -f "$(strip $(COMPOSE_PROD_FILE))" logs -f'
endif

prod-down: ## Stop production services (keeps volumes and data)
	$(COMPOSE_PROD) down

# ─── DEPLOY ───────────────────────────────────────────────
deploy-api: ## Deploy backend API to FastAPI Cloud (run from backend/api)
	cd backend/api && uvx --with 'fastapi[standard]' fastapi deploy

# ─── QUALITY / CHECKS ─────────────────────────────────────
format: ## @user Format frontend and backend source files in place
	pnpm exec prettier --write .
	$(RUFF) format .

lint: ## @user Run frontend lint and backend ruff checks
	pnpm lint
	pnpm format:check
	$(RUFF) check .
	$(RUFF) format --check .

typecheck: ## Run frontend typecheck and backend pyright
	pnpm typecheck
	$(UV_RUN) pyright

test: ## @user Run frontend and backend tests
	pnpm test
	# Run from backend/api so pytest reads its pyproject (testpaths, coverage gate).
	cd backend/api && uv run --no-sync pytest -q

test-e2e: build ## Run Playwright e2e against the production build
	pnpm --filter web test:e2e

openapi-check: ## Fail if backend/api/openapi.json is stale (read-only, no DB needed)
	$(UV_RUN) python backend/api/scripts/check_openapi_fresh.py

build: ## Build web app for production
	pnpm --filter web build

check: lint typecheck test db-validate openapi-check ## @user Run lint + typecheck + test + offline migration and OpenAPI validation