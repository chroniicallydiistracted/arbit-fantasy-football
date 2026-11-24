# Task handoff — TASK-20261124-007 — M3-3 DvP audit remediations 3, 4 and 5: row contract and byte verification; decoupled historical stages; rolling-window and split-half-k exploratory estimators

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Owner audit AUD-04, AUD-05 and AUD-03. (4) Enforce the observation row contract (actual-only source types, observed rows, table-specific source id and scoring hash, finality rule, status-consistent points, availability after kickoff, orientation, unique keys) at fitting and forecasting, verify the bytes of every content-addressed store object the main pipeline reads, and add contamination fixtures with forbidden or unknown values inside permitted columns. (5) Run the historical seasons through separate stages: schedule targets, point-in-time features, forecast-only outputs persisted with hashes before any label is read, label retrieval, evaluation joins and invalid-label coverage reporting; extend the leakage tests. (3) Add rolling 3-, 5- and 8-game residual estimators with shrinkage and a training-only split-half-k estimator, compared with REML, grid-tuned, recency-weighted and prior estimators on common samples, as a versioned EXPLORATORY run that never changes the frozen candidates. No change to frozen files, production or weights.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/dvp/contract.py, libs/arbit-model/src/arbit_model/dvp/explore.py, libs/arbit-model/src/arbit_model/dvp/shadow.py, scripts/model/dvp_explore.py, scripts/model/dvp.py, scripts/model/dvp_prospective.py, config/dvp/explore-v2.json, libs/arbit-model/tests/test_dvp_contract.py, libs/arbit-model/tests/test_dvp_explore.py, libs/arbit-model/tests/test_dvp_shadow.py, libs/arbit-model/tests/test_dvp_firewall.py, docs/research/dvp/EXPLORATORY_V2.md, docs/research/dvp/explore-v2.json, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/research/dvp/METHODOLOGY.md, docs/project/status.md, docs/project/changelog.md, docs/project/decision-register.md, docs/governance/state.json, docs/project/handoffs/2026-11-24-task-20261124-007-governance-handoff.md, scripts/model/dvp_plan_audit.py, libs/arbit-model/tests/test_dvp_plan_audit.py

## Review

AUD-04: walkforward.prepare rejects unknown columns but trusts accepted rows' lineage values; dvp.py season_manifest/read_targets/_contribution_cells open content-addressed objects by digest name without hashing their bytes (load_index alone verified). AUD-05: walk's target universe is the valid observation rows (58 refused-label cells never forecast); persisted historical forecasts are written after the label join. AUD-03: B05 had exponential weights only; rolling windows existed only as lab diagnostics; B03 used REML k with no split-half-k comparison. The new contract passes on all 31,668 frozen observations and the 1,956 archived 2026 rows and catches planted values.

Files: libs/arbit-model/src/arbit_model/dvp/walkforward.py, scripts/model/dvp.py, libs/arbit-model/src/arbit_model/dvp/provenance.py, libs/arbit-model/src/arbit_model/dvp/reliability.py

## Plan

1) arbit_model.dvp.contract: row-level lineage contract, enforced by shadow.prepare_checked, the prospective harness and every observation read in dvp.py (reliability, backtest, sitstart, verify). 2) dvp.verified_object: hash every content-addressed manifest and Parquet before reading. 3) Contamination fixtures inside permitted columns (test_dvp_contract.py). 4) shadow.walk_targets gains an "extra" hook that may add columns but never alter frozen ones. 5) arbit_model.dvp.explore: rolling 3/5/8-game residuals and training-only split-half k, with a built-in check that its residual history reproduces the frozen B03. 6) scripts/model/dvp_explore.py: decoupled stages (schedule targets, contract-checked features, forecast-only outputs persisted with hashes before labels, separate label read, keep-every-target join, coverage) for development, validation and holdout; compares frozen variants with v1 receipts. 7) config/dvp/explore-v2.json declared before results. 8) Run, report EXPLORATORY_V2.md, records.

Files: libs/arbit-model/src/arbit_model/dvp/contract.py, libs/arbit-model/src/arbit_model/dvp/explore.py, scripts/model/dvp_explore.py, config/dvp/explore-v2.json

## Implement

contract.py (row contract; violations, enforce); shadow.prepare_checked and the walk_targets extra hook (refuses any hook that alters a frozen column); explore.py (rolling 3/5/8 windows, training-only split-half k, built-in B03 reproduction check); dvp.py verified_object in season_manifest, read_targets and _contribution_cells, and contract.enforce on all four observation reads; dvp_prospective.py uses prepare_checked and enforces the contract on built observations; dvp_explore.py forecast (labelsRead false, write-once, hashed manifest) and evaluate (hash check, separate label read, keep-every-target join, coverage, v1 reproduction, exploratory comparisons); config/dvp/explore-v2.json declared before results; SCANNED gains contract.py, explore.py and dvp_explore.py. Recorded run run-20261124-82f2711 at 82f2711: v1 reproduced on valid rows; receipt docs/research/dvp/explore-v2.json.

Files: libs/arbit-model/src/arbit_model/dvp/contract.py, libs/arbit-model/src/arbit_model/dvp/explore.py, libs/arbit-model/src/arbit_model/dvp/shadow.py, scripts/model/dvp.py, scripts/model/dvp_prospective.py, scripts/model/dvp_explore.py, config/dvp/explore-v2.json, docs/research/dvp/explore-v2.json, libs/arbit-model/tests/test_dvp_contract.py, libs/arbit-model/tests/test_dvp_explore.py

## Validate

All governance checks exit 0 on the final tree: foundation, model-tests (203 with ARBIT_DVP_AUDIT_RUN; 22 new), point-in-time, lint, format, types (mypy incl. dvp_explore.py), python-suite. Real data: the contract passes all 31,668 frozen observations and 1,956 archived 2026 rows and catches planted values; exploratory run run-20261124-82f2711 at 82f2711 reproduces every frozen variant's v1 metrics (incl. intervals) on valid rows in all stages and positions, with 7-9/1-2/2 refused-label cells per position now forecast and reported; full plan audit rerun after the changes PASSED (214 items, 156/156 checks) once A12's live vintage diagnostic is allowed to grow.

Files: docs/research/dvp/explore-v2.json, libs/arbit-model/tests/test_dvp_contract.py, libs/arbit-model/tests/test_dvp_explore.py

## Document

EXPLORATORY_V2.md (decoupled stages, coverage, reproduction, rolling-window and split-half-k results and findings, k by fold, comparison with the original results); SOURCE_PROVENANCE.md (what the firewall proves and doesn't; enforcement at use; contamination fixtures); METHODOLOGY.md (post-holdout work); EXPERIMENT_REGISTRY.md (V2 and prospective rows); README (status, commands, documents); ENG-064; status; changelog; state.json next action.

Files: docs/research/dvp/EXPLORATORY_V2.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/research/dvp/METHODOLOGY.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/README.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Recorded commands

- `foundation`: exit=0, 2026-11-24T23:31:38Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=f092f3d9d745dbaaaa6ae2a04b5274b7d447b43dfeab1791c7546e0ea19af8fc
- `model-tests`: exit=0, 2026-11-24T23:31:50Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=1753b699dadab7cd0c711d29e515b71ec8cc8b72698728c7d35fe0bab161f6a8
- `point-in-time`: exit=0, 2026-11-24T23:31:51Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=c9684ef5e056b4fb40903074c4d323abf0fb63082dbe5623ac0b641b054de736
- `lint`: exit=0, 2026-11-24T23:31:52Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-24T23:31:52Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=1e633b06d59a3ac6a0ab24fc77ebfe2f3f69fe19261c2ff06237975505ac6607
- `types`: exit=0, 2026-11-24T23:31:52Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py"]; output SHA-256=99176f10c3f02945fdb86f50950625e6a027ebd91833e51d6ba348c5f14257fb
- `python-suite`: exit=0, 2026-11-24T23:32:58Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=01b4a7c4649e9110f6617d340c1c6d88677869cd344dd7152b3c4301c5372bf0
- `foundation`: exit=0, 2026-11-24T23:36:16Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=f092f3d9d745dbaaaa6ae2a04b5274b7d447b43dfeab1791c7546e0ea19af8fc
- `model-tests`: exit=0, 2026-11-24T23:36:28Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=df8cfcc275b25b017d6102fe44e7a331ba4784bc61e8784f99ef536f8548993c
- `point-in-time`: exit=0, 2026-11-24T23:36:30Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=57f14a26b498c5e583adf8935855a4bec706ad1c61f829b5eeab8f7ac43285ea
- `lint`: exit=0, 2026-11-24T23:36:30Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-24T23:36:30Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=1e633b06d59a3ac6a0ab24fc77ebfe2f3f69fe19261c2ff06237975505ac6607
- `types`: exit=0, 2026-11-24T23:36:31Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py"]; output SHA-256=99176f10c3f02945fdb86f50950625e6a027ebd91833e51d6ba348c5f14257fb
- `python-suite`: exit=0, 2026-11-24T23:37:34Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=d5272420ecfbaf6998b8aba6d1b8ade0f1891dddf336042b3fc5a863dc4a485c

## Findings / decisions / contradictions

- 2026-11-24T23:29:20Z [correction] Amended plan: the word extra was lost to shell backtick substitution — previous_summary_sha256=725f96d0572813b4b43b6f85ff43c37f731559e74b4f6277552b65bef4a72289
- 2026-11-24T23:36:16Z [observation] Plan audit rerun after the AUD-04 changes: every stage reproduces its committed receipt except A12's live vintage diagnostic, which reads Arbit's growing 2026 capture history (158 games and 12 versions at the receipt, 162 and 13 now; same conclusion, one QB cell moved 0.04). The audit now allows /results/A12/vintages to differ, and its prospective check follows the AUD-01 procedure. Result: PASSED, 214 items, 156/156 checks. — scripts/model/dvp_plan_audit.py

## Remaining unresolved / blocked

Remediation 2 (opportunity/efficiency), remediation 6 (simulation suite, AUD-06), AUD-07 threshold wording, remediation 7 (audit rebuild) and eligibility metadata are open; the committed plan-audit receipt is from db0d802 and is regenerated by remediation 7; the prospective timer awaits owner approval.

## Next executable action

Merge the PR for TASK-20261124-007 (branch claude/m3-dvp-remediation-345). Owner decision pending on the prospective sweep timer (week 13 window 2026-12-01 12:00 to 12-04 01:15 UTC). Next: remediation 2 (A09/B07 opportunity and efficiency from nflverse stats_player/stats_team/pbp, admitted through the firewall), then remediation 7 (rebuilt plan audit with the new status vocabulary) and research eligibility metadata; AUD-06/AUD-07 as the owner directs.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
