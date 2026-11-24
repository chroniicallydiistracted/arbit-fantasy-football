# Task handoff — TASK-20261124-006 — M3-3 DvP audit remediation 1: prospective shadow-forecast harness; week-12 forecasts archived before kickoff

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Remediation 1 of the owner's independent audit (AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md, AUD-01): a versioned prospective harness outside the frozen method that builds forecast targets from scheduled upcoming games, verifies every frozen method and config hash (loading the frozen dvp.py from git by hash), uses only data available before each preweek cutoff, captures the data snapshots and manifests used, generates and immutably archives forecast-only B00/B06 (all frozen variants) artifacts before kickoff with a hash-chained ledger, refuses overwrites and backdating, records missed weeks as missed and reconstructions as retrospective, captures FFA D/ST roster availability for a predeclared league-constrained evaluation, and evaluates archived forecasts later with the frozen Phase B and Phase C rules, keeping missing labels. Archive 2026 week 12 before its 2026-11-26 01:00 UTC cutoff. Also repair the references broken by the owner's move of the specification into docs/research/dvp (main CI red). No change to frozen files, production or weights.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/dvp/shadow.py, scripts/model/dvp_prospective.py, config/dvp/prospective.json, libs/arbit-model/tests/test_dvp_shadow.py, docs/research/dvp/PROSPECTIVE_2026.md, docs/research/dvp/prospective/2026/ledger.jsonl, docs/research/dvp/prospective/2026/week-12/forecasts.csv, docs/research/dvp/prospective/2026/week-12/manifest.json, docs/research/dvp/prospective/2026/week-12/league.json, docs/project/changelog.md, docs/project/decision-register.md, docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/research/dvp/README.md, scripts/model/dvp_plan_audit.py, libs/arbit-model/tests/test_dvp_plan_audit.py, docs/governance/tasks/TASK-20261123-005.json, docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md, docs/project/status.md, docs/governance/state.json, scripts/model/dvp.py, libs/arbit-model/tests/test_dvp_firewall.py, docs/project/handoffs/2026-11-24-task-20261124-006-governance-handoff.md, infra/systemd/arbit-dvp-prospective.service.template, infra/systemd/arbit-dvp-prospective.timer.template, infra/systemd/install-dvp-prospective.sh, docs/research/dvp/prospective/rehearsal-2025.json, docs/research/dvp/prospective/2026/README.md

## Review

Read the owner's audit (AUD-01..AUD-07) and AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md. Confirmed AUD-01: walkforward.walk builds targets from completed observation rows (prepare keeps valid rows), so it cannot forecast an unplayed week; PROSPECTIVE_2026.md planned post-season reconstruction. Week 12's preweek cutoff is 2026-11-26 01:00 UTC (GB at LA, Wednesday), per nflverse's schedule and frozen.json. Data state: the canonical targets index 6ffb62fb holds 2026 only through week 9; nflverse holds 2026 through week 11 (observed 2026-11-24 22:57 UTC); the league's current snapshot has 8 FFA teams holding 13 D/STs. walk() needs every earlier week's point-in-time B00 for residuals, so a week-W forecast walks weeks 1..W. evaluation_join requires 1:1 labels, so missing labels need their own join. CI on main was red after the owner moved the specification into docs/research/dvp (four broken links, the audit script and test path, and a completed task's review file).

Files: docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md, docs/research/dvp/Arbit_FFA_M3_DvP_Plan.md, libs/arbit-model/src/arbit_model/dvp/walkforward.py, libs/arbit-model/src/arbit_model/dvp/asof.py, docs/research/dvp/PROSPECTIVE_2026.md

## Plan

1) Repair the moved-specification references. 2) config/dvp/prospective.json: predeclare the window, data sources, readiness, classifications (PROSPECTIVE, MISSED, RETROSPECTIVE, REHEARSAL), archive and ledger, the evaluation (frozen Phase B protocol and Phase C rule on prospective weeks only; interim without labels) and an exploratory league-constrained D/ST evaluation, committed and pushed before any week-12 forecast. 3) arbit_model.dvp.shadow (adapter, not a frozen file): schedule targets, walk_targets with the frozen walk's own steps, forecast_only, attach_labels keeping every target, coverage, hash-chained ledger, league choices. 4) scripts/model/dvp_prospective.py: verify every frozen hash and load the frozen dvp.py from git by hash; history from the frozen audit run; the target season from a fresh build_targets into the week's archive with object bytes verified; readiness; write-once archive and export; MISSED and RETROSPECTIVE handling; sweep; rehearse (2025 equivalence plus evaluation); evaluate; verify. 5) Tests. 6) Rehearse, then archive week 12 before 2026-11-26 01:00 UTC and push the export. 7) A systemd timer for weeks 13-18, proposed for the owner's approval. 8) Documents and records.

Files: config/dvp/prospective.json, libs/arbit-model/src/arbit_model/dvp/shadow.py, scripts/model/dvp_prospective.py, libs/arbit-model/tests/test_dvp_shadow.py

## Implement

arbit_model.dvp.shadow (scheduled_targets, walk_targets with the frozen walk's own steps, forecast_only, attach_labels keeping every target, coverage, hash-chained ledger_entry/verify_ledger, league_choices). scripts/model/dvp_prospective.py (load_frozen verifies 22 frozen hashes and loads the frozen dvp.py from git at f75868b by hash; history from the frozen audit run with 41 store objects verified; build_season into the week's archive; season_observations with object bytes verified and firewall admission; readiness; league_capture; write_once and append_ledger; export; forecast, sweep, reconstruct, rehearse, evaluate with --weeks for checks, verify; confirmation labels only for the complete predeclared window). config/dvp/prospective.json declared and pushed at 23:12 UTC before any week-12 forecast. dvp.SCANNED gains shadow.py and dvp_prospective.py. Timer template and installer (not installed). Week 12 archived 2026-11-24 23:12:45 UTC (6f44e5b), exported and pushed (GitHub push 23:13:15). Moved-specification references repaired.

Files: libs/arbit-model/src/arbit_model/dvp/shadow.py, scripts/model/dvp_prospective.py, config/dvp/prospective.json, libs/arbit-model/tests/test_dvp_shadow.py, scripts/model/dvp.py, docs/research/dvp/prospective/2026/ledger.jsonl, docs/research/dvp/prospective/2026/week-12/forecasts.csv, docs/research/dvp/prospective/2026/week-12/manifest.json, docs/research/dvp/prospective/2026/week-12/league.json, docs/research/dvp/prospective/rehearsal-2025.json, infra/systemd/arbit-dvp-prospective.service.template, infra/systemd/arbit-dvp-prospective.timer.template, infra/systemd/install-dvp-prospective.sh

## Validate

Governance checks on the final tree, all exit 0: foundation, model-tests (with ARBIT_DVP_AUDIT_RUN; 179 tests incl. 12 new shadow tests), point-in-time, lint, format, types (mypy incl. dvp_prospective.py and dvp_plan_audit.py), python-suite. Real-data proofs: 2025 rehearsal at 5529152: adapter reproduces every non-control frozen holdout forecast within 7.1e-15 over 3,256 rows (b09 controls differ by design; 8 extra invalid-label targets kept), evaluation path labelled REHEARSAL. Week 12 PROSPECTIVE archive: 192 rows, no null B00/B06, 22 frozen hashes verified, readiness 163/163 earlier games completed and scored, 46 store objects verified, nflverse inputs observed 22:57-22:59 UTC before generation 23:12:45 UTC; export equals the ledger hashes; verify passes. Scratch 2026 week-11 run: forecast after cutoff recorded MISSED (exit 3), reconstruct stored RETROSPECTIVE, repeat did nothing, evaluate --weeks 11 descriptive, verify passed. Real sweep: skipped week 12, waited on week 13 (16 week-12 games without results), ledger unchanged. Timer units pass systemd-analyze verify.

Files: docs/research/dvp/prospective/rehearsal-2025.json, libs/arbit-model/tests/test_dvp_shadow.py

## Document

PROSPECTIVE_2026.md rewritten (true prospective vs reconstruction, freezes and declaration times, the harness's steps, adapter equivalence, window status with cutoffs and input-complete times, timer, missed/retrospective handling, evaluation, real-data checks). docs/research/dvp/prospective/2026/README.md (export, never edit, how to verify). DvP README status, commands and documents. ENG-063. Status (PR #13 on main, stack reload, owner audit and remediation status), changelog, state.json next action.

Files: docs/research/dvp/PROSPECTIVE_2026.md, docs/research/dvp/prospective/2026/README.md, docs/research/dvp/README.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Recorded commands

- `foundation`: exit=0, 2026-11-24T23:17:53Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=ef036079404a28c8b4c55418cf9eb71de018a6ec84f7b174fa3e77cc793adc21
- `model-tests`: exit=0, 2026-11-24T23:18:04Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=3b521893fbf481a4e955f34a47d6406d1456395fff338f4d4b6e10215cfd7fec
- `point-in-time`: exit=0, 2026-11-24T23:18:05Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=0e7871f8a39a7e28b42cd44a1b946b7144c4be8eb33a5dca62546708f0f051de
- `lint`: exit=0, 2026-11-24T23:18:06Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-24T23:18:06Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=4d6b09d243f7a62583cf94da33d35135e23f005e2cd7ebd1033a75f6653d34d7
- `types`: exit=0, 2026-11-24T23:18:06Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py"]; output SHA-256=009556134e2bb430dad64127a90550286c87a020971cce9d4acb642f74b8e00b
- `python-suite`: exit=0, 2026-11-24T23:19:11Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=be6f1fff73ef9de5c071a61f095f835907e17ba116c7e1fa90a54d48a5cbf834

## Findings / decisions / contradictions

- 2026-11-24T23:15:22Z [correction] Scope adjusted by hand: the timer ships as templates plus an installer (infra/systemd/*.template, install-dvp-prospective.sh) like the existing units, and the rehearsal receipt is in scope; the unit files named at start are not created. — infra/systemd/install-dvp-prospective.sh
- 2026-11-24T23:19:27Z [question] Owner approval needed to install the prospective sweep timer (sh infra/systemd/install-dvp-prospective.sh, six-hourly user timer from the main checkout, research only, read-only DB). Without it, weeks 13-18 need a manual sweep in each window; a week not archived before its cutoff is recorded MISSED. — infra/systemd/install-dvp-prospective.sh

## Remaining unresolved / blocked

Weeks 13-18 depend on the timer approval or manual sweeps; remediations 2-7 open; evaluation waits on the games; the exported archive copies are committed per week by an agent (the timer writes only the git-ignored archive and an export folder under artifacts).

## Next executable action

Merge PR for TASK-20261124-006 (branch claude/m3-dvp-prospective). Owner decision: install the prospective sweep timer, or run dvp_prospective.py sweep in each week's window (week 13: 2026-12-01 12:00 to 12-04 01:15 UTC). Then owner audit remediations 2-7 per docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md. After the season: evaluate the archived forecasts and put the D/ST weight decision to the owner (OWN-074).

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
