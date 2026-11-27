# charsooq — shortcuts for the documented pnpm/uv/compose workflow.
SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: build check install help help-all doctor doctor-prod \
	clean clean-build clean-cache format \
	dev-web dev-api dev-all \
	db-up db-down db-wait db-migrate db-bootstrap-owner db-seed db-seed-parsina db-seed-demo \
	db-clear-products db-validate db-sync-dev-to-staging db-seed-demo-staging \
	sync-dev-to-staging sync-staging dev-to-staging \
	docker-build docker-up docker-down docker-logs deploy-api \
	local-up local-down \
	prod-config prod-build prod-deploy prod-deploy-simulate prod-pull prod-image-revision \
	prod-watch-install prod-watch-status prod-watch-stop \
	prod-provision prod-migrate prod-bootstrap-owner prod-up prod-ps prod-logs \
	prod-down prod-caddy-validate tls-validate tls-activate tls-rollback \
	lint typecheck test test-e2e openapi-check

# ─── OUTPUT COLORS ────────────────────────────────────────
# Shared by help, doctor and deploy output. A pipe or NO_COLOR keeps output plain.
# Same palette as help: bo: bold green, g: green, bl: blue, d: dim, r: reset.
COLOR_INIT = bo=""; g=""; bl=""; d=""; r=""; \
	if [ -z "$${NO_COLOR:-}" ] && [ -t 1 ]; then \
		bo=$$'\033[1m\033[32m'; g=$$'\033[32m'; bl=$$'\033[34m'; d=$$'\033[2m'; r=$$'\033[0m'; \
	fi;

# ─── HELP ─────────────────────────────────────────────────
# `make help` lists only targets whose description starts with @user, without
# the variable block; `make help-all` lists every target and variable. The
# marker lives in the description itself, so there is no separate shortcut
# list to keep in sync.
help help-all: ## Show the short user list (help) or every target (help-all)
	@$(COLOR_INIT) \
	mode=all; [ "$@" = "help" ] && mode=user; \
	printf "%sChaharSooq%s%s — Persian-first admin panel (Next.js + FastAPI)%s\n\n" "$$bo" "$$r" "$$d" "$$r"; \
	printf "Usage:  make %s[VARIABLE=value]%s %s<TARGET>%s\n\n" "$$bl" "$$r" "$$bl" "$$r"; \
	printf "%sCommands:%s\n" "$$g" "$$r"; \
	awk -v g="$$g" -v bl="$$bl" -v r="$$r" -v mode="$$mode" '/^# ─── / { sec=$$0; sub(/^# ─── /, "", sec); sub(/ ─*$$/, "", sec); cur=sec; next } /^[a-z][a-z0-9_.-]*:[^=]*##/ { name=$$1; sub(/:.*/, "", name); desc=$$0; sub(/^[^#]*##[[:space:]]*/, "", desc); user=(desc ~ /^@user[[:space:]]+/); sub(/^@user[[:space:]]+/, "", desc); if (mode == "user" && !user) next; if (mode == "user") cur="USER SHORTCUTS"; if (cur != "" && cur != last) { printf "  %s%s:%s\n", g, cur, r; last=cur } printf "    %s%-22s%s %s\n", bl, name, r, desc }' $(MAKEFILE_LIST); \
	if [ "$$mode" = "user" ]; then printf "\n  Run %smake help-all%s to see every target.\n" "$$bl" "$$r"; \
	else \
		printf "\n%sOptions:%s\n" "$$g" "$$r"; \
		awk -v bl="$$bl" -v r="$$r" '/^[A-Z][A-Z0-9_]*[[:space:]]*\?=.*##/ { key=$$1; line=$$0; sub(/^[^?]*\?=[ \t]*/, "", line); n++; split(line, p, /##/); val=p[1]; gsub(/^[ \t]+|[ \t]+$$/, "", val); entry[n]=key "=" val; desc[n]=p[2]; gsub(/^[ \t]+|[ \t]+$$/, "", desc[n]); width=(length(entry[n])>width?length(entry[n]):width) } END { for (i=1;i<=n;i++) printf "  %s%-*s%s %s\n", bl, width, entry[i], r, desc[i] }' $(MAKEFILE_LIST); \
	fi

# ─── CONFIG / VARIABLES ───────────────────────────────────
COMPOSE_FILE ?= compose.local.yml ## Local development compose file (hot reload)
COMPOSE_PROD_FILE ?= compose.production.yml ## Production compose file (separate from development)
CHARSOOQ_SECRETS_DIR ?= /etc/charsooq/secrets ## Host directory of production secret files (never committed)
CHARSOOQ_TLS_DIR ?= /etc/charsooq/tls ## Host directory of organization TLS material (never committed)
PROD_ENV_FILE ?= /etc/charsooq/production.env
PROD_REMOTE_DIR ?= /opt/charsooq ## Remote checkout directory used by SSH prod-deploy/prod-logs
# Doctor checks the local stack by default. On the Production host either the
# host env file or an explicit identity selects the Production checks; pass
# DOCTOR_ENV=development|production to override the detection.
DOCTOR_ENV ?= $(if $(filter production,$(DEPLOYMENT_ENV)),production,$(if $(wildcard $(strip $(PROD_ENV_FILE))),production,development)) ## Environment checked by make doctor (development|production)
SSH_HOST ?= ## Optional server alias; when set, prod-deploy and prod-logs run over SSH instead of locally
VERSION ?= latest## Release to deploy; "latest" means the newest published GitHub Release
DB_PORT ?= 5433 ## Host port of the dev postgres db-wait/dev-api expect
YES ?= 0 ## Set YES=1 to skip the confirmation prompt for db-sync-dev-to-staging
FULL ?= 0 ## Set FULL=1 to also soft-deactivate staging products absent from dev (mirror)

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

dev-all: db-migrate ## Start backend + frontend together (stops both if either exits)
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

db-seed: db-migrate ## Ensure the env-managed owner (OWNER_USERNAME, OWNER_PASSWORD)
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
	DEPLOYMENT_ENV=staging $(UV_STAGING_PY)sync_dev_to_prod.py $(if $(filter 1,$(YES)),--yes,) $(if $(filter 1,$(FULL)),--mirror,)
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
doctor: ## @user Check the local stack or the Production host (DOCTOR_ENV=development|production)
	@$(COLOR_INIT) \
	mode="$(strip $(DOCTOR_ENV))"; \
	if [ "$$mode" != development ] && [ "$$mode" != production ]; then \
		printf 'unknown DOCTOR_ENV=%s — use development or production\n' "$$mode" >&2; exit 2; \
	fi; \
	if [ "$$mode" = production ]; then \
		printf '%sChaharSooq doctor%s — Production host\n' "$$bo" "$$r"; \
		printf '%sChecks host prerequisites, file-backed config, compose policy and live services.%s\n' "$$d" "$$r"; \
		printf '%sLines marked FIX need action before deploying or operating Production.%s\n\n' "$$d" "$$r"; \
	else \
		printf '%sChaharSooq doctor%s — local development environment\n' "$$bo" "$$r"; \
		printf '%sChecks toolchain versions, local config and dev services.%s\n' "$$d" "$$r"; \
		printf '%sLines marked FIX need action before running the dev stack.%s\n\n' "$$d" "$$r"; \
	fi; \
	issues=0; \
	report() { \
		if [ "$$2" = ok ]; then s="$$g OK $$r"; else s="$$bl FIX $$r"; issues=$$((issues + 1)); fi; \
		printf '  %s %s%-11s%s %s\n' "$$s" "$$bl" "$$1" "$$r" "$$3"; \
	}; \
	if [ "$$mode" = production ]; then \
		printf '%sHOST%s\n' "$$g" "$$r"; \
		for tool in docker curl jq; do \
			if command -v "$$tool" >/dev/null 2>&1; then \
				report "$$tool" ok 'installed on the host'; \
			else \
				report "$$tool" fix 'not found — required by deploy.sh'; \
			fi; \
		done; \
		if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
			report daemon ok 'Docker daemon reachable'; \
		else \
			report daemon fix 'daemon not reachable — start Docker, then make prod-deploy'; \
		fi; \
		printf '\n%sPRODUCTION CONFIG%s\n' "$$g" "$$r"; \
		env_file="$(strip $(PROD_ENV_FILE))"; \
		if [ -f "$$env_file" ]; then \
			missing=""; \
			for key in CHARSOOQ_PROXY_BIND_IP CHARSOOQ_SITE_HOST CHARSOOQ_EDGE_SUBNET CHARSOOQ_WEB_EDGE_IP CHARSOOQ_PUBLIC_SCHEME; do \
				grep -qE "^[[:space:]]*(export[[:space:]]+)?$$key=" "$$env_file" || missing="$$missing $$key"; \
			done; \
			if [ -z "$$missing" ]; then \
				report 'prod env' ok "$$env_file — required keys present (values not printed)"; \
			else \
				report 'prod env' fix "missing keys:$$missing in $$env_file"; \
			fi; \
		else \
			report 'prod env' fix "$$env_file missing — copy deploy/production.env.example and set real values"; \
		fi; \
		secret_dir="$${CHARSOOQ_SECRETS_DIR:-$(strip $(CHARSOOQ_SECRETS_DIR))}"; \
		if [ -d "$$secret_dir" ]; then \
			missing=""; \
			for name in postgres_password database_url migration_database_url session_secret owner_password parsina_password; do \
				[ -e "$$secret_dir/$$name" ] || missing="$$missing $$name"; \
			done; \
			if [ -z "$$missing" ]; then \
				report secrets ok 'six file-backed secrets present — contents not read'; \
			else \
				report secrets fix "missing or inaccessible:$$missing"; \
			fi; \
		else \
			report secrets fix "$$secret_dir missing — file-backed secrets required"; \
		fi; \
		if $(PROD_STRUCTURAL_ENV) $(COMPOSE_PROD) config --quiet >/dev/null 2>&1; then \
			report compose ok 'production compose structure valid (documentation values)'; \
		else \
			report compose fix 'production compose structure invalid — run make prod-config'; \
		fi; \
		policy=$$($(PROD_STRUCTURAL_ENV) $(COMPOSE_PROD) config --format json 2>/dev/null); \
		if printf '%s' "$$policy" | jq -e '.services.db.image == "postgres:19.0-trixie" and .services.caddy.image == "caddy:2.11.9-alpine" and .services.api.environment.DEPLOYMENT_ENV == "production" and .services.api.environment.RUN_MIGRATIONS_ON_STARTUP == "false" and .services.api.environment.RUN_OWNER_BOOTSTRAP_ON_STARTUP == "false" and .networks.backend.internal == true and ([.services | to_entries[] | select(.value.ports != null) | .key] == ["caddy"]) and (all(.services.caddy.ports[]; (.host_ip // "") != "" and . != "0.0.0.0"))' >/dev/null 2>&1; then \
			report policy ok 'PG 19.0 pin, identity, internal DB, no auto-migrate and bound Caddy'; \
		else \
			report policy fix 'compose policy failed — check pins, startup flags and published ports'; \
		fi; \
		printf '\n%sPRODUCTION RUNTIME%s\n' "$$g" "$$r"; \
		ids=$$($(COMPOSE_PROD) ps -q db api web caddy 2>/dev/null); \
		if [ -z "$$ids" ]; then \
			report services fix 'production stack not running — run make prod-deploy'; \
		else \
			bad=""; \
			for id in $$ids; do \
				state=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$$id" 2>/dev/null); \
				case "$$state" in healthy|running) ;; *) bad="$$bad $$id";; esac; \
			done; \
			if [ -z "$$bad" ]; then \
				report services ok 'db, api, web and caddy are running or healthy'; \
			else \
				report services fix "containers not ready:$$bad"; \
			fi; \
			unpinned=""; \
			for svc in api web; do \
				img=$$(docker inspect -f '{{index .Config.Image}}' "$$($(COMPOSE_PROD) ps -q "$$svc" 2>/dev/null)" 2>/dev/null); \
				case "$$img" in *@sha256:*) ;; *) unpinned="$$unpinned $$svc";; esac; \
			done; \
			if [ -z "$$unpinned" ]; then \
				report images ok 'api and web run digest-pinned images'; \
			else \
				report images fix "not digest-pinned:$$unpinned"; \
			fi; \
			if $(COMPOSE_PROD) run --rm --no-deps migrate python backend/api/scripts/migrate.py --check >/dev/null 2>&1; then \
				report migrations ok 'database at head — checked with the migration credential'; \
			else \
				report migrations fix 'migration head check failed — run make prod-deploy'; \
			fi; \
			if [ -f "$$env_file" ]; then \
				set -a; . "$$env_file"; set +a; \
				base="$${CHARSOOQ_PUBLIC_SCHEME:-http}://$${CHARSOOQ_PROXY_BIND_IP}"; \
				port="$${CHARSOOQ_PUBLIC_PORT:-80}"; \
				bad=""; \
				for path in /api/v1/health /api/v1/ready /login; do \
					curl -fsS --max-time 5 -o /dev/null "$$base:$$port$$path" 2>/dev/null || bad="$$bad $$path"; \
				done; \
				if [ -z "$$bad" ]; then \
					report probes ok '/api/v1/health, /api/v1/ready and /login respond'; \
				else \
					report probes fix "failed probes:$$bad"; \
				fi; \
			fi; \
		fi; \
	else \
		printf '%sTOOLCHAIN (pins: .node-version, .python-version, package.json)%s\n' "$$g" "$$r"; \
	node_v=$$(node --version 2>/dev/null || true); \
	node_plain=$${node_v#v}; \
	if [ -n "$$node_v" ] && [ "$$(printf '%s\n' 22 "$$node_plain" | sort -V | head -n 1)" = 22 ]; then \
		report node ok "$$node_v — need 22+ (.node-version)"; \
	else \
		report node fix "$${node_v:-not found} — install Node 22+ (.node-version)"; \
	fi; \
	pnpm_v=$$(pnpm --version 2>/dev/null || true); \
	if [ -n "$$pnpm_v" ]; then \
		report pnpm ok "$$pnpm_v — pinned in package.json (make install)"; \
	else \
		report pnpm fix "not found — run make install (pnpm 11 is pinned in package.json)"; \
	fi; \
	py_v=$$(python3 --version 2>/dev/null || true); \
	py_plain=$${py_v#Python }; \
	if [ -n "$$py_v" ] && [ "$$(printf '%s\n' 3.12 "$$py_plain" | sort -V | head -n 1)" = 3.12 ]; then \
		report python ok "$$py_plain — need 3.12 (.python-version)"; \
	else \
		report python fix "$${py_plain:-not found} — install Python 3.12 (.python-version)"; \
	fi; \
	uv_v=$$(uv --version 2>/dev/null | awk '{print $$2}'); \
	if [ -n "$$uv_v" ]; then \
		report uv ok "$$uv_v — runs backend scripts and migrations"; \
	else \
		report uv fix "not found — install uv (see README)"; \
	fi; \
	printf '\n%sLOCAL CONFIG%s\n' "$$g" "$$r"; \
	if [ -f backend/api/.env.local ]; then \
		report 'API env' ok 'backend/api/.env.local — API settings present'; \
	else \
		report 'API env' fix 'missing — cp backend/api/.env.example backend/api/.env.local'; \
	fi; \
	if [ -f apps/web/.env.local ]; then \
		report 'web env' ok 'apps/web/.env.local — web settings present'; \
	else \
		report 'web env' fix 'missing — cp apps/web/.env.example apps/web/.env.local'; \
	fi; \
	printf '\n%sDEV SERVICES%s\n' "$$g" "$$r"; \
	if docker info >/dev/null 2>&1; then \
		report docker ok 'daemon reachable — compose can start the local stack'; \
	else \
		report docker fix 'daemon not reachable — start Docker Desktop, then make db-up'; \
	fi; \
	pg_id=$$($(COMPOSE) ps -q postgres 2>/dev/null); \
	pg_health=$$([ -n "$$pg_id" ] && docker inspect -f '{{.State.Health.Status}}' "$$pg_id" 2>/dev/null || true); \
	if [ "$$pg_health" = healthy ]; then \
		report postgres ok "healthy on localhost:$(strip $(DB_PORT)) — dev database ready"; \
	else \
		report postgres fix "$${pg_health:-not running} — run make db-up (port $(strip $(DB_PORT)))"; \
	fi; \
	printf '\n%sMIGRATIONS%s\n' "$$g" "$$r"; \
	if heads=$$(cd backend/api && uv run --no-sync alembic heads 2>&1); then \
		report alembic ok "$$heads — apply pending migrations with make db-migrate"; \
	else \
		report alembic fix 'cannot read heads — run make install, then make db-migrate'; \
		fi; \
	fi; \
	printf '\n'; \
	if [ "$$issues" -eq 0 ]; then \
		if [ "$$mode" = production ]; then \
			printf '%sAll checks passed — the Production host is ready.%s\n' "$$g" "$$r"; \
		else \
			printf '%sAll checks passed — the local development setup is ready.%s\n' "$$g" "$$r"; \
		fi; \
	else \
		printf '%s%d item(s) need attention — re-run make doctor after fixing them.%s\n' "$$bl" "$$issues" "$$r"; \
	fi

doctor-prod: DOCTOR_ENV := production
doctor-prod: doctor ## @user Run doctor against the Production host (run on the server)

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
	CHAHARSOQ_WEB_IMAGE=ghcr.io/example/chaharsooq-web@sha256:0000000000000000000000000000000000000000000000000000000000000000

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
	CHAHARSOQ_WEB_IMAGE=chaharsooq-web:$(PROD_BUILD_TAG) \
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
	@echo "built chaharsooq-api:$(PROD_BUILD_TAG) and chaharsooq-web:$(PROD_BUILD_TAG) from $(PROD_BUILD_REVISION)"

# One command to deploy on the server. Set SSH_HOST to run remotely; otherwise
# run it directly on the host. VERSION defaults to the newest published release.
ifeq ($(strip $(SSH_HOST)),)
PROD_DEPLOY_CMD = ./deploy/scripts/deploy.sh "$(VERSION)"
else
PROD_DEPLOY_CMD = ssh $(SSH_HOST) 'cd $(strip $(PROD_REMOTE_DIR)) && ./deploy/scripts/deploy.sh "$(VERSION)"'
endif

# Stream the deploy transcript through the shared palette. pipefail keeps the
# deploy script's exit status; NO_COLOR or a pipe leaves the output untouched.
define COLORIZE_DEPLOY
awk -v d="$$d" -v g="$$g" -v bl="$$bl" -v bo="$$bo" -v r="$$r" '\
{ \
	if (index($$0, "[deploy] [") == 1) { \
		s = substr($$0, 10); e = index(s, "] "); \
		printf "%s[deploy]%s %s%s%s %s%s%s\n", d, r, g, substr(s, 1, e), r, bl, substr(s, e + 2), r \
	} else if (index($$0, "[deploy]     ") == 1) { \
		printf "%s%s%s\n", d, $$0, r \
	} else if (index($$0, "[deploy] ──") == 1 || index($$0, "[deploy] ERROR") == 1) { \
		printf "%s%s%s\n", bo, $$0, r \
	} else if (index($$0, "[deploy]   ") == 1) { \
		s = substr($$0, 12); e = index(s, "  "); \
		if (e > 0) printf "%s[deploy]%s   %s%s%s%s\n", d, r, bl, substr(s, 1, e - 1), r, substr(s, e); \
		else print $$0 \
	} else if (index($$0, "[deploy] ") == 1) { \
		printf "%s[deploy]%s %s\n", g, r, substr($$0, 10) \
	} else print $$0 \
}'
endef

prod-deploy: ## @user Deploy the newest GitHub Release on the server [VERSION=…] [SSH_HOST=…]
	@$(COLOR_INIT) \
	set -o pipefail; \
	$(PROD_DEPLOY_CMD) 2>&1 | $(COLORIZE_DEPLOY)

# Install/start/stop the outbound-only release-polling agent on the host (ADR 033).
# The timer calls deploy.sh; it never runs a CI workflow on the host.
prod-watch-install: ## @user Install and enable the 5-minute auto-deploy timer on the server
	@sed 's|/opt/charsooq|$(CURDIR)|g' deploy/systemd/charsooq-release-watch.service > /tmp/charsooq-release-watch.service
	@cp deploy/systemd/charsooq-release-watch.timer /tmp/charsooq-release-watch.timer
	sudo install -m 0644 /tmp/charsooq-release-watch.service /etc/systemd/system/
	sudo install -m 0644 /tmp/charsooq-release-watch.timer /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable --now charsooq-release-watch.timer
	@echo "auto-deploy timer enabled from $(CURDIR); check: make prod-watch-status"

prod-watch-status: ## @user Show auto-deploy timer status and recent agent log
	sudo systemctl status charsooq-release-watch.timer --no-pager || true
	sudo journalctl -u charsooq-release-watch.service -n 30 --no-pager

prod-watch-stop: ## @user Disable the auto-deploy timer (keeps manual prod-deploy working)
	sudo systemctl disable --now charsooq-release-watch.timer
	@echo "auto-deploy timer disabled; manual make prod-deploy still works"

# Local preview of the deploy transcript. Step names mirror deploy.sh; every
# value below is invented, and this recipe runs no deploy, Docker or SSH command.
prod-deploy-simulate: ## @user Preview prod-deploy output locally (SIMULATION, no server changes)
	@$(COLOR_INIT) \
	printf '%s[deploy] ── SIMULATION ─────────────────────────────────────────%s\n' "$$bo" "$$r"; \
	printf '%s[deploy] Fake preview of make prod-deploy; no server, images or database are touched.%s\n' "$$d" "$$r"; \
	step() { printf '\n%s[deploy]%s %s[%d/10]%s %s%s%s\n' "$$d" "$$r" "$$g" "$$1" "$$r" "$$bl" "$$2" "$$r"; }; \
	note() { printf '%s[deploy]     %s%s\n' "$$d" "$$1" "$$r"; }; \
	field() { printf '%s[deploy]%s   %s%-11s%s %s\n' "$$d" "$$r" "$$bl" "$$1" "$$r" "$$2"; }; \
	step 1 'Validating host configuration'; \
	note 'host configuration, secret directory and command dependencies are valid (simulated)'; \
	step 2 'Checking database cluster version'; \
	note 'cluster and image agree on PostgreSQL major 19 (simulated)'; \
	step 3 'Resolving the release to immutable image digests'; \
	note 'fetching the newest published release of example/charsooq'; \
	note 'api image   ghcr.io/example/chaharsooq-api@sha256:1111111111111111111111111111111111111111111111111111111111111111'; \
	note 'web image   ghcr.io/example/chaharsooq-web@sha256:2222222222222222222222222222222222222222222222222222222222222222'; \
	step 4 'Verifying that both images are from one release'; \
	note 'version 1.2.3, commit a1b2c3d4e5f60718293a4b5c6d7e8f9012345678'; \
	step 5 'Validating the production Compose file'; \
	step 6 'Pulling the released images'; \
	note 'api and web pulled by immutable digest (simulated)'; \
	step 7 'Provisioning database roles'; \
	note 'database roles already provisioned (simulated)'; \
	step 8 'Checking database migrations'; \
	note 'migrate: database already at head'; \
	printf '%s[deploy]     (skip) database already at head%s\n' "$$d" "$$r"; \
	step 9 'Starting api and web'; \
	note 'replaced v1.2.2 with v1.2.3 and reloaded Caddy (simulated)'; \
	step 10 'Verifying service and endpoint health'; \
	note 'all services healthy on attempt 1/30 (simulated)'; \
	printf '\n%s[deploy] ── Deployment summary ──────────────────────────────────%s\n' "$$bo" "$$r"; \
	field 'Status' 'deployed (simulated)'; \
	field 'Release' 'v1.2.3 (a1b2c3d4e5f60718293a4b5c6d7e8f9012345678)'; \
	field 'Host' 'https://charsooq.example.test'; \
	field 'Database' 'already at head'; \
	field 'Services' 'db=healthy api=healthy web=healthy caddy=running'; \
	field 'Probes' '/api/v1/health ok  /api/v1/ready ok  /login ok'; \
	field 'Duration' '42s'; \
	field 'Rollback' './deploy/scripts/deploy.sh v1.2.2'; \
	printf '\n%s[deploy] All services are up and every health probe passed on charsooq.example.test.%s\n' "$$g" "$$r"; \
	printf '%s[deploy] deployment complete (1.2.3)%s\n' "$$g" "$$r"; \
	printf '%s[deploy] ── SIMULATION COMPLETE — nothing was deployed ──────────%s\n' "$$bl" "$$r"

prod-pull: ## Pull the released API and web images (needs image refs)
	$(COMPOSE_PROD) pull api web

prod-image-revision: ## Print the release commit recorded in the image references (needs the image variables)
	@test -n "$(CHAHARSOQ_API_IMAGE)" && test -n "$(CHAHARSOQ_WEB_IMAGE)" || { \
		echo "usage: CHAHARSOQ_API_IMAGE=<ref> CHAHARSOQ_WEB_IMAGE=<ref> make prod-image-revision"; \
		exit 2; \
	}
	docker image inspect "$(CHAHARSOQ_API_IMAGE)" --format 'api revision {{index .Config.Labels "org.opencontainers.image.revision"}}'
	docker image inspect "$(CHAHARSOQ_WEB_IMAGE)" --format 'web revision {{index .Config.Labels "org.opencontainers.image.revision"}}'

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
	ssh $(SSH_HOST) 'cd $(strip $(PROD_REMOTE_DIR)) && test -f "$(PROD_ENV_FILE)" && set -a && . "$(PROD_ENV_FILE)" && set +a && docker compose -f "$(strip $(COMPOSE_PROD_FILE))" logs -f'
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