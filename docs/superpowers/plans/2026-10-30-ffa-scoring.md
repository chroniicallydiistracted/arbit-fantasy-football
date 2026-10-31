# Actual FFA Scoring Mapping and Reconciliation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize all 46 actual FFA scoring definitions and verify completed-period player and starting-lineup scores against ESPN before recommendations can be enabled.

**Architecture:** A pinned football category map translates provider IDs into the existing pure Decimal scorer. Normalization compiles separate athlete/D/ST rules, including D/ST override 16 and per-game allowed-points/yards ranges. A bounded verifier selects actual weekly stat blocks from archived boxscores, recomputes player contributions/totals and starting-lineup totals, brackets the settings version, and reports safe provenance and unsupported/missing cases.

**Tech Stack:** Existing Python 3.12, Pydantic, exact Decimal core scoring, guarded ESPN client, pytest; no new dependency or public application endpoint.

**Spec:** [Data architecture](../../architecture/data-architecture.md), [owner continuation and endpoint handoff](../../project/handoffs/2026-10-30-endpoint-coverage.md), DATA-001/004/005/006/007. Owner explicitly authorized this phase after endpoint wiring. Primary request/response evidence is authoritative; reference documentation is not sufficient when its IDs contradict actual football data.

## Global Constraints

- FFA 1729878439 / explicit season 2026; read-only public access; preserve the existing transport budget and safe output.
- Use raw `stats` for arithmetic, actual `statSourceId=0`, game/weekly `statSplitTypeId=1`, exact requested season/period and games-played marker 210=1. Projections and season aggregates cannot become actual game scores.
- The reference repository's football ID table and appliedStats description are incorrect. Mapping provenance is the maintained wrapper's own source at cwendt94/espn-api commit 700e15ddbb91124f031473d2411c8a6285944274, file blob 81834cda9e5dac613ebcfac9ad29a1619ba46c28, cross-checked with actual ESPN stat/contribution pairs. Copy factual mappings, not third-party implementation.
- Treat D/ST override 16 as a scoring role independent of bench/IR lineup placement. Unknown categories, reverse items, override roles or unsupported configuration fail the affected support gate.
- Per-game D/ST range inputs are raw 120 (points allowed) and 127 (yards allowed), checked against configured source indicator flags. Do not substitute D/ST-adjusted 187 or guess point-allowance definitions from play text.
- Recognized additive count fields omitted inside a complete played-game stat map are explicitly zero-suppressed source counts. Fill only those known counters, only with a valid actual block/GP=1; preserve a list/policy marker. Missing entire maps/blocks or required range totals remain unknown. Applied nonzero contributions without raw stats are errors.
- Compare at explicit cent precision, half-up as Arbit's reconciliation/display policy. Current FFA rates/counts produce exact cents; unobserved tie behavior is not claimed as ESPN's contract.
- Recommendations stay disabled. Scoring support/reconciliation is separate from canonical identities, persisted sync, model evaluation, member authentication and feature release.

## Review Focus

1. Wrong periods, projections, duplicate blocks or aggregate/multi-game stats must not enter actual scoring; Task 2 tests scope and completeness failures.
2. Missed FG is category 85; 50–59/60+ are disjoint 198/201; D/ST bands use exact boundaries and role overrides even on bench; Task 1 uses hand-calculated examples and boundary cases.
3. Sparse zeros require an explicit complete played-game contract; missing data and unknown/reverse/override categories must block verification; Tasks 1–2 test these cases.
4. Bench/IR, locked historical lineups, duplicate starters and unsupported slot/period configurations must not inflate team scores; Task 3 tests lineup totals and source drift.
5. Provider float serialization noise must not hide real score/contribution mismatches, nor leak names into reports; Tasks 2–3 test both and preserve source receipts/coverage for unobserved rare categories.

### Task 1: Factual category map and actual rules normalization

**Files:** `libs/arbit-data/src/arbit_data/espn/scoring_mapping.py`, `scoring_rules.py`, observed numeric-only fixtures under `tests/fixtures/espn`; `test_ffa_scoring_rules.py`.

**Interfaces:** `normalize_scoring(settings, season) -> NormalizedScoring` exposes athlete/DST RuleSets, all-source support diagnostics and semantic config hash; immutable mapping version/source provenance. Unknown definitions are retained as UnsupportedRule. Roles are athlete/default positions 1–5 and defense_unit/default 16, never lineup-slot-dependent.

- [ ] Write tests using actual 46 settings: QB 334 pass yards/two pass TD +23 rush yards/two rush TD =35.66; kicker one under-40 and one 40–49 FG, one missed FG, two PAT =8; 60+ FG counted once at6; D/ST 2 INT/4 sacks/return TD/13 PA/238 YA =19. Test range boundaries 0/1/6/7/13/14/17/18/27/28/34/35/45/46 and yard bands, unknown/reverse/extra overrides, changed rates/hash, duplicate rules and unsupported team/enhancement settings.
- [ ] Run focused tests and observe RED; implement mapping/normalization through existing core rules; repeat tests + Ruff/mypy, expect PASS; commit.

### Task 2: Scoped actual-stat and contribution reconciliation

**Files:** `scoring_stats.py`, optional `contracts.StatBlock.applied_stats`, `test_ffa_scoring_stats.py` and anonymized observed cases.

**Interfaces:** `reconcile_player(player, period, normalized, official_pool_total) -> PlayerReconciliation` computes from raw scoped stats; includes role, exact total, source total, per-rule discrepancies, zero-suppressed IDs and verification/known-zero status. A completed actual block must be unique, present and GP=1. Absent/GP=0 blocks with an explicit official zero are labeled provider-zero and never counted as verified played-stat cases.

- [ ] Add actual anonymized QB/K/DST examples and failures for source/split/season/period/GP, missing maps/totals, duplicate blocks, range-flag contradiction, missing scored raw value and genuine provider total/contribution mismatch. Verify floating serialization artifacts reconcile at cents.
- [ ] Run and observe RED; implement without reading appliedStats as input values or filling missing maps with zero. Repeat rule/stat tests and quality checks; expect PASS; commit.

### Task 3: Completed-week player/lineup audit and safe operator command

**Files:** `scoring_audit.py`, worker `espn-score-audit` command, tests for audit/CLI, research support/reconciliation reports, operator/status/architecture/handoff records.

**Interfaces:** `audit_scoring(client, season, periods=None)` reads settings/status, maps all configured rules, fetches each completed period's mRoster/mBoxscore/mMatchupScore with scoring+matchup scope, recomputes every archived roster entry and active-lineup total, then rereads settings. Default periods are observed first through latest-1, bounded by17; reject current/future/unsupported multiweek mappings. Command prints counts/diagnostics/hashes only and returns nonzero on unsupported/missing/mismatched cases. Raw data stays ignored.

- [ ] Add deterministic tests for exact player/lineup sums, bench/IR exclusion, duplicate starters, unsupported slots/period mapping, settings changes, unknown/nonzero missing actuals and safe CLI failure/success. Run and observe RED.
- [ ] Implement audit/command using existing provider routes; preserve all failed/skipped coverage and keep recommendationsEnabled false.
- [ ] Run a bounded live audit across completed weeks, record actual support/nonzero coverage and player/team/contribution differences; investigate discrepancies rather than widening tolerance. Add meaningful regressions if provider behavior differs.
- [ ] Run full runtime checks, obtain one independent whole-slice review, fix Important findings with RED→GREEN tests, rerun necessary checks and update final documentation/local commits. No merge/push/deploy.
