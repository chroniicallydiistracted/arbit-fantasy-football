# Task handoff — TASK-20261125-002 — M3-3 final directive Phase E: research eligibility registry and fail-closed assembly check

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Record every M3-3 DvP feature's research evidence, classification and production eligibility in one machine-readable registry extending arbit_model.feature_specs, with a fail-closed check at the model assembly boundary, so no later agent mistakes a feature's existence, historical reliability, research promise or prospective confirmation for production eligibility. No feature is activated and no production behavior or legacy constant changes. Also close AUD-01a now that unattended publication is verified with the owner-registered key.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** config/model/research-eligibility.json, libs/arbit-model/src/arbit_model/eligibility.py, libs/arbit-model/tests/test_eligibility.py, libs/arbit-model/src/arbit_model/feature_specs.py, AGENTS.md, docs/research/dvp/RESEARCH_ELIGIBILITY.md, docs/research/dvp/audit-findings.json, docs/research/dvp/AUDIT_RECONCILIATION.md, docs/research/dvp/README.md, docs/research/dvp/MODEL_CARD.md, scripts/model/dvp.py, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json, docs/project/handoffs/2026-11-25-task-20261125-002-governance-handoff.md

## Review

Inspected the existing feature registry (arbit_model.feature_specs: FEATURES with definitions, units, windows, sources and SHRINKAGE constants; legacy DvP columns opp_dvp_{QB..K}_{pg,pg_shrunk,adj,adj_shrunk,opps_pg} and opp_off_dst_allowed_*) and its consumers (team_features only; no production model assembles them). Collected each feature's evidence from the committed receipts (reliability-results A05/A07, backtest receipts, sitstart, league v2, explore-v3, simulation-v1, threshold-sensitivity-v1). Verified the owner-registered deploy key from the timer's service context (AUD-01a).

Files: libs/arbit-model/src/arbit_model/feature_specs.py, docs/research/dvp/reliability-results.json

## Plan

1) A machine-readable registry (config/model/research-eligibility.json) with the directive's fields and initial classifications. 2) arbit_model.eligibility: load with validation (required fields, evidence kinds, classifications, no production eligibility without recorded approvals), governing() by entry id, feature_specs patterns and estimator columns, check_assembly failing closed for production and reporting for research. 3) Tests. 4) feature_specs note and an AGENTS.md rule pointing production assembly at the gate; no feature activated, no constant changed. 5) Docs and records; close AUD-01a.

Files: config/model/research-eligibility.json, libs/arbit-model/src/arbit_model/eligibility.py

## Implement

config/model/research-eligibility.json (10 entries); arbit_model/eligibility.py (load, governing, check_assembly, classifications, covered; RegistryError, IneligibleFeature; DVP_LIKE pattern for unregistered DvP-like names); feature_specs docstring note; AGENTS.md rule.

Files: config/model/research-eligibility.json, libs/arbit-model/src/arbit_model/eligibility.py, libs/arbit-model/src/arbit_model/feature_specs.py, AGENTS.md

## Validate

All seven checks pass. test_eligibility.py (6): the directive's classifications recorded and nothing production-eligible; every legacy DvP feature_specs column governed and every registry pattern matching a real column; legacy shrinkage constants unchanged; production assembly refuses legacy columns, estimator columns, entry ids and unregistered DvP-like names while passing other features; research use reports; a registry claiming eligibility without recorded approvals, or with a missing evidence kind or unknown classification, fails to load. AUD-01a verified live: deploy key read-write, systemd-run publication over SSH with read-back and GitHub timestamp.

Files: libs/arbit-model/tests/test_eligibility.py

## Document

RESEARCH_ELIGIBILITY.md; MODEL_CARD.md eligibility note; DvP README; audit-findings.json (AUD-01a resolved, eligibility requirement resolved) and AUDIT_RECONCILIATION.md; decision register ENG-070; AGENTS.md rule; feature_specs note; status; changelog; next action.

Files: docs/research/dvp/RESEARCH_ELIGIBILITY.md, docs/research/dvp/audit-findings.json, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, AGENTS.md

## Recorded commands

- `foundation`: exit=0, 2026-11-25T09:09:42Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=a17f6745e4f2f6755a71cc19f87ae2fd4161548796a1494c5cef1b7f5e0cfc7c
- `model-tests`: exit=0, 2026-11-25T09:09:59Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=847fdc2fe5d7e226655f870fd9a1ce1faba4b06f634387cc656250357cb08022
- `point-in-time`: exit=0, 2026-11-25T09:10:01Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=173e473933a98d58f101464389496b1ac3431de03ab98b4c2ffc3eea5a1d0fc9
- `lint`: exit=0, 2026-11-25T09:10:01Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-25T09:10:01Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=0ccd40004adb6a6768747e829f98877ee39c1da053df52031678efa047bf185c
- `types`: exit=0, 2026-11-25T09:10:08Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py"]; output SHA-256=9d4d7e2a1d327e172e77feaa5ce9c52048e1c0cd4529d29acf1e814c347b343e
- `python-suite`: exit=0, 2026-11-25T09:11:16Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=b1a07fd6eb0305410b98730b2d2ef34cb1565d175ff74ba4085b6a2ede27a06e

## Findings / decisions / contradictions

- None

## Remaining unresolved / blocked

Remediation 7 and PB-AUD-08's audit rerun; prospective weeks 13-18 (future data).

## Next executable action

Merge the Phase E PR after CI, then remediation 7: the comprehensive plan audit (reconciled inventory, directive statuses, semantic checks, reruns from pinned inputs incl. PB-AUD-08, negative controls, fresh receipt).

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
