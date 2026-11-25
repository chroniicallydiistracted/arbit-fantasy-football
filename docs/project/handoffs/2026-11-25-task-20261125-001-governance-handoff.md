# Task handoff — TASK-20261125-001 — M3-3 final directive: AUD-06 simulation suite and AUD-07 threshold interpretation

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Implement and execute the predeclared statistical simulation suite (SIM-01 to SIM-18) exercising Arbit's actual DvP estimators and the complete development-selection-validation-decision procedure against known data-generating processes, with uncertainty validation; reproduce and correct the interpretation of the 1.8-point Phase C threshold and run a separately versioned descriptive threshold sensitivity, without changing any frozen threshold, method or the 2026 confirmation.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** config/dvp/simulation-v1.json, config/dvp/threshold-sensitivity-v1.json, libs/arbit-model/src/arbit_model/dvp/simulate.py, libs/arbit-model/tests/test_dvp_simulate.py, scripts/model/dvp_simulate.py, scripts/model/dvp_thresholds.py, scripts/model/dvp.py, docs/research/dvp/simulation-v1.json, docs/research/dvp/threshold-sensitivity-v1.json, docs/research/dvp/SIMULATION_AUD06.md, docs/research/dvp/THRESHOLDS_AUD07.md, docs/research/dvp/plots/simulation, docs/research/dvp/audit-findings.json, docs/research/dvp/AUDIT_RECONCILIATION.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/PLAYER_LEVEL_REPORT.md, docs/research/dvp/README.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json, docs/project/handoffs/2026-11-25-task-20261125-001-governance-handoff.md, scripts/model/dvp_simulate_summary.py

## Review

AUD-06 had no simulation suite; AUD-07's derivation (config/dvp/sitstart.json practicalMinimumDerivation) uses 0.5+asin(rho)/pi with D/ST B00's development Spearman 0.1448. Read the actual estimator, selection and decision code to exercise it unchanged: walkforward (prepare, fit_fold, walk, metrics, decide), shadow (scheduled_targets, walk_targets with extra hooks, forecast_only, attach_labels), explore (make_extra, make_opportunity_extra), lab (adjust, groups, reml_components, bootstrap_components), reliability (halves, split_half), opportunity.reliability, the frozen dvp.py _select, decisions (units, pairs, metrics, decide), league (decide, summarize). Pilot: about 5.7 s per full-procedure repetition on 8 workers.

Files: config/dvp/sitstart.json, libs/arbit-model/src/arbit_model/dvp/walkforward.py, scripts/model/dvp.py

## Plan

1) Declare and push config/dvp/simulation-v1.json (scenarios SIM-01..18, DGP, truth, reps, streams, measurements, acceptance A1-A8, inconclusive rule, budget) and config/dvp/threshold-sensitivity-v1.json before running. 2) Generator arbit_model.dvp.simulate in the real schemas with tests. 3) Runner (E1, E2, E3, U; resumable; spawned workers) and summarizer (acceptance with Monte Carlo intervals, plots). 4) Pilot against the budget, then the full suite. 5) AUD-07 script: reproduce the derivation, Pearson/Spearman, non-uniqueness on the actual forecasts, the descriptive grid from committed receipts. 6) Reports, register closure, records.

Files: config/dvp/simulation-v1.json, config/dvp/threshold-sensitivity-v1.json

## Implement

simulate.py (Scenario, SCENARIOS, generate with traits, persistence, abrupt/drift, exposure, MCAR/MNAR, shocks, heavy tails, tiers, volume/efficiency channels, oracle; known_difference); dvp_simulate.py (E1 estimator recovery, E2 complete procedure with every frozen and exploratory variant and Phase C, E3 league with all-week, changed-week and naive bootstraps and a separate truth, U bootstrap coverage; SeedSequence streams; resumable JSONL; frozen _select from git); dvp_simulate_summary.py (measurements, acceptance A1-A8 with the declared two-sided A8 check plus a labelled one-sided supplement, plots via arbit_model.dvp.svg); dvp_thresholds.py (D1, D2). Full suite ran at cc25e2c (33,100 repetitions, 0 failed); summary at 901da3d; thresholds at e65dcea.

Files: libs/arbit-model/src/arbit_model/dvp/simulate.py, scripts/model/dvp_simulate.py, scripts/model/dvp_simulate_summary.py, scripts/model/dvp_thresholds.py

## Validate

All seven checks pass (foundation, model-tests, point-in-time, ruff check, ruff format, mypy over arbit-model and twelve model scripts, full pytest). Model suite includes test_dvp_simulate.py (7 deterministic generator checks: schema and orientation, determinism, oracle and non-touchdown noise, REML recovery and null, missingness and exposure, the known RMSE difference, the volume identity). The expensive suite ran separately at cc25e2c, not in CI: 33,100 repetitions, 0 failed; acceptance A1, A2, A4, A5, A6, A7 PASS, A3 D/ST PASS and WR INCONCLUSIVE, A8 FAIL (reported). AUD-07: the 1% grid row reproduces every frozen holdout label; the derivation reproduces 1.82 points.

Files: docs/research/dvp/simulation-v1.json, docs/research/dvp/threshold-sensitivity-v1.json, libs/arbit-model/tests/test_dvp_simulate.py

## Document

SIMULATION_AUD06.md (design, acceptance, E1, E2, uncertainty, effect on earlier conclusions, limitations, governance implications, reproduction); THRESHOLDS_AUD07.md (D1 derivation reproduced and qualified, D2 grid, D3 conclusions); PLAYER_LEVEL_REPORT.md practical-minimum wording; plots/simulation (4 SVG); audit-findings.json and AUDIT_RECONCILIATION.md (AUD-06, AUD-07 resolved); EXPERIMENT_REGISTRY (AUD06, AUD07 rows); DvP README; decision register ENG-069; status; changelog; next action.

Files: docs/research/dvp/SIMULATION_AUD06.md, docs/research/dvp/THRESHOLDS_AUD07.md, docs/research/dvp/audit-findings.json, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-25T08:40:56Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=24569610f1938358d0c297ccfcebf341d06ec227418b706a32c3839e0768046a
- `model-tests`: exit=0, 2026-11-25T08:41:11Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=7e3b48301d71e01e8e38e5db0c7926adc1e55ca30f7265f2999561f3c411c5dd
- `point-in-time`: exit=0, 2026-11-25T08:41:13Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=1aa37a7424e520e34bd6d91345552d608e10f3c40943b32cbea0f8ec9037b89f
- `lint`: exit=0, 2026-11-25T08:41:13Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-25T08:41:13Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=d65d1849237d5f64b980d3add6001f7f9057674694ba95ccad4930ca1b5c9d7f
- `types`: exit=1, 2026-11-25T08:41:16Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py", "scripts/model/dvp_league_2026.py", "scripts/model/dvp_league_2026_v2.py", "scripts/model/ffa_2026_inventory.py", "scripts/model/ffa_2026_pin.py", "scripts/model/dvp_simulate.py", "scripts/model/dvp_simulate_summary.py", "scripts/model/dvp_thresholds.py"]; output SHA-256=b02a27d36849e7c038eef46bc5759b006d5aaed49639c46a762f9fa389d3601f
- `python-suite`: exit=0, 2026-11-25T08:42:24Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=3e867ea68fea11d44b4f487ef655abc7169c3f2f592fa7b7a9461ac8e7ae9cfc
- `foundation`: exit=0, 2026-11-25T08:42:36Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=24569610f1938358d0c297ccfcebf341d06ec227418b706a32c3839e0768046a
- `model-tests`: exit=0, 2026-11-25T08:42:52Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=3a783271210cd4fd7b60f477d6e5f6575760dae04f551c62b3a8516b0d1c69b1
- `point-in-time`: exit=0, 2026-11-25T08:42:53Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=ed8668431f13ca8253596def935c4a63dbd6ffa9aded074e30bfa7ae751f9446
- `lint`: exit=0, 2026-11-25T08:42:53Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-25T08:42:53Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=d65d1849237d5f64b980d3add6001f7f9057674694ba95ccad4930ca1b5c9d7f
- `types`: exit=0, 2026-11-25T08:42:54Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py", "scripts/model/dvp_league_2026.py", "scripts/model/dvp_league_2026_v2.py", "scripts/model/ffa_2026_inventory.py", "scripts/model/ffa_2026_pin.py", "scripts/model/dvp_simulate.py", "scripts/model/dvp_simulate_summary.py", "scripts/model/dvp_thresholds.py"]; output SHA-256=a8206929f371883d5b2bd94e4228612bfa996ab227f4f6ce3c8502f3ffbc8fc9
- `python-suite`: exit=0, 2026-11-25T08:44:01Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=86fef5b5ab8e37a3e4711cd63484df8d8b90d809b0a132c5e8ceeb1ee5cddec3

## Findings / decisions / contradictions

- 2026-11-25T07:29:10Z [correction] Scope extended by hand with scripts/model/dvp_simulate_summary.py (the suite's summarizer, split from the runner). — scripts/model/dvp_simulate_summary.py
- 2026-11-25T08:44:14Z [correction] A8's declared null makes B06 add noise, so its true league gain is slightly negative (league-truth.json); the declared two-sided false-positive check is reported as declared (FAIL in 3 of 4) beside a labelled one-sided supplementary check (PASS); the criterion itself was not changed. — docs/research/dvp/simulation-v1.json
- 2026-11-25T08:44:14Z [next_step] Phase E: extend arbit_model.feature_specs with a research eligibility registry (config/model/research-eligibility.json) covering D/ST B06, D/ST league-constrained utility, QB-K aggregate DvP with AUD-06/07 qualifications, K opportunity volume, other opportunity variants, and every legacy opp_dvp_* / opp_off_dst_* feature; a fail-closed check at model assembly; tests. — not yet verified

## Remaining unresolved / blocked

Deploy key (owner). Phase E, remediation 7, PB-AUD-08's audit rerun. A8 fails and A3 for WR is inconclusive (reported limitations, no defect).

## Next executable action

Merge the AUD-06/07 PR after CI. Then Phase E (eligibility registry) and remediation 7 (comprehensive audit). Owner: register the evidence deploy key before 2026-12-04 01:15 UTC.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
