# Task handoff — TASK-20261124-003 — M3-3 DvP Phase 4: frozen manifest, 2025 conditional holdout, decisions, model card, prospective 2026 freeze

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Phase 4 of the owner's DvP specification (OWN-074). Freeze the Phase 3 method in a manifest (code and config hashes, frozen candidates, audit run, evaluation protocol and predeclared decision rules) before 2025 is forecast; a holdout stage that refuses to run unless every frozen hash matches; evaluate the frozen candidates (D/ST B06, B00 elsewhere, plus each position's best DvP for information) on 2025 as CONDITIONALLY_HELD_OUT with parameters fit through 2024; label each position and the whole PROMISING, INCONCLUSIVE, NOT_USEFUL or BLOCKED by the predeclared rule; write MODEL_CARD.md and a prospective 2026 freeze for confirmation on games completed after it. Research only: no weight, service or production change; any production use needs the owner.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/dvp/walkforward.py, libs/arbit-model/tests/test_dvp_walkforward.py, scripts/model/dvp.py, config/dvp/frozen.json, config/dvp/backtest.json, docs/research/dvp/backtest-holdout.json, docs/research/dvp/MODEL_CARD.md, docs/research/dvp/PROSPECTIVE_2026.md, docs/research/dvp/BACKTEST_REPORT.md, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/experiment-registry.json, docs/research/dvp/DATA_DICTIONARY.md, docs/research/dvp/plots/backtest-delta.svg, docs/project/status.md, docs/project/changelog.md, docs/project/decision-register.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/governance/state.json

## Review

Read the specification's Phase 4 (frozen manifest, CONDITIONALLY_HELD_OUT labeling, prospective confirmation, decision labels per position and globally) and section 12, the Phase 3 receipts and frozen candidates, and the stage guard. 2025 exposure: descriptive only (v0 and Phase A used 2016-2025 for repeatability); no 2025 forecast, outcome or parameter entered model selection, which used development folds 2017-2023 and was confirmed on 2024.

Files: config/dvp/backtest.json, scripts/model/dvp.py, libs/arbit-model/src/arbit_model/dvp/walkforward.py

## Plan

1) dvp.py freeze writes config/dvp/frozen.json: SHA-256 of the method files (walkforward.py, lab.py, asof.py, observations.py, dvp.py, base/backtest configs, frozen candidates), the audit run's output hashes and targets index, the protocol (RMSE, week-block bootstrap, seed, practical minimum) and the decision rule, plus the prospective 2026 window. 2) backtest --stage holdout runs only when every frozen hash matches the files on disk; parameters fit on 2016-2024; candidates evaluated on 2025; decisions by the predeclared rule (PROMISING if the candidate is a DvP variant meeting the minimum in development, validation and holdout; NOT_USEFUL if the best DvP misses the minimum in all three; INCONCLUSIVE otherwise; BLOCKED on any integrity failure). 3) Tests for the holdout guard. 4) MODEL_CARD.md, PROSPECTIVE_2026.md, registry decisions, records.

Files: scripts/model/dvp.py, config/dvp/frozen.json, libs/arbit-model/src/arbit_model/dvp/walkforward.py, libs/arbit-model/tests/test_dvp_walkforward.py

## Implement

walkforward: check_stage admits the holdout only as a verified holdout stage; decide() applies the predeclared rule. dvp.py: freeze (method and config hashes, audit outputs, targets index, protocol, decision rule, periods, prospective window from the schedule; refuses uncommitted code and mismatched candidates); backtest --stage holdout (verifies every frozen hash first, coverage check, decisions per position and overall); registry record M3-3-HOLDOUT-2025; report plot with all three periods. Runs: freeze at f75868b (2026-11-24 03:16 UTC, prospective 2026 weeks 12-18), holdout at 165d140 (all hashes verified), report and registry afterwards (dvp.py changed only in registry and plot order after the holdout).

Files: libs/arbit-model/src/arbit_model/dvp/walkforward.py, libs/arbit-model/tests/test_dvp_walkforward.py, scripts/model/dvp.py, config/dvp/frozen.json, config/dvp/backtest.json

## Validate

Checks: foundation, model tests (125), point-in-time, ruff check and format, mypy, the full Python suite: all exit 0. Holdout guard tests: holdout refused without a verified manifest and outside the holdout stage (T18); decision rule unit-tested for every label. The holdout receipt records the frozen manifest hash (1ef59583) and code 165d140; every frozen hash was verified before forecasting; coverage complete (3,256 forecasts = every valid 2025 cell). Freeze cross-checked the candidates against the development receipt and the validation receipt's candidates hash. Model card and report numbers checked against the receipt (one overstatement about unshrunk D/ST corrected).

Files: libs/arbit-model/tests/test_dvp_walkforward.py, docs/research/dvp/backtest-holdout.json, config/dvp/frozen.json

## Document

MODEL_CARD.md, PROSPECTIVE_2026.md, BACKTEST_REPORT.md (Phase 4 section), README, EXPERIMENT_REGISTRY.md, DATA_DICTIONARY.md, backtest plot; decision register ENG-061; status, changelog, M3 plan.

Files: docs/research/dvp/MODEL_CARD.md, docs/research/dvp/PROSPECTIVE_2026.md, docs/research/dvp/BACKTEST_REPORT.md, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/DATA_DICTIONARY.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/superpowers/plans/2026-11-09-m3-model.md

## Recorded commands

- `foundation`: exit=0, 2026-11-24T03:18:47Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=56a3a2e481f4fc5ede809b4fe9c4bc8e5a3974114c415aa9efdd149a57b4ba0b
- `model-tests`: exit=0, 2026-11-24T03:19:38Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=67757b3cb1c026cad85974573c1b93e38f8a35131bbb055739a93f26c1067b6f
- `point-in-time`: exit=0, 2026-11-24T03:19:40Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=1aed7ba9461f6031dc638c64f5d433d6a8ba71caa1d00b11698780fafd5a7f86
- `lint`: exit=0, 2026-11-24T03:19:40Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=e83204db783718300b1d1f1af1f60eb1a350f4140d5c653994fb67bc65273b1d
- `format`: exit=0, 2026-11-24T03:19:40Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=1b1cee5ee82fdde072764580fe64fa8a6ebbc86621afb47e2edab178da1ca138
- `types`: exit=0, 2026-11-24T03:19:41Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py"]; output SHA-256=bfe68eeda4b395a659102ac01a1d7cc8c48c5a2ea08ac09714f9ce1731a87089
- `python-suite`: exit=0, 2026-11-24T03:21:27Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=07b69af150eab65c8b8a90997255e902f92f741627048a9af59355a49e343c77

## Findings / decisions / contradictions

- 2026-11-24T03:21:39Z [observation] 2025 conditional holdout: D/ST B06 -4.1% RMSE (interval excludes 0) -> PROMISING; QB best DvP -1.1% only in 2025 -> INCONCLUSIVE; RB, WR, TE, K NOT_USEFUL. A 2025 noise placebo improved TE by 0.65%: sub-1% changes arise by chance. — docs/research/dvp/backtest-holdout.json
- 2026-11-24T03:21:40Z [correction] scripts/model/dvp.py changed after the holdout run (registry record and plot ordering only), so its hash no longer matches config/dvp/frozen.json; the holdout ran at 165d140 with every hash verified, and a re-run or the prospective scoring must use the frozen commit (f75868b) for the method files. — config/dvp/frozen.json
- 2026-11-24T03:21:40Z [question] Owner decision after the prospective 2026 window: whether a D/ST opponent term (B06, k about 8, last-season prior) may enter the Sit/Start model as a weighted contribution (OWN-074 requires approval). — docs/research/dvp/MODEL_CARD.md

## Remaining unresolved / blocked

Production use of the D/ST term needs the owner's approval after prospective confirmation. feature_specs DvP constants are still v0's. NWS User-Agent contact still needed before weather W3.

## Next executable action

Merge PR #10 (Phase 3) and this Phase 4 PR (branch claude/m3-dvp-phase4). DvP research then waits for the 2026 regular season to end: rebuild targets with 2026, add a prospective stage that verifies the frozen method hashes against the new targets, score 2026 weeks 12-18 (PROSPECTIVE_2026.md). Meanwhile resume M3 slices 3c-3e and weather W1.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
