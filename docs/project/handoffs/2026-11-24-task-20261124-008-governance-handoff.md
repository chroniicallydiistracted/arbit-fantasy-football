# Task handoff — TASK-20261124-008 — M3-3 DvP audit remediation 2: opportunity volume and scoring efficiency (A09, B07 extensions)

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Owner audit AUD-02. Admit nflverse player and team statistics (the exact files the FFA targets were built from) through a versioned admission with the firewall's rules and field catalog; build per team-game-position opportunity volume (QB dropbacks and carries, RB carries and targets, WR/TE targets, K FG and PAT attempts, D/ST opponent plays) with receptions and D/ST sack and turnover counts; reconcile player volumes with team totals and points with volumes; report coverage, true zeros, missing and invalid cells; measure volume and efficiency allowed reliability separately (REML k, season-cluster intervals) and their duplication; add actual-history-only forward predictors (volume channel, efficiency channel, both) through the exploratory hook, compared with B00, B03, B06 and the retained non-touchdown B07 on common rows; all EXPLORATORY, declared in config before results, never changing frozen candidates.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/dvp/opportunity.py, libs/arbit-model/src/arbit_model/dvp/explore.py, scripts/model/dvp_explore.py, scripts/model/dvp.py, config/dvp/explore-v3.json, libs/arbit-model/tests/test_dvp_opportunity.py, docs/research/dvp/OPPORTUNITY_EFFICIENCY.md, docs/research/dvp/explore-v3.json, docs/research/dvp/README.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/research/dvp/METHODOLOGY.md, docs/project/status.md, docs/project/changelog.md, docs/project/decision-register.md, docs/governance/state.json, docs/project/handoffs/2026-11-24-task-20261124-008-governance-handoff.md

## Review

AUD-02: A09 split points by scoring rule only; B07 used non-touchdown points; true volume was called unavailable. Arbit already holds it: gamebook.OPPORTUNITY_COLUMNS (attempts, carries, targets, fg_att, pat_att), team_features opps_pg, feature_specs opp_dvp_<pos>_opps_pg. nflverse stats_player and stats_team carry every needed count with no nulls in 2016-2025, and the field catalog classifies them as history (generic fantasy points excluded). The frozen provenance allowlist has no stats source and provenance.py is frozen, so a versioned admission with the same rules is needed. Each season's FFA targets manifest pins the exact stats files used.

Files: libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/team_features.py, libs/arbit-model/src/arbit_model/feature_specs.py, libs/arbit-model/src/arbit_model/fields.py, libs/arbit-model/src/arbit_model/dvp/provenance.py

## Plan

1) arbit_model.dvp.opportunity: versioned admission (admit_realized) with the firewall's rules; volume per cell (QB dropbacks + carries, RB carries + targets, WR/TE targets, K FG + PAT attempts, D/ST the offense's plays) with components; cells with missing/zero/ok status and ratio efficiency; reconciliation of player sums with team statistics; coverage; REML reliability of points, volume and efficiency allowed with season-cluster intervals and their correlation. 2) explore.make_opportunity_extra: volume channel b07v, efficiency channel b07e, both b07ve, training-only k, ratio-of-sums efficiency with a league pseudo-volume prior; explore.compose. 3) dvp_explore.py: --config version, opportunity command, composed hooks, B07 comparison and term correlations. 4) config/dvp/explore-v3.json declared before results. 5) Tests. 6) Recorded run, OPPORTUNITY_EFFICIENCY.md, records.

Files: libs/arbit-model/src/arbit_model/dvp/opportunity.py, libs/arbit-model/src/arbit_model/dvp/explore.py, scripts/model/dvp_explore.py, config/dvp/explore-v3.json, libs/arbit-model/tests/test_dvp_opportunity.py

## Implement

opportunity.py (SOURCES_V2, admit_realized, player_volumes, dst_volumes, cells with missing/zero/ok status and ratio efficiency, reconcile, coverage, unit_frame, reliability); explore.py (opportunity_parameters with training-only REML k, make_opportunity_extra for b07v/b07e/b07ve, compose); dvp_explore.py (--config version, opportunity command reading the pinned stats manifests with bytes re-hashed, composed hooks, B07 comparison, term correlations, opportunity summary in the receipt); config/dvp/explore-v3.json declared first; SCANNED gains opportunity.py. Recorded run run-20261124-ef59e6f at ef59e6f: reconciliation 5,278/5,278, v1 reproduced on valid rows; receipt docs/research/dvp/explore-v3.json.

Files: libs/arbit-model/src/arbit_model/dvp/opportunity.py, libs/arbit-model/src/arbit_model/dvp/explore.py, scripts/model/dvp_explore.py, scripts/model/dvp.py, config/dvp/explore-v3.json, docs/research/dvp/explore-v3.json, libs/arbit-model/tests/test_dvp_opportunity.py

## Validate

Governance checks on the final tree, all exit 0: foundation, model-tests (211 with ARBIT_DVP_AUDIT_RUN; 7 new opportunity tests incl. planted-trait recovery and pure-noise non-reward), point-in-time, lint, format, types, python-suite. Real data at ef59e6f: admission dropped fantasy_points and fantasy_points_ppr and admitted 2016-2025 stats from the pinned manifests; player sums equal team statistics in 5,278 of 5,278 team-games; all 43 cells without a statistics row have 0 points; frozen variants still reproduce v1 on valid rows; every number in OPPORTUNITY_EFFICIENCY.md checked against explore-v3.json (two drafted claims corrected: K's volume channel ties B06 in development; term correlations range wider).

Files: docs/research/dvp/explore-v3.json, libs/arbit-model/tests/test_dvp_opportunity.py

## Document

OPPORTUNITY_EFFICIENCY.md (data, admission, reconciliation, coverage, reliability, forecasting, findings, comparison with original results, possible future tests); SOURCE_PROVENANCE.md (realized statistics through the versioned allowlist); METHODOLOGY.md; EXPERIMENT_REGISTRY.md (V3 rows); README (status, documents, commands); ENG-065; status; changelog; state.json next action.

Files: docs/research/dvp/OPPORTUNITY_EFFICIENCY.md, docs/research/dvp/SOURCE_PROVENANCE.md, docs/research/dvp/METHODOLOGY.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/dvp/README.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Recorded commands

- `foundation`: exit=0, 2026-11-24T23:51:51Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=6682b49cd350113d3c1bf51eb0adadd82dea524bc56503f66f4aade0931f5e8d
- `model-tests`: exit=0, 2026-11-24T23:52:04Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=9697903e1813d30fb9578f4418116dcc433db825b022085ef46168df1b01af2b
- `point-in-time`: exit=0, 2026-11-24T23:52:06Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=33a7644ae9ddc91317f923451765cd3af70226d9ce4b0541a717cc23c970c414
- `lint`: exit=0, 2026-11-24T23:52:06Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-24T23:52:06Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=4005a3baef41e1147158243a5f95a933f558f473d17d288b6610d0488113c185
- `types`: exit=0, 2026-11-24T23:52:06Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py"]; output SHA-256=b3429aa44ddb9f8cd6d195c59088566d18eacf7d37a41d57a8c574445f6a4851
- `python-suite`: exit=0, 2026-11-24T23:53:14Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=ff216a5168975f4b5999d79a1c7a8bbdbbb9de16ac8da253206c1d4ac70e461e

## Findings / decisions / contradictions

- None

## Remaining unresolved / blocked

Remediation 6 (simulation suite, AUD-06), AUD-07 threshold wording, remediation 7 and eligibility metadata are open; the committed plan-audit receipt is from db0d802; the prospective timer awaits owner approval.

## Next executable action

Merge the PR for TASK-20261124-008 (branch claude/m3-dvp-opportunity). Owner decision pending on the prospective sweep timer. Next: remediation 7 (rebuild dvp_plan_audit.py and PLAN_COMPLETION_SCOPE.md with COMPLETE_VERIFIED/PARTIAL/BLOCKED_EXTERNAL/PENDING_FUTURE_DATA/NOT_APPLICABLE/DEFERRED_APPROVAL/NOT_IMPLEMENTED/FAILED, per-variant per-position per-stage validation, test coverage complete vs partial) and research eligibility metadata; AUD-06/AUD-07 as the owner directs.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
