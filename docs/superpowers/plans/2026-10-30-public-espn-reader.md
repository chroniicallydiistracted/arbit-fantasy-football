# Public ESPN Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn the verified public FFA access into a reusable, bounded acquisition path with validated provider contracts and safe local inspection.

**Architecture:** Keep the audited reference checkout separate from Arbit code. A synchronous, read-only ESPN transport supplies observed-payload contracts and a league acquisition service; the worker exposes a manual inspection command. Provider acquisition is distinct from canonical snapshot publication: unresolved identities and unnormalized rules cannot satisfy the publication gate.

**Tech Stack:** Existing Python 3.12, standard-library HTTPS, Pydantic, pytest; no new runtime service or dependency.

**Spec:** [Data architecture](../../architecture/data-architecture.md), [public endpoint evidence](../../research/espn-public-api-audit-2026-10-30.md), DATA-001/004/005/006/007. Owner authorized the next development phase and workspace clone on 2026-10-30; message boards are explicitly out of scope. Existing stack/architecture approval continues; execute locally without a new approval round.

## Global Constraints

- Single FFA league 1729878439; configured season 2026, explicit future season rollover only.
- GET only, cookie-free public mode; fixed ESPN HTTPS origin, no redirects or environment proxies.
- Unknown data is not zero. Preserve exact source scoring settings without claiming rule support or canonical identity resolution.
- No application endpoint, credential setup, publication, scheduler, external push or deployment in this slice.
- No member identifiers or raw league payloads in logs or tracked fixtures. Fixtures use synthetic names/IDs in observed structures and are labeled synthetic.
- Acquire serially at most 30 requests/minute per transport instance; bounded requests/pages/bytes, explicit status and drift errors. One manual process only; a cross-process limiter is required before scheduled concurrent sync.

## Review Focus

1. Redirects, HTML success pages, oversized/compressed or slow payloads must produce bounded safe errors; Task 2 tests these inputs.
2. Retry-After seconds/date and repeated throttling must end the acquisition without early retry; Task 2 tests typed retry hints (the durable scheduler will own retries later).
3. Negative D/ST IDs, empty preseason rosters/drafts and unknown scoring items must remain valid observed facts; Task 3 tests those contexts.
4. Repeated pages, wrong availability filters, ownership/lineup/period/settings changes during acquisition must fail rather than return a supposedly consistent result; Task 3 tests these races. A mutation that changes and reverts between observations is inherently undetectable and must be documented.
5. CLI failures and successful summaries must not expose names, owner GUIDs, response bodies or private state; Task 4 tests actual command behavior and safe output.

### Task 1: Pinned reference and documentation scope

**Files:** `.gitignore`, `docs/research/espn-reference.md`, `scripts/validate_foundation.py`, `tests/contracts/test_foundation_references.py`, roadmap/decision/status/known-issue documentation.

**Interfaces:** ignored `.references/Public-ESPN-Fantasy-API` at `097c42f0da0b692ceb3168a2c6af1e7479be5906`; validation excludes only this external reference root, while ordinary project links/JSON remain checked.

- [x] Write a regression that copies tracked planning artifacts into a temporary root, introduces foreign broken links/malformed JSON under `.references`, and still validates; a broken project link must still fail.
- [x] Run `uv run pytest tests/contracts/test_foundation_references.py`; expect RED from foreign content being scanned.
- [x] Exclude `.references` from artifact discovery; document clone provenance, public access evidence and owner removal of message boards from integration scope. Correct the stale roadmap 401 blocker.
- [x] Repeat the focused tests and `python3 scripts/validate_foundation.py`; expect PASS; commit this deliverable.

### Task 2: Bounded public transport

**Files:** `libs/arbit-data/src/arbit_data/espn/{__init__,transport,http_deadline}.py`, `libs/arbit-data/tests/test_espn_transport.py`, root pytest paths.

**Interfaces:** `EspnTransport.get(season: int, *, views: tuple[str,...], scoring_period: int|None = None, fantasy_filter: dict[str,object]|None = None) -> FetchResult`; result has parsed JSON object and immutable source receipt (URL, observed time, SHA-256, bytes). `EspnError` carries safe code, optional HTTP status and retry-after seconds only.

- [x] Write tests against a local HTTP server through the real urllib opener for JSON/Decimal, no auth/cookies, correct view/filter query, pacing, 401/403/404/429/5xx, Retry-After date/seconds, HTML, redirects, nonfinite JSON, malformed/oversized responses and timeout. Inject the opener URL only at the test network boundary, never a public transport base-URL option.
- [x] Run `uv run pytest libs/arbit-data/tests/test_espn_transport.py`; expect missing implementation RED.
- [x] Implement fixed-origin standard-library HTTPS streaming with 15-second timeout, identity encoding, 8 MiB cap, safe status codes, no automatic retry, receipts and per-instance serial two-second pacing. Reject invalid season/period/view input before network access.
- [x] Repeat focused tests, Ruff and strict mypy; expect PASS; commit.

### Task 3: Observed contracts and consistent acquisition

**Files:** `libs/arbit-data/src/arbit_data/espn/{contracts,reader}.py`, `libs/arbit-data/tests/test_espn_reader.py`, `tests/fixtures/espn/*` with evidence/provenance README.

**Interfaces:** `EspnReader(transport).fetch_league_snapshot(season: int, scoring_period: int|None = None) -> EspnAcquisition`. Provider snapshot exposes settings, status, teams/rosters, draft, schedule and available players, all with ESPN IDs; source receipts and capture window travel with it. No canonical `LeagueSnapshotCandidate` is produced.

- [x] Add anonymized observed-structure fixtures, complete for required contract fields, preserving negative D/ST IDs, nonstandard rule/slot IDs and OFFLINE draft shape. Add assertions for exact Decimal settings, distinct requested/current periods, team records, matchup scope and full available pages.
- [x] Add failure tests for missing/wrong section metadata, duplicate/mismatched ownership or team IDs, unsupported statuses, repeated/full unterminated pages, roster/lineup/settings/period drift between initial/final reads, and empty valid preseason contexts.
- [x] Run focused reader tests; expect missing implementation RED.
- [x] Implement view-specific strict required fields with unknown additive fields ignored, preserved complete settings dictionaries, finite decimal JSON values, explicit invariants. Fetch combined settings/team/roster/matchup-score/draft/status, pages of 300 FREEAGENT/WAIVERS players until a short page (max 20 pages), then reread league context and verify ownership/lineup/settings/draft/period stability. Use requested period for all reads, including historical context. Do not describe the result as atomic.
- [x] Repeat reader and transport tests plus Ruff/mypy; expect PASS; commit.

### Task 4: Manual local inspection and handoff

**Files:** worker CLI, `services/worker/tests/test_espn_inspect.py`, pytest paths, local-development/data-architecture/status/changelog/README/AGENTS and dated handoff.

**Interfaces:** `arbit-worker espn-inspect [--scoring-period INT]` reads configured league season and prints only counts, source hashes/times and explicit acquisition-only/unnormalized-rules state; no database needed, no output file of raw data. Existing synthetic CLI unchanged.

- [x] Write CLI tests for successful redacted counts, typed provider failure, invalid period and fixture command compatibility. Run focused tests; expect RED.
- [x] Implement the command and operator instructions, including manual-only limiter and downstream normalization gates.
- [x] Run full `make runtime-check`, `git diff --check`, and one bounded opt-in live `espn-inspect`; record actual current counts and changed observations, without hardcoding audit counts as expectations.
- [x] Obtain one fresh-context whole-slice review, fix important findings with behavioral regressions, rerun required checks, update handoff and commit. Leave the branch local for owner review.

## Execution rulings

The reader advances by actual page length until an empty page, rather than treating a short page as completion; the regression proved a server cap would otherwise truncate 101 players to 50. Ownership acquisition is current-period only: historical rosters cannot be joined to current availability. The planning-artifact checker also excludes ignored local capture/state roots because a concurrently written research file previously broke document validation; the regression still rejects broken project links.

Final review identified slow header/chunk framing and extreme decimal-exponent failures. Real-clock HTTP regressions first reproduced both; the fix adds remaining-time socket reads, a shared connection/write/response I/O budget, and safe DecimalException translation. System DNS resolution is explicitly outside the interruptible I/O deadline.
