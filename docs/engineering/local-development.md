# Local Development — M1a

The runtime/core/snapshot foundation is implemented. There is no frontend UI, member authentication, live FFA ingestion or projection model yet. All fixture data is explicitly synthetic and may only publish to a database ending in `_fixture` or `_test`.

## Pinned tools

Python **3.12.13**, Node **24.22.2**, pnpm **12.16.1**, uv **0.11.33**. Python and JS transitive versions are frozen in `uv.lock` and `pnpm-lock.yaml`. PostgreSQL 18 uses the immutable digest in `infra/compose.yaml`; no floating database image is used. Resolved Python API dependencies include FastAPI 0.162.0, Pydantic 2.14.2, SQLAlchemy 2.1.6, psycopg 3.3.6 and Alembic 1.20.1. The Starlette test client uses HTTPX2, as required by its current integration; deprecated HTTPX behavior is not suppressed.

## Install and test

From the repository root with Docker available:

```sh
uv sync --frozen
pnpm install --frozen-lockfile
make db-up
make runtime-check
```

`db-up` starts only the dedicated `arbit-dev` PostgreSQL service on **127.0.0.1:55439**, preserving its named volume, and idempotently creates `arbit_test` and `arbit_fixture`. The published local credentials are for this local container only and must not be used for any deployed service. Integration tests default to `arbit_test`; override `ARBIT_TEST_DATABASE_URL` for an isolated test host. Names must end in `_test`. Each test creates and removes its own random schema; it never drops public tables or the database. Database tests are not silently skipped when the service is unavailable.

`make runtime-check` runs foundation validation, Ruff lint/format checks, strict mypy, full Draft 2020-12 AJV contract validation, and the entire pytest suite. `make check` still provides the standard-library-only documentation check. `make format` is the explicit formatter; checks do not rewrite files. CI provisions a dedicated PostgreSQL service and executes the same frozen installs and runtime checks; no private ESPN access is needed.

If a host's global Corepack points into an incompatible Windows cache, use the pinned tools without modifying global installation:

```sh
npm exec --yes --package=node@24.22.2 --package=pnpm@12.16.1 -- pnpm install --frozen-lockfile
npm exec --yes --package=node@24.22.2 --package=pnpm@12.16.1 -- make runtime-check
```

## Synthetic end-to-end smoke path

```sh
export ARBIT_DATABASE_URL='postgresql+psycopg://arbit_local:arbit-local-dev-only@127.0.0.1:55439/arbit_fixture'
make db-migrate
make fixture
make api
```

The fixture command prints only the synthetic label and snapshot/hash references. Running the same file again reuses the snapshot and outbox event. The file is not real FFA scoring or roster data. API binds to **127.0.0.1:8000**; `/health/live` reports process liveness, `/health/ready` checks database and schema revision. Missing database/migrations returns safe 503 readiness and does not disclose credentials. There are no public league-data or interactive documentation routes. Production startup is deliberately unavailable until member authentication exists.

Stop the API with Ctrl+C; stop local PostgreSQL with `docker compose -f infra/compose.yaml stop`. Do not run volume-deletion commands unless intentionally discarding local data. No cloud service, external transaction or production database is involved.

## Implemented boundaries and remaining work

Core validates fixed FFA configuration and temporal aliases/affiliations, with no name-only merges or scoring assumptions. Scoring is pure Decimal arithmetic with explicit rules, scopes and rounding, including unsupported/missing diagnostics. Persistence publishes validated complete candidates atomically, preserves the last valid current pointer, deduplicates revisions and writes a transactional outbox. Jobs support idempotency conflicts, row-locked claims, expiring tokens, heartbeat, fencing, delayed retries and failed state. Leased worker publication must pass its lease into `publish_snapshot`; the synthetic smoke command is not the production scheduler.

Current snapshot fields cover the first core/persistence slice only. Actual league metadata/settings, persisted cross-provider mappings, full team/manager/roster contracts, availability pagination and source completeness proof remain M1b/M1c. Source adapter retries add provider-aware jitter, Retry-After and global polling budgets; the durable queue currently provides deterministic bounded retry delay. Missing or unsupported actual FFA rules must still block affected advice.

Next: authorized local FFA access and capability inventory, then full provider normalization and nflverse manifests/coverage. Deliberate UX/UI work follows the [design system](../design/design-system.md) and [feature workflows](../product/feature-experiences.md); generic dashboard filler and ungrounded analytics do not satisfy those specifications.
