# Task handoff — TASK-20261124-001 — M3-3 DvP Phase 2: reliability lab (A00, A02-A10, A12) on the repaired FFA targets

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Run the specification's Phase A on the validated, R-072-repaired completed-game observations (OWN-074): A00 landscape and raw vs adjusted ranks; A02 split-method sensitivity including 1,000 seeded random balanced splits; A03 opponent-adjustment variants; A04 position stability by era and half size with joint season-bootstrap orderings; A05 variance components (method of moments and REML with unequal game counts, boundary and convergence reported); A06 temporal stability (first vs second half, lag decay, rolling windows); A07 between-season carryover; A08 within-week permutation nulls and cluster-bootstrap comparisons; A09 FFA-component decomposition from the scorer's rule contributions; A10 era, season-exclusion, trimming and influence robustness; A12 refused-line and stat-correction sensitivity. Tables, SVG plots, intervals, RELIABILITY_REPORT and METHODOLOGY; tests T12-T14, T23, T24, T28. Descriptive only: no forecast, no weight change, no production write.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/dvp/lab.py, libs/arbit-model/src/arbit_model/dvp/svg.py, libs/arbit-model/src/arbit_model/dvp/provenance.py, libs/arbit-model/tests/test_dvp_lab.py, libs/arbit-model/tests/test_dvp_firewall.py, scripts/model/dvp.py, config/dvp/reliability.json, docs/research/dvp/RELIABILITY_REPORT.md, docs/research/dvp/METHODOLOGY.md, docs/research/dvp/reliability-results.json, docs/research/dvp/plots/split-scatter-QB.svg, docs/research/dvp/plots/split-scatter-RB.svg, docs/research/dvp/plots/split-scatter-WR.svg, docs/research/dvp/plots/split-scatter-TE.svg, docs/research/dvp/plots/split-scatter-K.svg, docs/research/dvp/plots/split-scatter-DST.svg, docs/research/dvp/plots/k-forest.svg, docs/research/dvp/plots/weight-curves.svg, docs/research/dvp/plots/lag-decay.svg, docs/research/dvp/plots/null-distributions.svg, docs/research/dvp/plots/carryover.svg, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/experiment-registry.json, docs/research/dvp/DATA_DICTIONARY.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/research/dvp/PROJECTION_EXCLUSION_AUDIT.json, docs/research/dvp/audit-receipt.json, docs/research/dvp/SCORE_FINALITY_AUDIT.json, docs/research/dvp/continuity-manifest.json, docs/research/dvp/DATA_QUALITY.md, docs/research/dvp/V0_REPRODUCTION.md, docs/research/dvp/v0-reproduction.json, docs/project/status.md, docs/project/changelog.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/superpowers/plans/2026-11-09-m3-model.md, libs/arbit-model/README.md, docs/governance/state.json

## Review

Read the specification's Phase A (A00-A12), sections 6-9 and 11 (estimators, unequal halves, clustered resampling, multiple comparisons, required reports and plots, tests T12-T14, T21-T24, T28), the phase 1 code (observations, reliability, provenance, dvp.py) and receipts. Inputs: the audit run phase1-audit-20261124T021910Z observations on repaired index 6ffb62fb (31,668 cells, 31,610 valid) and its schedule. matplotlib and scipy are absent; plots will be deterministic SVG written by the lab, and estimators use numpy (installed). The athlete and D/ST target tables carry per-rule contributions, which allow the FFA-component decomposition (A09) without a new data family; true opportunity counts would need a new realized-statistics source and are left to Phase B/C.

Files: docs/research/dvp/V0_REPRODUCTION.md, docs/research/dvp/DATA_DICTIONARY.md, libs/arbit-model/src/arbit_model/dvp/provenance.py, scripts/model/dvp.py

## Plan

lab.py: position frames (entity = defense, or offense for D/ST; faced = the other side); adjustments none/season/loo_mean/loo_median/loo_shrunk; split assignments calendar/alternating/chronological/first6_next6/home_away/random (numpy, seeded); method-of-moments and REML one-way components with unequal sizes, boundary and convergence; lag-binned ICC; rolling-window correlations with model-implied values; carryover with slope and leave-one-pair-out CV; within-week permutation nulls; season, unit and franchise cluster bootstraps; jackknife influence. svg.py: deterministic plots. provenance: a contributions source spec for A09. dvp.py reliability subcommand writing reliability-results.json, plots and run artifacts; registry records for A00-A10, A12. Tests T12-T14, T23, T24, T28 plus determinism. Then RELIABILITY_REPORT.md and METHODOLOGY.md written from the results.

Files: libs/arbit-model/src/arbit_model/dvp/lab.py, libs/arbit-model/src/arbit_model/dvp/svg.py, libs/arbit-model/src/arbit_model/dvp/provenance.py, scripts/model/dvp.py, config/dvp/reliability.json, libs/arbit-model/tests/test_dvp_lab.py

## Implement

lab.py (adjustments, six split methods and seeded random splits, MoM and REML variance components with boundary/non-convergence flags, season component, implied split r, lag profile with season bootstrap, rolling windows with model-implied values, carryover with leave-one-season-out CV, within-week permutation null, cluster bootstraps, joint orderings, influence, winsorize/trim, landscape, rank agreement); svg.py (deterministic scatter, forest, lines, histograms); provenance (FFA_ACTUAL_AS_OF type; contribution and gamebook sources); dvp.py reliability (all Phase A experiments, Holm, A09 contributions, A12 refusal and 2026 vintage check, plots) and registry records for executed Phase A; code_version ignores receipt changes; order-independent rank agreement. Runs: audit phase1-audit-20261124T024442Z (all PASSED), v0 rerun exact, reliability (code 3a1fe11) identical across two runs, registry 33 experiments.

Files: libs/arbit-model/src/arbit_model/dvp/lab.py, libs/arbit-model/src/arbit_model/dvp/svg.py, libs/arbit-model/src/arbit_model/dvp/provenance.py, scripts/model/dvp.py, config/dvp/reliability.json, libs/arbit-model/tests/test_dvp_lab.py, libs/arbit-model/tests/test_dvp_firewall.py

## Validate

Checks: foundation, model tests (113), point-in-time, ruff check and format, mypy, the full Python suite: all exit 0. Determinism: two reliability runs on the same audit run gave identical results and byte-identical plots (T13). Phase 1 reproduction holds: odd/even adjusted r and k match v0-validated exactly (QB 0.2706/22.23 ... DST 0.4853/8.74); v0 rerun exact. Synthetic tests with known answers: REML recovers k=9 with unequal season lengths (T12); equal group means and pure noise give boundary or k>50, a grid-edge maximum is flagged unconverged (T14); a mid-season trait shift is caught by halves and lags, not odd/even (T23); permutation nulls reject only real signal and center as derived (T24); the planted extreme unit-season is found by influence (T28). A09 components sum back to each cell exactly (max difference 0). Report figures spot-checked against the receipt (claims corrected where the first draft overstated: MoM agreement, boundary share, noise SD, spread ratio, offense-vs-defense ratio).

Files: libs/arbit-model/tests/test_dvp_lab.py, libs/arbit-model/tests/test_dvp_firewall.py, docs/research/dvp/reliability-results.json, docs/research/dvp/audit-receipt.json, docs/research/dvp/v0-reproduction.json

## Document

RELIABILITY_REPORT.md (conclusions by position and every experiment's table), METHODOLOGY.md (hypotheses, estimators, look-ahead protections, Phase B comparator and metrics declared before it runs), README, EXPERIMENT_REGISTRY.md, DATA_DICTIONARY.md, SOURCE_PROVENANCE.md (new sources; current index corrected to 6ffb62fb), plots; decision register ENG-059; status, changelog, M3 plan, libs/arbit-model README.

Files: docs/research/dvp/RELIABILITY_REPORT.md, docs/research/dvp/METHODOLOGY.md, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/DATA_DICTIONARY.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/superpowers/plans/2026-11-09-m3-model.md, libs/arbit-model/README.md

## Recorded commands

- `foundation`: exit=0, 2026-11-24T02:52:06Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=894488ae9ff25ca120b2f7f577d4fbecac375bbb13c66d9b76263c55466e8542
- `model-tests`: exit=0, 2026-11-24T02:52:18Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=4df923268ed21892e4ffdf0f76c84d8923f5aea63866131b296fb09d8b4110e0
- `point-in-time`: exit=0, 2026-11-24T02:52:20Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=370367a1c65273488edd93634feecf4951520a0b35476f37fad3ecf0525c17c6
- `lint`: exit=0, 2026-11-24T02:52:20Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=e83204db783718300b1d1f1af1f60eb1a350f4140d5c653994fb67bc65273b1d
- `format`: exit=0, 2026-11-24T02:52:20Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=e030c765b9e4b75270fcda60043cf01b6c8e191f3d3d12613a5efcb373a7d975
- `types`: exit=0, 2026-11-24T02:52:21Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py"]; output SHA-256=0c91bcb0d6295e69dd55cd261656064cfd8a5f08970f42cb7983688f15673daa
- `python-suite`: exit=0, 2026-11-24T02:53:29Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=6dd8f468fc88bea04029c3bd22bcac44fe5b1db384315f12991c03c8c4e5b64f

## Findings / decisions / contradictions

- 2026-11-24T02:53:45Z [observation] v0's WR k of 44 came from an unlucky odd/even partition (2.5th percentile of 1,000 random splits); REML with each unit's game count gives 26.7 (17.8-58.3). Raw WR repeatability is mostly season-wide scoring (permutation p 0.077); the adjusted measure is the meaningful one. — docs/research/dvp/RELIABILITY_REPORT.md
- 2026-11-24T02:53:45Z [risk] A12's 2026 stat-correction check is a lower bound: Arbit's nflverse vintages start 2026-10-31 and miss 2026-11-10 to 11-22, so only week 9 was observed fresh. Seasons 2016-2025 hold final revisions only. — docs/research/dvp/reliability-results.json
- 2026-11-24T02:53:45Z [next_step] Phase 3: walk-forward with the preweek cutoff; B00 as declared in METHODOLOGY.md (own prior regressed by a training-only slope, in-season shrinkage with training-only k); variants B01-B08 with emphasis on D/ST offense-allowed (k 7-9), QB recency (B05), RB rushing yards (B07); controls B09; T15-T25 leakage tests. — docs/research/dvp/METHODOLOGY.md

## Remaining unresolved / blocked

feature_specs dvp_* constants remain v0's until Phase B decides (OWN-074); Phase 2 suggests WR's should be about 27, not 44, but no weight changes without Phase B. A12 correction evidence is a lower bound (vintage coverage). True opportunity counts need a realized-statistics source admitted to the DvP firewall (A09 uses receptions). NWS User-Agent contact still needed before weather W3.

## Next executable action

Merge the DvP Phase 2 PR (branch claude/m3-dvp-phase2), then Phase 3: the walk-forward engine (preweek cutoff, B00 as declared in docs/research/dvp/METHODOLOGY.md, B01-B12, leakage tests T15-T25), development folds 2017-2023 and 2024 validation.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
