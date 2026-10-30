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
