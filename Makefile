.PHONY: check runtime-check db-up db-migrate api fixture test lint format typecheck contracts
check:
	python3 scripts/validate_foundation.py
runtime-check: check lint typecheck contracts test
lint:
	uv run ruff check .
	uv run ruff format --check .
format:
	uv run ruff check --fix .
	uv run ruff format .
typecheck:
	uv run mypy
contracts:
	pnpm check:contracts
test:
	uv run pytest
db-up:
	docker compose -f infra/compose.yaml up -d --wait
	docker compose -f infra/compose.yaml exec -T postgres psql -U arbit_local -d postgres -v ON_ERROR_STOP=1 < infra/init_databases.sql

db-migrate:
	uv run alembic upgrade head

api:
	uv run uvicorn arbit_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log

fixture:
	uv run arbit-worker fixture tests/fixtures/league-snapshot.example.json

.PHONY: local-env local-db-migrate local-sync local-sync-watch local-api local-sync-status
local-env:
	python3 scripts/local_environment.py
local-db-migrate: local-env
	uv run --env-file .env.local alembic upgrade head
local-sync: local-env
	uv run --env-file .env.local arbit-worker sync --once
local-sync-watch: local-env
	uv run --env-file .env.local arbit-worker sync --watch
local-sync-status: local-env
	uv run --env-file .env.local arbit-worker sync-status
local-api: local-env
	uv run --env-file .env.local uvicorn arbit_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers

.PHONY: local-nflverse-catalog local-nflverse-verify
local-nflverse-catalog: local-env
	uv run --env-file .env.local arbit-worker nflverse-catalog --live
local-nflverse-verify: local-env
	uv run --env-file .env.local arbit-worker nflverse-verify --all

.PHONY: web-check web-build member-api
web-check:
	pnpm check:client
	pnpm check:design
	pnpm check:web
	pnpm test:pwa
web-build:
	pnpm --filter @arbit/web build
member-api: local-env
	uv run --env-file .env.local --env-file .env.auth.local uvicorn arbit_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log --timeout-graceful-shutdown 5

.PHONY: local-worker services-install services-status services-remove
local-worker: local-env
	uv run --env-file .env.local arbit-worker run
services-install:
	sh infra/systemd/install.sh
services-status:
	systemctl --user status arbit-worker.service arbit-api.service --no-pager
services-remove:
	sh infra/systemd/install.sh --remove
