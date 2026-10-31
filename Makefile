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
	uv run uvicorn arbit_api.main:create_app --factory --host 127.0.0.1 --port 8000

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
	uv run --env-file .env.local uvicorn arbit_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers

.PHONY: local-nflverse-catalog local-nflverse-verify
local-nflverse-catalog: local-env
	uv run --env-file .env.local arbit-worker nflverse-catalog --live
local-nflverse-verify: local-env
	uv run --env-file .env.local arbit-worker nflverse-verify --all
