# Developer entry points. `make help` lists targets.
#
# Quick start:   make setup && make dev
#
# Everything here mirrors what CI runs (.github/workflows/ci.yml), so a green
# `make lint test` locally should mean a green CI.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

COMPOSE        ?= docker compose
PROJECT        := doctools
REDOCLY        := npx -y @redocly/cli@2.72.1
PRISM_PORT     ?= 4010

BACKEND_DIR    := backend
FRONTEND_DIR   := frontend
HAS_BACKEND    := $(wildcard $(BACKEND_DIR)/pyproject.toml)
HAS_FRONTEND   := $(wildcard $(FRONTEND_DIR)/package.json)

# Same command as CI and docs/api.md §8. Output is committed.
DATAMODEL_CODEGEN := uv run datamodel-codegen \
	--input ../shared/openapi.yaml --input-file-type openapi \
	--output app/schemas/generated/models.py \
	--output-model-type pydantic_v2.BaseModel --target-python-version 3.12 \
	--use-annotated --field-constraints --use-standard-collections --use-union-operator \
	--use-subclass-enum --use-schema-description --disable-timestamp --reuse-model \
	--strict-nullable --collapse-root-models --formatters ruff-format

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
.PHONY: setup
setup: .env ## Create .env (random local secrets) and install backend/frontend deps
	@command -v docker >/dev/null || { echo "docker is required"; exit 1; }
	@command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
	@command -v npm >/dev/null || { echo "node/npm is required (see .nvmrc)"; exit 1; }
ifneq ($(HAS_BACKEND),)
	cd $(BACKEND_DIR) && uv sync --locked
endif
ifneq ($(HAS_FRONTEND),)
	cd $(FRONTEND_DIR) && npm ci --no-audit --no-fund
endif
	@echo "Setup done. Next: make dev"

# .env is generated once from .env.example. Every __GENERATE__ placeholder gets
# its own random 32-byte hex value; the DB URL picks up the generated password.
# An existing .env is never overwritten.
.env:
	@test -f .env.example || { echo ".env.example is missing"; exit 1; }
	@umask 077; awk ' \
	  { while (index($$0, "__GENERATE__")) { cmd = "openssl rand -hex 32"; cmd | getline r; close(cmd); sub(/__GENERATE__/, r) } } \
	  /^POSTGRES_PASSWORD=/ { split($$0, kv, "="); pg = kv[2] } \
	  /APP_DATABASE__URL=/ && pg != "" { sub(/<password>/, pg) } \
	  { print }' .env.example > .env
	@echo "Created .env (mode 600) with fresh local secrets. Never commit it."

# -----------------------------------------------------------------------------
# Local stack (compose.yaml)
# -----------------------------------------------------------------------------
.PHONY: dev
dev: .env ## Build and start valkey, api, workers, sweeper (detached, waits for health)
	$(COMPOSE) up --build --detach --wait
	@echo ""
	@echo "  API     http://localhost:$${API_PORT:-8000}/health"
	@echo "  Logs    make logs"
	@echo "  Stop    make down"

.PHONY: dev-all
dev-all: .env ## Like dev, plus postgres, Prism mock and the Next.js dev server
	$(COMPOSE) --profile db --profile mock --profile frontend up --build --detach --wait

.PHONY: down
down: ## Stop the stack (keeps postgres data; temp workspace is RAM-only)
	$(COMPOSE) --profile db --profile mock --profile frontend down --remove-orphans

.PHONY: logs
logs: ## Tail logs of all running services (SERVICE=api to filter)
	$(COMPOSE) logs --follow --tail 100 $(SERVICE)

.PHONY: ps
ps: ## Show service status and health
	$(COMPOSE) ps

.PHONY: mock
mock: ## Run the Prism mock of shared/openapi.yaml on :4010
	$(COMPOSE) --profile mock up --detach --wait mock
	@echo "Prism mock: http://localhost:$(PRISM_PORT)  (set NEXT_PUBLIC_API_BASE_URL to it)"

# -----------------------------------------------------------------------------
# Quality
# -----------------------------------------------------------------------------
.PHONY: test
test: ## Run backend (pytest) and frontend (vitest) tests
ifneq ($(HAS_BACKEND),)
	cd $(BACKEND_DIR) && uv run pytest
endif
ifneq ($(HAS_FRONTEND),)
	cd $(FRONTEND_DIR) && npm test
endif

.PHONY: test-e2e
test-e2e: ## Frontend Playwright smoke tests (installs chromium on first run)
	cd $(FRONTEND_DIR) && npx --no-install playwright install chromium && npm run test:e2e

.PHONY: lint
lint: ## ruff, ruff format --check, mypy, eslint, typecheck, redocly, compose config
ifneq ($(HAS_BACKEND),)
	cd $(BACKEND_DIR) && uv run ruff check . && uv run ruff format --check . && uv run mypy app
endif
ifneq ($(HAS_FRONTEND),)
	cd $(FRONTEND_DIR) && npm run lint && npm run typecheck
endif
	$(REDOCLY) lint --config redocly.yaml shared/openapi.yaml
	$(COMPOSE) --profile db --profile mock --profile frontend config --quiet

.PHONY: fmt
fmt: ## Auto-format and auto-fix (ruff; frontend `format` script if present)
ifneq ($(HAS_BACKEND),)
	cd $(BACKEND_DIR) && uv run ruff check --fix . && uv run ruff format .
endif
ifneq ($(HAS_FRONTEND),)
	cd $(FRONTEND_DIR) && npm run --if-present format
endif

.PHONY: codegen
codegen: ## Regenerate contract code (backend models, frontend types) from shared/openapi.yaml
ifneq ($(HAS_BACKEND),)
	cd $(BACKEND_DIR) && $(DATAMODEL_CODEGEN)
endif
ifneq ($(HAS_FRONTEND),)
	cd $(FRONTEND_DIR) && npm run api:types
endif

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
.PHONY: clean
clean: ## Stop the stack and delete the temp workspace volume and local caches
	$(COMPOSE) --profile db --profile mock --profile frontend down --remove-orphans
	-docker volume rm $(PROJECT)_workspaces 2>/dev/null
	rm -rf .data
	find $(BACKEND_DIR) -path $(BACKEND_DIR)/.venv -prune -o -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/htmlcov $(BACKEND_DIR)/.coverage $(FRONTEND_DIR)/coverage

.PHONY: clean-all
clean-all: clean ## clean + delete ALL compose volumes (postgres data, node_modules cache)
	$(COMPOSE) --profile db --profile mock --profile frontend down --volumes --remove-orphans
