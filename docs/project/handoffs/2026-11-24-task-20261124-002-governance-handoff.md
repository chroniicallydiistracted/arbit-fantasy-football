# Task handoff — TASK-20261124-002 — M3-3 DvP Phase 3: walk-forward engine, B00-B12 on development folds and 2024 validation

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Phase 3 of the owner's DvP specification (OWN-074): a preweek walk-forward over completed-game FFA actuals. B00 (offense-only, as declared in METHODOLOGY.md: own prior regressed by a training-only slope, in-season shrinkage with training-only k) and DvP variants B01-B07 (raw, point-in-time residual unshrunk and shrunk, recomputed-baseline residual, prediction-tuned k on a declared grid, recency-weighted, dynamic with last-season prior, non-touchdown components), diagnostics B08, negative controls B09, per-game cutoff B10, projection-contamination resistance B11 and availability-rule sensitivity B12. Rolling-origin development folds 2017-2023, tuning on development only, then 2024 validation with the practical minimum fixed from development data before validation runs. Forecasts frozen before labels join (evaluation_join). Leakage tests T15-T20, T22, T24, T25. 2025 is not touched (Phase 4 needs a frozen manifest). Research only: no weight, service or production change.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/dvp/walkforward.py, libs/arbit-model/tests/test_dvp_walkforward.py, scripts/model/dvp.py, config/dvp/backtest.json, config/dvp/frozen-candidates.json, docs/research/dvp/BACKTEST_REPORT.md, docs/research/dvp/backtest-development.json, docs/research/dvp/backtest-validation.json, docs/research/dvp/METHODOLOGY.md, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/experiment-registry.json, docs/research/dvp/DATA_DICTIONARY.md, docs/research/dvp/plots/backtest-delta.svg, docs/project/status.md, docs/project/changelog.md, docs/project/decision-register.md, docs/superpowers/plans/2026-11-09-m3-model.md, libs/arbit-model/README.md, docs/governance/state.json

## Review

Read the specification's Phase B (B00-B12), sections 6-7 and 9 (forecast estimator, point-in-time vs recomputed baselines, common eligible rows, paired deltas with block bootstrap, practical minimum from development data only, decision labels, Phase 3 gate), the as-of layer (cutoffs, features_as_of, FrozenForecasts, evaluation_join, league_prior), Phase 2's lab and METHODOLOGY.md where B00 and the metrics were declared, and the reliability results that motivate the variants (D/ST k about 7-9, QB drift, RB rushing yards, touchdowns noise, carryover slopes).

Files: docs/research/dvp/METHODOLOGY.md, docs/research/dvp/README.md, scripts/model/dvp.py

## Plan

walkforward.py: fold parameters fit on training seasons only (own k by REML, prior slope by carryover, DvP k and slope from training residuals), a preweek or per-game loop over cutoffs using features_as_of, B00 and variants computed per target row from rows available by the cutoff, point-in-time residuals from earlier B00 forecasts, recomputed-baseline residuals, recency weights, last-season priors, non-touchdown components; forecasts frozen and joined to labels only through evaluation_join; metrics per position on common rows (RMSE, MAE, bias, Spearman, calibration deciles, paired delta with block bootstrap, by season and week bins). dvp.py backtest --stage development|validation: development folds 2017-2023 and tuning, then validation 2024 from a candidates file fixed after development; refuses 2025. Tests T15-T20, T22, T24, T25 on synthetic seasons. BACKTEST_REPORT.md and registry records.

Files: libs/arbit-model/src/arbit_model/dvp/walkforward.py, libs/arbit-model/tests/test_dvp_walkforward.py, scripts/model/dvp.py, config/dvp/backtest.json, config/dvp/frozen-candidates.json

## Implement

walkforward.py: prepare (fails closed on unknown columns), fit_fold (training-only own k, prior slope, DvP k and slope, non-TD k), walk (preweek/per-game cutoffs via features_as_of; B00; point-in-time residual store; recomputed baselines; recency weights; last-season prior; non-TD residuals; B09 controls; frozen forecasts), evaluate (evaluation_join), metrics with block-bootstrap deltas, calibration, breakdowns, check_stage (refuses holdout). dvp.py backtest (development with selection and frozen candidates, validation from candidates, B10 and B12 sensitivity), report (plot from receipts), Phase B registry records; walkforward.py added to the code scan. Runs: development 2017-2023 (code d811711), candidates frozen (3a920c2), validation 2024 (3a920c2), report and registry.

Files: libs/arbit-model/src/arbit_model/dvp/walkforward.py, libs/arbit-model/tests/test_dvp_walkforward.py, scripts/model/dvp.py, config/dvp/backtest.json, config/dvp/frozen-candidates.json

## Validate

Checks: foundation, model tests (123), point-in-time, ruff check and format, mypy, the full Python suite (default threads, as CI): all exit 0. Leakage on synthetic seasons: future and own results never change a forecast (T16, T17); Thursday results reach Sunday only under per-game cutoffs (T15); fold parameters unchanged by later seasons and the holdout refused (T18); every variant covers the same rows and labels join only through evaluation_join (T19, T20); a real defense effect helps, pure noise and placebos don't (T21, T22, T24); week 1 is the prior with nothing missing (T25); planted projections fail closed (B11); forecasts reproducible (T13). Real data: development and validation receipts; placebo controls show no meaningful uplift; candidates frozen (sha 2b2ce424) before validation, recorded in the validation receipt. Report claims checked against receipts and corrected where the draft overstated (unshrunk D/ST, recency, non-TD, controls, B12 attribution).

Files: libs/arbit-model/tests/test_dvp_walkforward.py, docs/research/dvp/backtest-development.json, docs/research/dvp/backtest-validation.json, config/dvp/frozen-candidates.json

## Document

BACKTEST_REPORT.md (setup, comparator, development and validation tables, variants, controls, diagnostics, sensitivity, gate status, direction); METHODOLOGY.md (practical minimum and candidate freezing recorded), runbook, EXPERIMENT_REGISTRY.md, DATA_DICTIONARY.md, plot; decision register ENG-060; status, changelog, M3 plan, libs/arbit-model README.

Files: docs/research/dvp/BACKTEST_REPORT.md, docs/research/dvp/METHODOLOGY.md, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/DATA_DICTIONARY.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/superpowers/plans/2026-11-09-m3-model.md, libs/arbit-model/README.md

## Recorded commands

- `foundation`: exit=0, 2026-11-24T03:10:00Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=967aee99b494ae8cfc46eeb4d120a08545e3579edfd26acc50a13c9ddf4c45ae
- `model-tests`: exit=0, 2026-11-24T03:10:49Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=fcc2c3926b317d582132d348ac93a189f11eff6e4f11fe7a8fd1535dd57b6b44
- `point-in-time`: exit=0, 2026-11-24T03:10:51Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=e2f08e7615aa1507340dcf4e2e45fb5d751f669a7d377c72dd63ea1f8f681efa
- `lint`: exit=0, 2026-11-24T03:10:51Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=e83204db783718300b1d1f1af1f60eb1a350f4140d5c653994fb67bc65273b1d
- `format`: exit=0, 2026-11-24T03:10:51Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=1b1cee5ee82fdde072764580fe64fa8a6ebbc86621afb47e2edab178da1ca138
- `types`: exit=0, 2026-11-24T03:10:52Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py"]; output SHA-256=bfe68eeda4b395a659102ac01a1d7cc8c48c5a2ea08ac09714f9ce1731a87089
- `python-suite`: exit=0, 2026-11-24T03:12:36Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=a989845e70185a69f92a9320ef0101bd2757b5396fd9f6ea2dd76e69f920416c

## Findings / decisions / contradictions

- 2026-11-24T03:12:50Z [observation] D/ST is the one group where the opponent term earns a place: B06 cuts next-game RMSE 3.0% in development (every season) and 6.4% in 2024. Positions gain under 1% and did not replicate (WR worse in 2024). Unshrunk DvP is 4-13% worse. — docs/research/dvp/BACKTEST_REPORT.md
- 2026-11-24T03:12:50Z [risk] The walk-forward is slow under polars' default thread pool on small frames (tests about 40 s vs 4 s with POLARS_MAX_THREADS=2). Receipts record the thread setting; results were produced with 2 threads. — docs/research/dvp/backtest-development.json
- 2026-11-24T03:12:50Z [decision_proposed] Phase 4 should evaluate only the frozen candidates (D/ST B06; B00 elsewhere) on 2025 as CONDITIONALLY_HELD_OUT, then freeze a prospective 2026 shadow test. Any production use of D/ST B06 needs the owner's approval (OWN-074). — config/dvp/frozen-candidates.json

## Remaining unresolved / blocked

No weight changes: feature_specs DvP constants remain v0's until the owner approves a Phase 4 outcome. Phase C (player-level Sit/Start) only for D/ST, if Phase 4 confirms. NWS User-Agent contact still needed before weather W3.

## Next executable action

Merge the DvP Phase 3 PR (branch claude/m3-dvp-phase3). Then Phase 4: run the frozen candidates (config/dvp/frozen-candidates.json) on 2025 as a conditional holdout with a frozen manifest, label each position PROMISING/INCONCLUSIVE/NOT_USEFUL/BLOCKED, write the model card, and freeze a prospective 2026 shadow test.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
