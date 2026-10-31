# ESPN Endpoint Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every verified useful JSON/PNG request in the public audit callable through Arbit before proceeding to scoring normalization.

**Architecture:** Extend the existing guarded transport with an explicit endpoint catalog and validated request options. A provider client checks each endpoint's observed sections and returns source payloads/receipts with available, limited or metadata-only capability. An audit verifier reconstructs each successful request through the catalog and runs it through that same client, emitting safe evidence only.

**Tech Stack:** Existing Python 3.12, urllib, Pydantic, pytest and native worker CLI; no new dependency.

**Spec:** [Data architecture](../../architecture/data-architecture.md), [all audited requests](../../research/espn-public-2026-10-30.json), [audit interpretation](../../research/espn-public-api-audit-2026-10-30.md); DATA-001/004/005/006/007. Owner explicitly conditions the next phase on wiring all successful endpoints. Proceed within the accepted architecture without another approval gate.

## Global Constraints

- Fixed FFA league 1729878439; explicit supported seasons 2026–2100; GET only, no cookies/auth/proxies/redirects.
- Only exact registered ESPN route families; no arbitrary URLs or following provider `$ref` links.
- Preserve existing deadline, size, rate, Decimal and safe-error behavior; the core reader remains backward compatible.
- Message boards, failed routes, three HTML legacy routes and the unknown-view negative control are excluded. HTTP 200 shells remain explicitly limited/metadata-only.
- All source payloads remain inside the data adapter; no public application route, canonical scoring, publication or model claim follows from retrieval coverage.
- Tests stay offline and use synthetic content; opt-in live verification emits only statuses, section/count metadata and hashes.

## Review Focus

1. Catalog options/IDs, duplicate query parameters, foreign hosts, encoded paths or unexpected filters must not become arbitrary network requests; Task 1 tests rejection and exact reconstruction.
2. Player directories return root arrays, images return PNG, and scoreboards omit some IDs; Task 2 tests these distinct boundaries without relaxing JSON-object league contracts.
3. HTTP-200 shells, missing/wrong sections or wrong entity IDs must not be called complete data; Task 2 tests capability states and scope mismatches.
4. Every useful audit variant must be exercised through the production builder/client, including corrected news/standings scope, periods and filters; Task 3 tests full audit coverage and live reconstruction.
5. Verification failures must preserve partial safe evidence, stop on auth/throttling and return nonzero; Task 3 tests these cases and command output privacy.

### Task 1: Explicit route catalog and audited-request reconstruction

**Files:** `libs/arbit-data/src/arbit_data/espn/endpoints.py`, `audit_requests.py`; tests `test_espn_endpoints.py`.

**Interfaces:** `Endpoint` enum; frozen `EndpointOptions` for season/views/scoring+matchup period/player/event/team/limit/page/sport/filter; `build_request(endpoint, options) -> EndpointRequest` (fixed URL, response format, filter JSON). `audit_requests(records) -> tuple[AuditedRequest,...]` accounts for all 81 original records as callable or explicitly excluded; unexpected success cases fail closed.

- [ ] Write table-driven route examples with literal expected URLs and known input/query rejection cases. Reconstruct all 68 callable successful cases, including 63 JSON/PNG data cases and five limited/metadata cases; exclude nine HTTP failures, three legacy HTML and one unknown control.
- [ ] Run focused tests; expect missing-module RED.
- [ ] Implement the catalog and inverse audit matcher, rejecting unconsumed or duplicated non-view query parameters. Rebuild every matched URL/filter through the production builder and compare semantic query pairs before accepting it.
- [ ] Repeat tests and Ruff/mypy; expect PASS; commit.

### Task 2: Shared transport and observed capability client

**Files:** existing `transport.py`, new `client.py`, shared loopback test support and `test_espn_client.py`/transport tests.

**Interfaces:** `EspnTransport.fetch(endpoint, options) -> EndpointFetchResult` supports object/array/PNG formats from catalog only. Existing `get(...) -> FetchResult` stays object-only and preserves the core reader protocol. `EspnClient.fetch(endpoint, options) -> EndpointResponse` validates observed required sections, IDs and period metadata and labels available/limited/metadata-only.

- [ ] Add real-loopback tests for array directories, both CDN image routes, corrected hosts/queries, malformed binary/type, scope mismatch and empty/absent sections. Verify the existing guarded transport rejects unregistered URLs and that all families execute through it.
- [ ] Run tests; expect absent general fetch/client RED.
- [ ] Generalize response format handling without weakening legacy `get`; share the same serial limiter, deadlines, safe errors and receipts across all endpoints. Implement per-view/per-family section checks and opaque-ID validation. Do not manufacture empty payloads for absent data.
- [ ] Repeat all adapter/reader tests and quality checks; expect PASS; commit.

### Task 3: Executable coverage evidence, final review and handoff

**Files:** `libs/arbit-data/src/arbit_data/espn/verification.py`, worker command `espn-endpoints`, coverage report documentation/JSON, operator/status/architecture/handoff records.

**Interfaces:** `verify_audit(records, client, live=False)` accounts for every record; live mode invokes all 68 recognized successful cases through the production client. `arbit-worker espn-endpoints [--live]` reads the checked-in audit from the repository root and prints safe JSON with per-case classification/receipt/capability; nonzero on unexpected failed checks. This is opt-in manual inspection, never scheduled or mandatory CI.

- [ ] Add tests for all-route successful verification, fail-closed unexpected success, safe partial failure evidence, 401/429 stop/no retry and CLI nonzero/privacy behavior. Run and observe RED.
- [ ] Implement safe reporting/CLI, preserving prior fixture/inspection commands.
- [ ] Run full `make runtime-check` and one paced live verification through the production adapter. Validate earlier captured bodies separately to distinguish access drift from implementation issues. Record actual outcomes, never replace a failed result with the old audit.
- [ ] Obtain the required single independent whole-slice review, fix Important findings with RED→GREEN tests, rerun checks and finish documentation/local commits. Record deferred downstream scoring/sync/model scope explicitly.
