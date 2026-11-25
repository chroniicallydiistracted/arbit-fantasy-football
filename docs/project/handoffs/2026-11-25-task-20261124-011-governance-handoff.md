# Task handoff — TASK-20261124-011 — M3-3 final directive Phase B: corrected league-constrained evaluation from pinned inputs

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Resolve PB-AUD-01 to -06 and -08 and verify the Phase B v1 results: content-level live reconciliation, fail-closed ownership replay verified at every snapshot moment, availability reconstruction validated against observed snapshot states, all-week bootstrap, streaming feasibility and collisions, exact decision sets and comparable manager decisions, immutable pinned league inputs; a separately versioned corrected C05L-2026-EXP (v2) declared before it is computed, v1 preserved.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** config/dvp/league-2026-exploratory-v2.json, scripts/model/ffa_2026_pin.py, scripts/model/ffa_2026_inventory.py, scripts/model/dvp_league_2026_v2.py, libs/arbit-model/src/arbit_model/ffa_history.py, libs/arbit-model/src/arbit_model/dvp/league.py, libs/arbit-model/tests/test_ffa_history.py, libs/arbit-model/tests/test_dvp_league.py, scripts/model/dvp.py, docs/research/ffa-2026-inventory-v2.json, docs/research/ffa-2026-league-inputs-v1.json, docs/research/dvp/league-2026-exploratory-v2.json, docs/research/FFA_2026_DATA_INVENTORY.md, docs/research/dvp/LEAGUE_CONSTRAINED_2026.md, docs/research/dvp/audit-findings.json, docs/research/dvp/AUDIT_RECONCILIATION.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/README.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json, docs/project/handoffs/2026-11-25-task-20261124-011-governance-handoff.md

## Review

Reconciled PB-AUD-01 to -06, -08 and the section 8 numbers against code at 2e2520f, the database and ESPN: live checks compared only id, type and status; the replay ignored trades and would fall back to proposal time for a waiver (no case in data: 52/52 executed waivers have processed_at; trade items only on 2 canceled proposals); the availability rule ignored game locks and processing times (ESPN processes at midnight Pacific; all unowned units go on waivers after their game until Wednesday); the bootstrap dropped zero-change weeks (reproduced -90.05/+80.00 vs -96.03/+74.02); streaming picks collide; decision receipts lacked candidate sets; inputs were read live. Observed rosters never exceed 16 non-IR players; D/ST limit 3.

Files: libs/arbit-model/src/arbit_model/ffa_history.py, libs/arbit-model/src/arbit_model/dvp/league.py, scripts/model/ffa_2026_inventory.py, scripts/model/dvp_league_2026.py

## Plan

1) Pin the normalized league inputs (one read-only transaction; hashed local bundle; committed manifest). 2) Declare C05L-2026-EXP v2 (fail-closed replay verified at every snapshot; availability rule v2 with predeclared holdout acceptance; cutoff classes; all-week bootstrap; feasibility and collisions; exact decision sets; comparable managers; eligibility-aware matchups; v1 comparison) and push before computing. 3) Implement in ffa_history, league, a v2 script reading only the bundle, and content-level live checks in the inventory. 4) Recorded runs from clean commits. 5) Docs and register closure.

Files: config/dvp/league-2026-exploratory-v2.json, scripts/model/ffa_2026_pin.py, scripts/model/dvp_league_2026_v2.py

## Implement

ffa_2026_pin.py (bundle inputs-v1, manifest c354dcca, 9 files); ffa_history: UnsupportedHistory, validate_draft, processing_moments, availability_v2 (lock strictly before the moment); league: summarize blocks ALL_WEEKS/CHANGED_WEEKS with block counts and missing coverage, feasibility, collisions, matchup_effects_v2; dvp_league_2026_v2.py (pinned bundle only; ownership at every snapshot; availability validation design/holdout/decision moments; cutoff classes; four decision kinds with exact option sets, evidence, feasibility, owner at game; managers split; matchups; v1 comparison); ffa_2026_inventory.py --content (read-only alias lookups; transactions by Arbit's content hash over the union of pages; lineups by capture hash then field by field). A trial exposed the game lock compared with <= at the exact cutoff, contrary to the declared rule; fixed before the recorded run (trial output discarded). Receipts: ffa-2026-inventory-v2.json and league-2026-exploratory-v2.json at 39f763e.

Files: libs/arbit-model/src/arbit_model/ffa_history.py, libs/arbit-model/src/arbit_model/dvp/league.py, scripts/model/dvp_league_2026_v2.py, scripts/model/ffa_2026_inventory.py

## Validate

All seven checks pass (foundation, model-tests, point-in-time, ruff check, ruff format, mypy incl. dvp_league_2026_v2.py, ffa_2026_pin.py, ffa_2026_inventory.py, full pytest). Model suite 265 passed, 2 skipped (main-machine artifacts). New tests: test_ffa_history.py (fail closed on executed trades, unknown ownership items and waivers without processing times; conflicting adds; simultaneous and later moves; draft validation; rule v2 holds, locks, Tuesday exclusion, clock change, exact-kickoff), test_dvp_league.py (all-week bootstrap with zero-change weeks and missing coverage, deterministic; feasibility classes; collisions; matchup ties, unknowns and ineligible picks). Recorded runs at 39f763e: content check (536/536 transactions equal; 11/11 lineups historical fields equal) and C05L v2 from pinned inputs only (ownership equal at 1,522/1,522 snapshots; rule v2 holdout 99.3%, accepted; start -6 [-96.03, 74.02]; claimable +110; with waivers +96).

Files: docs/research/ffa-2026-inventory-v2.json, docs/research/dvp/league-2026-exploratory-v2.json, libs/arbit-model/tests/test_ffa_history.py, libs/arbit-model/tests/test_dvp_league.py

## Document

LEAGUE_CONSTRAINED_2026.md (v2 section: changes, availability validation table, v1/v2 results, week-9 and week-11 effects, feasibility and collisions, managers, matchups, unchanged conclusion; PRO capture text updated); FFA_2026_DATA_INVENTORY.md (corrections: content-level reconciliation, every-snapshot ownership, rule v2 with validation and error patterns, cutoff classes, limitations, downstream items); audit-findings.json and AUDIT_RECONCILIATION.md (PB-AUD-01..06, PB-RESULTS resolved; PB-AUD-08 in progress pending remediation 7); EXPERIMENT_REGISTRY (v2 row); decision register ENG-068; status; changelog; next action.

Files: docs/research/dvp/LEAGUE_CONSTRAINED_2026.md, docs/research/FFA_2026_DATA_INVENTORY.md, docs/research/dvp/audit-findings.json, docs/research/dvp/AUDIT_RECONCILIATION.md, docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-25T04:19:13Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=8e800a800e56c91eedb12073f7148e4a0b39e7f1ffb57bfc7979c612794b7ba9
- `model-tests`: exit=0, 2026-11-25T04:19:27Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=038709f29b1dfebd27fbc67235964e2113461cca5b58e61549bb623d7ea63639
- `point-in-time`: exit=0, 2026-11-25T04:19:28Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=4ccdf452dca17dfbf5cc1d3aedf7b05e8c8e147e93c1d9ef23b0c9c02bbace23
- `lint`: exit=0, 2026-11-25T04:19:29Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-25T04:19:29Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=678b3ca6820a0d323f54a957cc1e4426487b2bdba16694b72c6fe03386fc1d1f
- `types`: exit=0, 2026-11-25T04:19:30Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py", "scripts/model/dvp_league_2026.py", "scripts/model/dvp_league_2026_v2.py", "scripts/model/ffa_2026_inventory.py", "scripts/model/ffa_2026_pin.py"]; output SHA-256=76ecd93717f04859bb80f61d11bffe1f2f6a9d8d6f914ce1b99152bd0ae21b87
- `python-suite`: exit=0, 2026-11-25T04:20:37Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=cedde11dfd5806c404f73a854bc8889922c353f16be8df4d703c2db94364ac35

## Findings / decisions / contradictions

- 2026-11-25T04:20:52Z [correction] A trial run of the v2 experiment tested the game lock with <= at the exact preweek cutoff (the first kickoff), treating Thursday-night units as locked, contrary to the declared rule that no week-W game has started at decision time. Fixed to < with a test before the recorded run; the trial output was discarded. — libs/arbit-model/src/arbit_model/ffa_history.py
- 2026-11-25T04:20:52Z [decision_proposed] Availability rule v3 (waiver-run drops free at once; all unowned units on waivers from Tuesday until Wednesday's run) to be validated on future snapshots before any use; not adopted post hoc. — docs/research/FFA_2026_DATA_INVENTORY.md

## Remaining unresolved / blocked

Deploy key registration (owner). AUD-06, AUD-07, eligibility registry, remediation 7. PB-AUD-08 closes with remediation 7's rerun.

## Next executable action

Merge the Phase B PR after CI. Then AUD-06 (simulation suite), AUD-07 (threshold sensitivity), research eligibility registry, remediation 7 (comprehensive audit including the pinned Phase B rerun). Owner: register the evidence deploy key.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
