# Task handoff — TASK-20261124-004 — M3-3 DvP plan completion: Phase C (D/ST Sit/Start), T26/T27, verify mode, idempotent reruns, missing deliverables

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Close every remaining action item of the owner's DvP specification v1.1 that can run now: Phase C (C00-C05) for D/ST, the only group with a credible group-level signal, with a predeclared rule and a prospective freeze before 2026 week 12; tests T26 and T27; a verify-only mode that reads artifacts back and reproduces receipts; idempotent reruns that never rewrite frozen files or evidence; METRICS.csv, calibration and error-by-season plots, the per-position conclusion table and a deliverables map; and accurate project records. No production, weight or canonical-table change.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/dvp/decisions.py, libs/arbit-model/tests/test_dvp_decisions.py, libs/arbit-model/tests/test_dvp_readback.py, libs/arbit-model/tests/test_dvp_firewall.py, scripts/model/dvp.py, config/dvp/sitstart.json, config/dvp/frozen-phase-c.json, docs/research/dvp/PLAYER_LEVEL_REPORT.md, docs/research/dvp/sitstart.json, docs/research/dvp/verify-receipt.json, docs/research/dvp/METRICS.csv, docs/research/dvp/plots/calibration.svg, docs/research/dvp/plots/error-by-season.svg, docs/research/dvp/plots/sitstart.svg, docs/research/dvp/README.md, docs/research/dvp/MODEL_CARD.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/experiment-registry.json, docs/research/dvp/BACKTEST_REPORT.md, docs/research/dvp/PROSPECTIVE_2026.md, docs/research/dvp/METHODOLOGY.md, docs/research/dvp/DATA_DICTIONARY.md, docs/research/dvp/DATA_QUALITY.md, docs/research/dvp/M3-3_CONTINUITY.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/project/status.md, docs/project/changelog.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/superpowers/plans/2026-11-09-m3-model.md, libs/arbit-model/README.md, docs/governance/state.json

## Review

Audited every action item of the owner's DvP specification v1.1 (sections 4-12) against the repository: test IDs T01-T40 by test function, experiment registry statuses, section 11 deliverables, CLI contracts, the frozen manifest. Found open: Phase 5 (C00-C05) PLANNED though D/ST was PROMISING (the section 5 gate is a credible group-level signal, not prospective confirmation); T26 and T27 had no tests; no verify-only mode; METRICS.csv, calibration and error-by-season plots and the section 11 per-position conclusions table missing; the project next action was stale (weather PR from 2026-11-22). Reproduction rerun on scratch copies: the 2025 holdout from the frozen commit 165d140 and development/validation from main give identical forecast content and results; found R-075 (a development rerun rewrote frozen-candidates metadata; forecast bytes are row-order dependent). Arbit has no player projection (the app says projections are not built) and FFA lineups exist only for 2026 periods 1-10 (read-only query).

Files: config/dvp/sitstart.json

## Plan

1) Declare Phase C first (config/dvp/sitstart.json): D/ST only by the gate; C00 = B00; pairwise start/sit accuracy of the frozen b06 vs b00 on every same-week pair; ties; close and waiver-pool subgroups; week-block bootstrap 2,000/1729; practical minimum 1.8 points derived from Phase B's 1% RMSE minimum and B00's development Spearman; rule PROMISING/INCONCLUSIVE/NOT_USEFUL/BLOCKED; commit and push before computing. 2) decisions.py (pure) and dvp.py sitstart on hash-checked frozen forecasts. 3) dvp.py verify (verify-only, T27). 4) Idempotent reruns (R-075). 5) T26/T27 tests and the T31 scan list. 6) Freeze Phase C for 2026 weeks 12-18 before 2026-11-26 01:00 UTC. 7) report: METRICS.csv, calibration, error-by-season, sitstart plots; registry. 8) Documents and records.

Files: config/dvp/sitstart.json

## Implement

decisions.py: units (D/ST forecast row -> the scoring D/ST, orientation checked against canonical observations, fails closed), pairs, metrics (accuracy, changed choices, points from changes, worst cases, within-week Spearman, top 8, subgroups, week-block bootstrap), decide. dvp.py: sitstart (checks frozen candidates and audit run, forecast hashes, projection-like columns, common rows); verify (v0 bytes, frozen commit vs manifest via git show, working-tree changes, audit outputs, every metric recomputed, label joins, D/ST whole points, relative bias, sign, sample, receipts verified); write_forecasts and content_sha256 (write once, refuse different content); development never rewrites frozen-candidates.json; report adds METRICS.csv and three plots; registry adds C00-C05 records; SCANNED adds decisions.py. config/dvp/frozen-phase-c.json frozen 2026-11-24T06:57:55Z. Results: Phase C PROMISING (+4.45/+8.55/+6.62 points); verify PASSED (468 metrics).

Files: libs/arbit-model/src/arbit_model/dvp/decisions.py, scripts/model/dvp.py, config/dvp/frozen-phase-c.json, docs/research/dvp/sitstart.json, docs/research/dvp/verify-receipt.json, docs/research/dvp/METRICS.csv, docs/research/dvp/experiment-registry.json, docs/research/dvp/plots/calibration.svg, docs/research/dvp/plots/error-by-season.svg, docs/research/dvp/plots/sitstart.svg, libs/arbit-model/tests/test_dvp_decisions.py, libs/arbit-model/tests/test_dvp_readback.py, libs/arbit-model/tests/test_dvp_firewall.py

## Validate

Checks at f3ceabf+receipt: foundation, model tests (157 with ARBIT_DVP_AUDIT_RUN; 155 + 2 skipped without, as CI), point-in-time, ruff check and format, mypy, full Python suite: all exit 0. dvp.py verify PASSED: 468 of 468 committed metrics recompute exactly; labels join 1:1 and equal observations; D/ST labels whole; relative bias under 15%; D/ST term sign positive (0.24, 0.35, 0.28); frozen commit matches all 11 frozen hashes; v0 byte-identical. Reproduction on scratch copies: 2025 holdout from 165d140, development and 2024 from main: keys, labels and missing cells identical; 18 (holdout) and 881 (development) float values differ by at most 7e-15 (parallel sums); results, selection, sensitivity and folds identical. R-075 fix shown on the real development stage: forecasts file and frozen-candidates hashes unchanged after a rerun. Phase C rerun from bac02af: receipt identical apart from code and time. Phase C rule committed (317361f, pushed 06:48 UTC) before results (bac02af).

Files: docs/research/dvp/verify-receipt.json, libs/arbit-model/tests/test_dvp_readback.py, libs/arbit-model/tests/test_dvp_decisions.py

## Document

PLAYER_LEVEL_REPORT.md (new); MODEL_CARD.md (Phase C, per-position conclusions table, integrity flags); README.md (status, sitstart/verify commands, idempotent reruns, frozen-commit rule, section 11 deliverables map); EXPERIMENT_REGISTRY.md and experiment-registry.json (C00-C05); BACKTEST_REPORT.md (Reproduction section with measured float differences, sample); PROSPECTIVE_2026.md (Phase C freeze, frozen-tree procedure); METHODOLOGY.md (Phase C declared); DATA_DICTIONARY.md, DATA_QUALITY.md, SOURCE_PROVENANCE.md, M3-3_CONTINUITY.md (inventory current); METRICS.csv and three plots. Project: ENG-062, R-075, changelog, status, state.json next action, M3 plan, libs/arbit-model/README.md.

Files: docs/research/dvp/PLAYER_LEVEL_REPORT.md, docs/research/dvp/MODEL_CARD.md, docs/research/dvp/README.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/changelog.md, docs/project/status.md

## Recorded commands

- `foundation`: exit=0, 2026-11-24T07:03:01Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=cfe2f6a671d53115016111df6555671814b3be24bdfd264adec13645cf2103e1
- `model-tests`: exit=0, 2026-11-24T07:03:09Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=87b6884e26806d9dd124a78d5fec5b54474d6b8cfaf9d6cb95203390181bcb82
- `point-in-time`: exit=0, 2026-11-24T07:03:10Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=9a343a29a27d896ad2d7aee7ada6fd510f0c969503ef161a58ca2cdda05f0c22
- `lint`: exit=0, 2026-11-24T07:03:11Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=e83204db783718300b1d1f1af1f60eb1a350f4140d5c653994fb67bc65273b1d
- `format`: exit=0, 2026-11-24T07:03:11Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=3c450d7ce666250994d6bf787bd7ab72d3aa5789fca8cfca1176f8c83d584e50
- `types`: exit=0, 2026-11-24T07:03:12Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py"]; output SHA-256=9fd069f93f3bc1e35050ef1a0ae1c544b98c5a371a3c6b457441f4ff72b4763e
- `python-suite`: exit=0, 2026-11-24T07:04:16Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=a34d382bffb58d346384580e118ffd0cf4a70622ab6a4661e095646a1bf6efdd
- `foundation`: exit=0, 2026-11-24T07:07:01Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=9a6b3064f1c7470cecc64b84e55726f2019e8511a8e9b645827f490fac8e5272
- `model-tests`: exit=0, 2026-11-24T07:07:09Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=268262b5aaa8fa9aff77aa2b1fa89ef6651f3ea296769ca3f64fd52eb6d4c19e
- `point-in-time`: exit=0, 2026-11-24T07:07:10Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=788e15571c51c044b5c93466f847283338f68d29b467ef2383bc7fe7a8d7ea0b
- `lint`: exit=0, 2026-11-24T07:07:10Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=e83204db783718300b1d1f1af1f60eb1a350f4140d5c653994fb67bc65273b1d
- `format`: exit=0, 2026-11-24T07:07:10Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=3c450d7ce666250994d6bf787bd7ab72d3aa5789fca8cfca1176f8c83d584e50
- `types`: exit=0, 2026-11-24T07:07:10Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py"]; output SHA-256=9fd069f93f3bc1e35050ef1a0ae1c544b98c5a371a3c6b457441f4ff72b4763e
- `python-suite`: exit=0, 2026-11-24T07:08:10Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=0ccbaa38a832f6274f45565b8eea25deeb6b1e47210e0eca2f7c28bca1b110e2

## Findings / decisions / contradictions

- 2026-11-24T07:08:26Z [correction] My previous report treated Phase C as waiting on the prospective 2026 confirmation; the specification's gate (section 5) is a credible group-level signal, which D/ST had. Phase C has now run. I also first wrote that rerun forecasts were identical; measured, up to 881 values differ by at most 7e-15 (parallel sums). Documents state the measured difference. — docs/research/dvp/BACKTEST_REPORT.md
- 2026-11-24T07:08:26Z [observation] Phase C D/ST: pairwise start/sit accuracy B06 vs B00 +4.45 (dev), +8.55 (2024), +6.62 (2025) points, minimum 1.8 declared first: PROMISING. Points per changed choice +1.6 to +2.7; worst single choice -40. — docs/research/dvp/sitstart.json
- 2026-11-24T07:08:26Z [question] Owner decision after the prospective 2026 window (both levels): whether the D/ST opponent term (B06) may enter the Sit/Start model as a weighted contribution (OWN-074). — docs/research/dvp/MODEL_CARD.md
- 2026-11-24T07:08:26Z [risk] The prospective 2026 scoring must run the frozen method from the freeze commit's tree (165d140); dvp.py on main differs from the frozen hash by design. The prospective harness must be a new file that calls the frozen library unchanged. — docs/research/dvp/PROSPECTIVE_2026.md

## Remaining unresolved / blocked

Prospective 2026 scoring (after the season); owner decision on a D/ST production weight (OWN-074); league-constrained lineup evaluation blocked for 2016-2025 (no FFA lineup history); feature_specs keeps v0's DvP constants until the owner decides.

## Next executable action

Merge the DvP plan-completion PR (claude/m3-dvp-completion). Every action item of the DvP specification is then done except the prospective 2026 weeks 12-18 scoring at both levels, which waits on the regular season (PROSPECTIVE_2026.md). Meanwhile: M3 slices 3c-3e and weather W1; NWS User-Agent contact from the owner before W3.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
