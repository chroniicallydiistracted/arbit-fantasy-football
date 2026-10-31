# Local Development — M1

The runtime/core/snapshot foundation is implemented. Real canonical FFA ingestion and protected local operator reads are implemented; see the [sync guide](ffa-synchronization.md). Comprehensive NFLverse storage, source-revision proofs, exact GSIS/ESPN joins and protected source-stat reads are implemented; see the [NFLverse guide](nflverse-ingestion.md). There is no frontend UI, member authentication or projection model yet. All fixture data is explicitly synthetic and may only publish to a database ending in `_fixture` or `_test`.

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

`db-up` starts only the dedicated `arbit-dev` PostgreSQL service on **127.0.0.1:55439**, preserving its named volume, and idempotently creates `arbit_test` and `arbit_fixture`. The published local credentials are for this local container only and must not be used for any deployed service. Integration tests default to `arbit_test`; override `ARBIT_TEST_DATABASE_URL` for an isolated test host. Names must end in `_test`. Each test creates and removes its own random schema with no public-table fallback. Migration version tables and readiness checks bind to the intended current schema; tests never drop public tables or the database. Database tests are not silently skipped when the service is unavailable.

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

## Public FFA inspection

From the repository root, after `uv sync --frozen`, run:

```sh
uv run arbit-worker espn-inspect
# Optional explicit current period; historical ownership acquisition is rejected.
uv run arbit-worker espn-inspect --scoring-period 8
```

This opt-in command reads the configured 2026 public league without cookies, credentials or a database. It prints counts, UTC capture times, request URLs/filters and body checksums only; it does not save source bodies, publish a canonical snapshot or calculate advice. A successful fresh read observed eight teams, 132 owned players, 923 available players, 46 scoring items and 128 draft picks; these are observations, not hardcoded expectations. [Live receipt](../research/espn-reader-live-2026-10-30.json).

For the complete audited surface, run `uv run arbit-worker espn-endpoints` for offline wiring coverage, or add `--live` for the paced 68-case source verification. The report distinguishes 63 data/PNG cases, three limited responses, two metadata-only responses and 13 excluded cases. A failed live check returns nonzero with safe partial evidence. See the [coverage matrix](../research/espn-endpoint-coverage-2026-10-30.md).

Run one inspection process at a time. One transport serializes requests to at most 30/minute, caps each body at 8 MiB and availability at 20 requests, and stops on typed provider or consistency errors. A 15-second elapsed I/O budget covers address attempts after DNS, TLS, writes, headers, bodies and chunk framing. Every socket read receives only the remaining budget, so periodic bytes cannot extend it. Synchronous system DNS resolution cannot be interrupted; this is not a guaranteed DNS or absolute process deadline. An error goes to stderr as a safe code/status/retry hint with exit 1. Invalid CLI arguments exit 2. Respect `retryAfterSeconds`; the command never retries automatically. A 429 also prevents early reuse of the same transport. Current published database state is unaffected by every inspection outcome.

Scheduled sync now uses a [separate durable path](ffa-synchronization.md) with shared provider pacing, retries and canonical publication; these standalone research commands retain their per-instance budget. No member login, historical availability or atomic multi-request snapshot is implied. Message boards are excluded from scope. The [pinned reference](../research/espn-reference.md) lives under ignored `.references`; local captures and third-party files are excluded from the planning-artifact checker, while project links/contracts remain validated.

## Actual FFA scoring audit

```sh
uv run arbit-worker espn-score-audit
uv run arbit-worker espn-score-audit --periods 1 2 3 4 5 6 7
```

Default coverage is the provider's observed first through latest-minus-one period (maximum 17); current/future and multiweek matchup periods are rejected. Each selected period uses archived boxscores, exact actual-stat scope and fetched scoring settings, then a final settings-version check. The command compares independent raw-stat contributions, scoped player references and starting-lineup totals, returning nonzero for unsupported, missing, mismatched or changed input. No database, ESPN secrets or recommendations are needed or enabled. Reports contain counts, diagnostics and source hashes; no names or raw source payloads.

The [final evidence](../research/ffa-scoring-verification-2026-10-30.md) verifies 46 configured rules, 797 played games, 121 separately labeled provider-zero entries and 56 lineups across weeks 1–7. Eleven categories have no nonzero observed example; synthetic tests cover their formulas/boundaries. Private parsed-input archives replay the same results. Use the recorded source/mapping/code hashes; later corrections require a new capture and audit. Do not use the reference repository's incorrect football ID table or substitute projections/current pool totals for scoped actuals.

## Implemented boundaries and remaining work

Core validates fixed FFA configuration and temporal aliases/affiliations, with no name-only merges or scoring assumptions. Scoring is pure Decimal arithmetic with explicit rules, scopes and rounding, including unsupported/missing diagnostics. Persistence publishes validated complete candidates atomically, preserves the last valid current pointer, deduplicates revisions and writes a transactional outbox. Jobs support idempotency conflicts, row-locked claims, expiring tokens, heartbeat, fencing, delayed retries and failed state. Leased worker publication must pass its lease into `publish_snapshot`; the synthetic smoke command is not the production scheduler.

Full canonical FFA documents now include persisted exact ESPN aliases, observed affiliations, immutable policy/scoring versions, manager/team membership, rosters/availability, standings, matchups and draft picks. Source health, shared request pacing, retries and correction history are implemented and live-verified. Exact GSIS/ESPN crosswalks are implemented and locally verified in M1d. Member/account binding, Sleeper supplemental mappings, semantic model features, optimization and model evaluation remain later work. Unknown/unsupported input prevents publication; recommendations remain disabled.

M1e supplemental/live-source proof and asset prerequisites are implemented; use the [operator guide](supplemental-live-sources.md) for cached acquisition, inspection, verification and offline replay. Next: M2 member authentication/application shell, with OIDC/invite policy selected before auth implementation. M1d has fully imported and verified the published NFLverse catalog; rerun commands and source limits are in the [operator guide](nflverse-ingestion.md). Deliberate UX/UI follows the [design system](../design/design-system.md) and [feature workflows](../product/feature-experiences.md).
