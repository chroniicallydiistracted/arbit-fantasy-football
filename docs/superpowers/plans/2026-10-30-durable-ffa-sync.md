# Durable FFA synchronization implementation plan

Date: 2026-10-30. Base: `95d8f14`. Approved next M1c phase, executed inline using the executing-plans and test-driven-development skills. Specification: [data architecture](../../architecture/data-architecture.md), [access ADR](../../architecture/decisions/004-access-live-and-pwa.md), [actual scoring proof](../../research/ffa-scoring-verification-2026-10-30.md). Requirements: DATA-001/005/006/007 and ENG-004. No member UI, recommendations, hosting or provider writes.

## Global constraints

- Fixed public FFA league/explicit season. Exact source-native aliases, scoped fantasy identities, separate athlete/NFL team/DST; never match names or derive DST identity arithmetically.
- Immutable private parsed/redacted source archives, rule versions and snapshot history. New migration, never edit applied foundation DDL. Raw response hashes remain distinct from parsed archive hashes.
- Missing or unsupported identities/rules block publication. First/new scoring definitions must reconcile completed ESPN periods. Empirical gaps retain their existing labels; recommendations stay disabled.
- Atomic, leased publication. Incomplete/failed/old captures cannot displace current; identical refreshes confirm freshness without creating revisions. Corrections append history and outbox; replay cannot promote old state.
- Shared PostgreSQL provider pacing/cooldown across scheduled workers; bounded retries, heartbeats, durable due times. Local-only operator reads are explicitly separate from future invite-only member authentication.
- Local commands require non-production `_local`/`_test` databases. No push, merge, deployment, or public league API. Default health-only API remains unchanged.

## Task 1 — Canonical contracts and private captures

Files: core identity; ESPN boundary/reader; new data `league.py`, `archives.py`; sanitized fixtures/tests.

Interfaces: `ProviderRef.scope`; canonical versioned `LeagueDocument` with UUID identities, Decimal strings, explicit source scopes/unknowns; `CaptureArchive.write/read` returns a content hash and validates bounded immutable gzip content. Retain only manager ID/display name and observed owner references. Reader stability includes manager/team membership. Missing draft profiles fail closed with an explicit mapping limitation.

Steps: write failing behavioral tests for privacy/roundtrip/tampering/size, identity scoping and source-context changes; run RED; implement; run focused tests GREEN plus lint/type checks. Expected: no provider contact details in archives; source receipts/timestamps preserved; distinct identity kinds and scopes. Commit the slice.

## Task 2 — Transactional canonical persistence

Files: new `0002_ffa_sync` migration; schema/db/snapshots/jobs; new identity repository, normalization and league publication/read repository; PostgreSQL integration tests.

Interfaces: exact temporal aliases and observed affiliations; immutable full rules/scoring evidence; full canonical documents attached to existing snapshots; source capture metadata; sync health/schedule and provider budget tables. Publication resolves identities, validates rules, writes full facts/current/outbox, and completes a supplied lease in one transaction. Full-state hashes exclude observation time, while publication lineage retains capture hashes. History exposes previous revision/change summary; replay returns original revision without promotion.

Steps: RED tests against real isolated PostgreSQL for stable aliases, atomic rollback, no-change confirmation, stale/replay handling, corrections/rule changes and lease fencing; implement; GREEN integration and existing foundation tests; commit. Expected: eight-team data can be normalized without fabricated UUIDs, points or inferred policies; prior immutable records survive updates.

## Task 3 — Reliable automatic synchronization

Files: new shared provider gate; durable sync scheduler/service; worker CLI; queue helpers; operational tests.

Interfaces: `sync --once/--watch`, `sync-status`, `sync-replay HASH`; schedule at most one active league job, leased heartbeat, persisted bounded retry/cooldown/pause, safe failure codes, last-good snapshot/freshness. One gated transport serves both acquisition and new-rule scoring audit; unchanged verified rule versions reuse immutable evidence. Private captured inputs can be replayed offline.

Steps: RED integration tests for duplicate scheduling, transient/permanent failures, stale-worker protection, shared pacing/429 circuit and unchanged/rule-changed sync; implement; GREEN focused tests; commit. Expected: network failure preserves last good data, automatic retry honors Retry-After, access/rule failures pause for operator review, restart resumes due work. Explicit one-shot requests may resume paused work.

## Task 4 — Protected local reads and operator setup

Files: API settings/routes, local environment generator/Make targets, API/integration tests and operator guide.

Interfaces: optional secret local operator token enables `/internal/league/current`, `/history`, `/snapshots/{id}`, `/sync`; token plus actual loopback peer required, no-store everywhere. No token means no data routes. Production remains unavailable pending M2 authentication. Local environment file generated once with restricted permissions and no printed secrets; process opts in explicitly with `uv run --env-file`.

Steps: RED tests for default route absence, unauthorized/nonloopback access, no-store and persisted document/history/freshness reads; implement; GREEN tests; commit. Expected: API serves the same stored canonical facts produced by worker, without source HTTP calls.

## Task 5 — Live proof, review and handoff

Run full runtime checks, isolated migration/upgrade and failure/replay tests. Migrate local development database; complete bounded live ESPN → private archive → canonical publication → authorized HTTP read. Repeat to prove no-change behavior; replay original capture offline. Leave no polling/server process running. Write sanitized evidence with counts/hashes only. Dispatch one fresh final whole-branch reviewer (executing-plans requirement), fix Important/Critical findings with failing regression tests and rerun full checks. Update AGENTS/README/status/requirements/decisions/issues/changelog, architecture/local development and dated handoff. Commit clean local branch.

Review focus: lock ordering and duplicate workers; expired leases during slow network; source drift/new rules; actual-vs-projected point scope; partial/unknown aliases; manager privacy; stale archive replay and clock freshness; gzip bomb/path/tamper handling; API peer/token handling and safe failures; rollback of first capture and pre-existing foundation migrations. No data, cookies, tokens or member names in committed evidence.
