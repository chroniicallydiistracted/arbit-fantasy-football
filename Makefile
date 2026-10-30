.PHONY: check runtime-check db-up test lint format typecheck contracts
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
