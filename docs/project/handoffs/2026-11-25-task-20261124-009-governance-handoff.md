# Task handoff — TASK-20261124-009 — M3-3 owner audit Phase B: FFA 2026 data coverage, ownership reconstruction, league-constrained D/ST evaluation

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Owner Phase B requirements (AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md): record that 2026 is FFA's inaugural season (owner decision, source docs, knowledge base, research audit); inventory and verify the ESPN data capabilities Arbit already reaches through its existing guarded integration, with a 2026 season and scoring-period coverage matrix, eligibility and temporal-integrity classes; validate lineups, rosters, player statistics and transactions; reconstruct 2026 ownership and availability from the draft and executed transactions, verified against every captured period roster and archived snapshots; split C05L into C05L-HIST (NOT_APPLICABLE), C05L-2026-EXP (run the exploratory league-constrained D/ST start/sit and streaming evaluation of B00 vs B06 on weeks 1-11) and C05L-2026-PRO (continue the prospective capture with decision-time availability); document limitations and downstream ESPN capabilities. Read-only: no provider projections, migrations, league changes, transactions or weights.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md, libs/arbit-model/src/arbit_model/ffa_history.py, libs/arbit-model/src/arbit_model/dvp/league.py, scripts/model/ffa_2026_inventory.py, scripts/model/dvp_league_2026.py, scripts/model/dvp_prospective.py, scripts/model/dvp.py, scripts/model/dvp_plan_audit.py, config/dvp/league-2026-exploratory.json, libs/arbit-model/tests/test_ffa_history.py, libs/arbit-model/tests/test_dvp_league.py, libs/arbit-model/tests/test_dvp_shadow.py, libs/arbit-model/tests/test_dvp_plan_audit.py, docs/research/ffa-2026-inventory.json, docs/research/FFA_2026_DATA_INVENTORY.md, docs/research/dvp/league-2026-exploratory.json, docs/research/dvp/LEAGUE_CONSTRAINED_2026.md, docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/research/dvp/plan-audit-receipt.json, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/PLAYER_LEVEL_REPORT.md, docs/research/dvp/MODEL_CARD.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/research/dvp/PROSPECTIVE_2026.md, docs/research/dvp/README.md, docs/research/source-register.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json, docs/project/handoffs/2026-11-24-task-20261124-009-governance-handoff.md, docs/research/dvp/M3-3_CONTINUITY.md, AGENTS.md

## Review

Phase B (owner audit): read the requirements in full and inspected the ESPN audit docs, endpoint coverage, arbit_data.espn (client, reader with HISTORICAL_AVAILABILITY_UNSUPPORTED, scoring_audit), league_history (reconciled lineup captures, transaction store), league_store/snapshots, rule_version and the worker's history lanes. Database: lineups captured and reconciled 8/8 for periods 1-11; transactions read for periods 1-12 (536 records, unique ids, 0 revised after first observation, no completed trades: 2 canceled proposals, 7 declines; waivers 52 executed, 14 failed, 7 canceled); 128 draft picks; 56 matchups (44 with results); 1,520 snapshots from 2026-10-31 with an 11-day gap (2026-11-11 to 11-21, the database outage). Rules: 24-hour waivers, INDIVIDUAL_GAME locks, D/ST limit 3; in-season trades allowed (deadline 2026-12-02, 3 vetoes; the isTradingEnabled=false flag is under draftSettings). Replaying the draft and executed adds and drops reproduces every captured period roster exactly; draft transaction items carry the team on the transaction, not the item.

Files: docs/research/espn-public-api-audit-2026-10-30.md, docs/research/espn-endpoint-coverage-2026-10-30.md, libs/arbit-data/src/arbit_data/league_history.py, libs/arbit-data/src/arbit_data/espn/reader.py, libs/arbit-data/src/arbit_data/espn/scoring_audit.py, docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md

## Plan

1) OWN-076 (inaugural season) in the decision register, source register, knowledge base and audit. 2) arbit_model.ffa_history: ownership replay from the draft and executed moves, verification against captured period rosters and snapshots, availability classes with the waiver hold. 3) scripts/model/ffa_2026_inventory.py: capabilities, coverage matrix, lineup and transaction validation, ownership replay with daily snapshot checks, D/ST state at each preweek cutoff, optional live re-verification through the existing guarded client (scoring audit, transaction re-reads; nothing stored). 4) config/dvp/league-2026-exploratory.json declared and pushed first; arbit_model.dvp.league and scripts/model/dvp_league_2026.py run C05L-2026-EXP (start, stream, stream with waivers; managers; matchup effects). 5) Prospective harness captures D/ST availability at decision time and reports league results per decision kind (C05L-2026-PRO). 6) Plan audit: C05L split (HIST not applicable, 2026-EXP done, 2026-PRO open), Phase B items, new kind; receipt regenerated. 7) Documents and records.

Files: libs/arbit-model/src/arbit_model/ffa_history.py, libs/arbit-model/src/arbit_model/dvp/league.py, scripts/model/ffa_2026_inventory.py, scripts/model/dvp_league_2026.py, config/dvp/league-2026-exploratory.json, scripts/model/dvp_plan_audit.py

## Implement

arbit_model.ffa_history (moves, replay, verify_periods, availability, snapshot_agreement); arbit_model.dvp.league (pick, decide, summarize, matchup_effects with direction against actual results); scripts/model/ffa_2026_inventory.py (DB read-only inventory, coverage, validation, ownership replay with daily snapshots, preweek D/ST state, optional live re-verification through EspnClient(EspnTransport()), nothing stored; outside the DvP scan because it imports ESPN readers); scripts/model/dvp_league_2026.py (C05L-2026-EXP under config/dvp/league-2026-exploratory.json, declared in 07505d9); dvp_prospective.py captures D/ST availability and reports league results per decision kind with a free-agents-only stream; dvp_plan_audit.py splits C05L (HIST not_applicable, 2026-EXP, 2026-PRO open), adds PB0/PB3/PB4/PB5/PB7 and eight checks. Receipts: ffa-2026-inventory.json at e57ebc4, league-2026-exploratory.json at 3848cad, plan-audit-receipt.json at 1b99375 (221 items, 164/164 checks).

Files: libs/arbit-model/src/arbit_model/ffa_history.py, libs/arbit-model/src/arbit_model/dvp/league.py, scripts/model/ffa_2026_inventory.py, scripts/model/dvp_league_2026.py, scripts/model/dvp_prospective.py, scripts/model/dvp_plan_audit.py, scripts/model/dvp.py, libs/arbit-model/tests/test_ffa_history.py, libs/arbit-model/tests/test_dvp_league.py, libs/arbit-model/tests/test_dvp_plan_audit.py, docs/research/ffa-2026-inventory.json, docs/research/dvp/league-2026-exploratory.json, docs/research/dvp/plan-audit-receipt.json

## Validate

All seven checks passed at the Phase B head: foundation, model-tests, point-in-time, lint (ruff check .), format (ruff format --check .), types (mypy on arbit-model and the six model scripts including dvp_league_2026.py and ffa_2026_inventory.py), python-suite (pytest -q). Tested results: inventory receipt from clean commit e57ebc4 with live re-verification (scoring 88/88 lineups, 1,221 player-games, 0 mismatches; transactions equal to ESPN's per period, 4 FUTURE_ROSTER records paged with period 8 explained); ownership replay equals 11/11 period rosters and 14/14 daily snapshots; C05L-2026-EXP receipt from clean commit 3848cad identical to the trial run; plan audit rerun of every stage on scratch copies (holdout from frozen tree 165d140): 221 items, 215 done, 5 open, 1 not applicable, 0 failed, 164/164 checks; model suite 213 passed, 0 skipped. Not tested: the week-13 availability capture runs only in that week's window; the harness capture code was exercised against the current snapshot (13 owned, 19 free agents).

Files: docs/research/ffa-2026-inventory.json, docs/research/dvp/league-2026-exploratory.json, docs/research/dvp/plan-audit-receipt.json

## Document

New: docs/research/FFA_2026_DATA_INVENTORY.md (capability inventory with eligibility classes, coverage by period, validation, ownership and availability method, retrieval report, limitations, downstream ESPN capabilities as future work) and docs/research/dvp/LEAGUE_CONSTRAINED_2026.md (C05L dispositions, method, results, matchup implications, prospective capture). Updated: decision register (OWN-076, ENG-066), source register (SRC-39), AGENTS.md (inaugural season), EXPERIMENT_REGISTRY (C05L-HIST, -2026-EXP, -2026-PRO rows), PLAYER_LEVEL_REPORT, MODEL_CARD, PROSPECTIVE_2026, SOURCE_PROVENANCE (ESPN league-management data, inventory outside the DvP scan), DvP README, M3-3_CONTINUITY, PLAN_COMPLETION_SCOPE (rebuilt counts, C05L split, Phase B section), status, changelog and the project next action. Corrected: an earlier progress message said trading was off; in-season trades are enabled and none completed.

Files: docs/research/FFA_2026_DATA_INVENTORY.md, docs/research/dvp/LEAGUE_CONSTRAINED_2026.md, docs/project/decision-register.md, docs/research/source-register.md, AGENTS.md, docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-25T02:36:13Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=c48a784dc8b0a085748781c2b2c8393fab4def8cdc4714ab07c46644800991e5
- `model-tests`: exit=0, 2026-11-25T02:37:59Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=3b9efbf740bac243f0d22b72eb7e9ccf6bf0d886ac118c08547c78eafee50991
- `point-in-time`: exit=0, 2026-11-25T02:38:01Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=05b29fc10012c9b43884c84ede5a6257493b4bbc06f7b33e924c6d1748cedc70
- `lint`: exit=0, 2026-11-25T02:38:13Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-25T02:38:13Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=ad2f219ae28580ec8ae080a22b693d6dbedd68c2a6187fa65f798bfa59d58077
- `types`: exit=0, 2026-11-25T02:38:14Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py", "scripts/model/dvp_league_2026.py", "scripts/model/ffa_2026_inventory.py"]; output SHA-256=af63f6cd84f6a31312288603f61eea85424057c4b4099acab5a3ac955aa8bd90
- `python-suite`: exit=0, 2026-11-25T02:39:22Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=69a8d040bb7c006187baa1437f85be994758bd654bb35128898178ff009aeb54

## Findings / decisions / contradictions

- 2026-11-25T02:30:34Z [correction] Scope extended by hand with docs/research/dvp/M3-3_CONTINUITY.md, whose inventory still called league lineups BLOCKED. — docs/research/dvp/M3-3_CONTINUITY.md
- 2026-11-25T02:35:24Z [correction] Scope extended by hand with AGENTS.md: B0 asks for the inaugural-season fact in the persistent knowledge base, and AGENTS.md is the cross-agent rule that says never to guess first-season history. — AGENTS.md
- 2026-11-25T02:39:41Z [assumption] C05L-2026-EXP counts a D/ST as claimable only when it is on no roster and was not dropped within 48 hours at the preweek cutoff; units on or possibly on waivers enter only the separate upper-bound variant. Conservative reading of B5: not every unowned player was claimable. — config/dvp/league-2026-exploratory.json
- 2026-11-25T02:39:41Z [correction] Trades: in-season trading is enabled (deadline 2026-12-02 17:00 UTC, 3 veto votes); isTradingEnabled false is a draft setting. No trade has executed (2 proposals canceled, 7 declines). This corrects an earlier progress message in the session. — docs/research/ffa-2026-inventory.json
- 2026-11-25T02:39:41Z [next_step] Owner: approve or decline the prospective sweep timer before week 13's window (2026-12-01 12:00 to 12-04 01:15 UTC); otherwise run sweep manually in that window. The week-13 capture is the first with D/ST availability. — not yet verified

## Remaining unresolved / blocked

Sweep timer approval (owner). AUD-06 simulation suite and AUD-07 threshold wording (owner-directed). Remediation 7 beyond the C05L/Phase B status additions. Transaction store keeps no earlier revisions (downstream item).

## Next executable action

Merge the Phase B PR after CI. Owner decision on the prospective sweep timer before 2026-12-01 12:00 UTC. Then remediation 7 (full status-vocabulary rebuild, per-variant validation, test coverage map), research eligibility metadata, and AUD-06/AUD-07 as the owner directs. After the season: C05L-2026-PRO and the archived forecasts.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
