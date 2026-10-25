SHELL := /bin/bash
.DEFAULT_GOAL := help
UV ?= uv
PNPM ?= pnpm
PY := .venv/bin/python
export PYTHONPATH := apps/server/src

.PHONY: help bootstrap dev up down migrate seed-demo create-user check test e2e test-live build contract contract-check verify
help:
	@echo 'bootstrap dev up down migrate seed-demo create-user check test e2e test-live build contract contract-check verify'
bootstrap:
	$(UV) sync --frozen
	$(PNPM) install --frozen-lockfile
	$(PY) scripts/runtime_check.py

dev:
	$(PY) scripts/dev.py
up:
	docker compose up --build -d
down:
	docker compose down
migrate:
	.venv/bin/alembic -c apps/server/alembic.ini upgrade head
seed-demo:
	$(PY) -m offerpilot.cli seed-demo
create-user:
	$(PY) -m offerpilot.cli create-user --username '$(USERNAME)' $(if $(ADMIN),--admin,)
check:
	.venv/bin/ruff check apps/server/src
	.venv/bin/ruff format --check apps/server/src
	.venv/bin/mypy
	$(PNPM) --dir apps/web check

test:
	.venv/bin/pytest apps/server/tests/unit apps/server/tests/integration apps/server/tests/contract -q --tb=short
	$(PNPM) --dir apps/web test

e2e:
	$(PY) scripts/e2e.py

test-live:
	$(PY) scripts/live.py

build:
	$(PNPM) build
	$(UV) build --wheel --out-dir .local/dist
	$(PY) scripts/validate_deployment.py

contract:
	$(PY) scripts/openapi.py
	$(PNPM) contract
	$(PNPM) --dir apps/web exec prettier --write src/api/schema.d.ts

contract-check:
	$(PY) scripts/contract_check.py

verify: check test e2e build contract-check
