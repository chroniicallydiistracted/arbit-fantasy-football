# Arbit M1a Core and Snapshot Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Parallel agent work requires explicit authorization; this plan does not require it.

**Goal:** Establish a locally runnable, tested core for fixed FFA configuration, identity, exact scoring, durable snapshot publication and a health/readiness path without claiming live FFA integration.

**Architecture:** Python core/data libraries are composed by an API and worker with PostgreSQL. A fixture-driven end-to-end path proves atomic, versioned publication; live ESPN access and full nflverse ingestion are subsequent M1 slices. No private data endpoint is exposed before M2 authentication.

**Tech Stack:** Python 3.12 baseline, uv workspace, FastAPI/Pydantic, SQLAlchemy/Alembic, pytest/Ruff/type checker, PostgreSQL 18 target; Node 24/pnpm only for contract validation tooling at this slice.

**Spec:** [Foundation design](../specs/2026-10-30-arbit-foundation-design.md), [data architecture](../../architecture/data-architecture.md), [API contracts](../../architecture/api-contracts.md).

## Global Constraints

- Single FFA league, annual redraft; do not add tenancy or a second league provider.
- ESPN league `1729878439`, season `2026`; no assumed PPR, slots, draft format or waiver system.
- Unknown data is not zero. Unknown scoring/identity blocks affected advice explicitly.
- Exact Decimal scoring belongs in core; adapters/client cannot reimplement it.
- ESPN interactions read-only, credentials server-only and excluded from source/fixtures/logs.
- Proposed architecture must be reviewed/adoption recorded before runtime installation; framework versions/lockfiles are selected then, not claimed already pinned.
- Current local check is `python3 scripts/validate_foundation.py`. Commands introduced below become available only with Task 1.

## Review Focus

1. Partial/paginated provider results must preserve the last complete current snapshot — Task 4 rejection test.
2. Unknown stat IDs, nonlinear bonuses and negative/fractional scores must not silently use default PPR — Task 3 boundary fixtures.
3. Same-name athletes, D/ST and historical team changes must not cross-map — Task 2 ambiguity tests.
4. Duplicate or overlapping worker completion must not overwrite newer state — Task 4 lease/fencing and idempotency tests.
5. A copied client environment or diagnostic response must not expose secrets — Task 1 configuration/log tests and Task 5 health payload test.

## File map

Create root Python workspace/lockfile and real commands; `libs/arbit-core/src/arbit_core/{config,identity,rules,scoring}.py`; `libs/arbit-data/src/arbit_data/{contracts,snapshots,jobs}.py`; service entry points under `services/api/src/arbit_api` and `services/worker/src/arbit_worker`; SQLAlchemy/Alembic schema under `services/api/migrations`; local runtime under `infra/compose.yaml`; focused tests under each Python member and integration tests under `tests/integration`. Retain current responsibility READMEs. Add standards-compliant contract validation using the schemas already in `packages/contracts/schemas`.

### Task 1: Reproducible local runtime and checks

**Files:** create root/member `pyproject.toml`, `uv.lock`, `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `infra/compose.yaml`; update Makefile/CI/validation guide; add `services/api/tests/test_config.py`.

**Interfaces:** consumes confirmed league JSON and `.env.example`; produces workspace imports `arbit_core`, `arbit_data`, `arbit_api`, `arbit_worker`, a disposable PostgreSQL test service and `make runtime-check`.

- [ ] Record ADR-001/002 adoption and exact supported runtime/tool/dependency/image versions; retain proposal history. If stack review changes it, revise this plan before generating code.
- [ ] Create the minimal native workspaces and frozen lockfiles, with Python 3.12 and Node 24 compatibility checks. Implement `make runtime-check` to run format/lint/type, pytest and standards-compliant JSON-schema example validation; do not add empty fake test targets.
- [ ] Add config rejection tests for missing league/season, unsafe production auth bypass, and secrets rendered into health/log/client configuration. Expected behavior: errors name missing setting without containing its secret value.
- [ ] Implement typed secret settings and local-only bind defaults; pin local PostgreSQL image and health check. Use an isolated test database with migrations, not production data.
- [ ] Run `uv sync --frozen`, `pnpm install --frozen-lockfile`, `make runtime-check`, and the foundation validator; record results and commit the focused bootstrap change within normal repository authorization.

### Task 2: Fixed league configuration and canonical identity

**Files:** create `libs/arbit-core/src/arbit_core/config.py`, `identity.py`, tests `test_league_config.py`, `test_identity.py`; add schema-validation fixture cases.

**Interfaces:** `load_league_config(path: Path) -> LeagueConfig`; `ProviderRef(provider: str, entity_kind: EntityKind, external_id: str)`; `resolve_identity(ref: ProviderRef, as_of: datetime) -> ResolvedIdentity | UnresolvedIdentity`. `EntityKind` is athlete/nfl_team/defense_unit/fantasy_team; unresolved result carries reason/candidates, not guessed identity.

- [ ] Write tests asserting the checked-in config loads league `1729878439`/2026; a different league fails fixed-scope validation; provider IDs preserve leading zeroes; invalid/missing season fails clearly. Run `uv run pytest libs/arbit-core/tests/test_league_config.py -q` and observe relevant failure.
- [ ] Implement configuration type/loader matching the checked-in schema. Run the same tests and confirm pass.
- [ ] Write identity tests: two synthetic same-name athletes remain unresolved without verified alias; athlete and D/ST aliases never collide; team affiliation changes with cutoff; overlapping active aliases reject. Run `uv run pytest libs/arbit-core/tests/test_identity.py -q` and observe failure.
- [ ] Implement typed identities/aliases and deterministic resolution with explicit unresolved state. Run both focused test files, `make runtime-check`, and record requirement DATA-005/CTX-001 evidence; commit the focused slice.

### Task 3: Exact scoring and unsupported-rule behavior

**Files:** create `libs/arbit-core/src/arbit_core/rules.py`, `scoring.py`, `libs/arbit-core/tests/test_scoring.py`, clearly synthetic rule/stat fixtures.

**Interfaces:** `score(stat_line: StatLine, rules: RuleSet) -> ScoreBreakdown`, contributions as Decimal; `UnsupportedRuleError(rule_ids: tuple[str, ...])`. RuleSet includes content hash, version, supported linear/threshold/range mappings and retained unknown IDs.

- [ ] Write a failing hand-calculated synthetic test: 250 pass yards ×0.04 +2 pass TD ×4 −1 INT ×2 +25 rush yards ×0.1 = Decimal `18.50`. Add exact per-rule contribution assertions. Run `uv run pytest libs/arbit-core/tests/test_scoring.py -q` and confirm failure.
- [ ] Implement pure Decimal evaluation and contribution breakdown. Test threshold bonus: 299 pass yards is `11.96`; 300 with a 3-point ≥300 bonus is `15.00`. A missing applicable required stat must be unknown/error, not zero; an explicitly zero stat is valid.
- [ ] Add negative/fractional, threshold boundaries, per-game versus season bonus, kicking distance/ranges, D/ST rule definitions and correction fixtures only for explicitly defined synthetic rules. An unknown ID `9999` raises UnsupportedRuleError and remains in diagnostics; no default scoring inference.
- [ ] Run focused tests and runtime checks. Record that this is core correctness against synthetic rules, **not FFA score reconciliation**; enumerate actual FFA category mapping/reconciliation as M1b/M1c work. Commit the scoring slice.

### Task 4: Atomic snapshots and durable job semantics

**Files:** create `libs/arbit-data/src/arbit_data/contracts.py`, `snapshots.py`, `jobs.py`; migrations; `tests/integration/test_snapshot_publication.py`, `test_job_leases.py`.

**Interfaces:** `publish_snapshot(candidate: LeagueSnapshotCandidate, unit_of_work: UnitOfWork) -> SnapshotRef`; `get_current_snapshot(season: int, unit_of_work: UnitOfWork) -> LeagueSnapshot | None`; `claim_job(worker_id: str, now: datetime) -> LeasedJob | None`; `complete_job(job_id: UUID, lease_token: UUID, result_ref: str) -> CompletionResult`. Candidate includes manifest/rules hash, complete flag, provider observation time, owned/available records and revision; incomplete publication raises `IncompleteSnapshotError`.

- [ ] Add PostgreSQL integration fixtures/migrations. Write tests: publish complete A; reject partial B while pointer remains A; replay A without duplicate ownership/outbox; duplicate player ownership rejects transaction; older observed revision cannot replace newer pointer. Run `uv run pytest tests/integration/test_snapshot_publication.py -q` against the isolated DB and confirm meaningful failures.
- [ ] Implement schema constraints, transactional publication, immutable revisions and unique idempotency/outbox keys. Keep raw bodies out of serving responses and redact before persistence.
- [ ] Write tests: lease expires and another worker reclaims; stale lease token cannot complete/re-publish; two claimers get distinct active work; retry exhaustion persists failed/dead-letter state. Run `uv run pytest tests/integration/test_job_leases.py -q` and observe failures.
- [ ] Implement lease claim/heartbeat/fenced completion and bounded retry states. Run integration/runtime/foundation checks. Record DATA-006 and concurrency evidence; commit migrations and publication/jobs together.

### Task 5: Local fixture-driven service path and handoff

**Files:** create `services/api/src/arbit_api/main.py`, `services/worker/src/arbit_worker/main.py`, `tests/integration/test_foundation_path.py`; update status, handoff and validation guide.

**Interfaces:** FastAPI app with `/health/live` and `/health/ready`; worker fixture command loads a synthetic candidate and publishes it; internal repository read returns the same pinned snapshot. No unprotected private data API or ESPN credential import UI is introduced.

- [ ] Write a failing integration test: migrate isolated DB → publish synthetic complete candidate through worker composition → read current snapshot through service repository → assert same snapshot/rules/hash and unique outbox record. Readiness returns unavailable for missing migration/DB and healthy when configured; health includes no secret or raw league payload.
- [ ] Implement the minimal service composition and health endpoints. Keep readiness independent of upstream ESPN availability; complete data path uses fixtures, not a mandatory network call.
- [ ] Run `make runtime-check`, targeted integration path, fresh local service health smoke check and foundation validation. Record exact command/results and close only the M1a obligations actually proven.
- [ ] Update requirement status evidence, status/changelog/handoff, and next task: authorized FFA settings/capability inventory and sanitized adapter proof at M1b. Do not declare full M1 or live integration complete; commit the reviewed slice.

## Self-review and execution boundary

This plan covers the runtime/core/snapshot slice. It deliberately does not implement full ESPN/nflverse/Sleeper ingestion, member sign-in, projection models, any advisor, Live graphics or Archive UI; the roadmap retains those obligations. Source access, exact FFA rule support and real deployment require their own evidence. Verify adopted stack choices and dependencies before execution, then follow each gate without substituting documentation for behavior.
