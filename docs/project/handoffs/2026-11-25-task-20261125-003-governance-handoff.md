# Task handoff — TASK-20261125-003 — M3-3 final directive remediation 7: comprehensive plan-completion audit

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Extend the plan audit into the final development gate: a reconciled requirement inventory (specification, AUD-01..07, AUD-01a-d, B0-B8, PB-AUD-01..08, owner decisions DEC-01..10, eligibility), the directive's completion statuses with an evidence rule, semantic checks, reruns from pinned inputs (exploratory v2/v3, the corrected Phase B evaluation, thresholds, a deterministic simulation sample and summary, prospective archive verification, live content verification), negative controls proving the audit detects failure, and a fresh receipt with the overall assessment.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** scripts/model/dvp_plan_audit.py, scripts/model/dvp_plan_audit_directive.py, scripts/model/dvp_simulate.py, scripts/model/dvp_simulate_summary.py, libs/arbit-model/tests/test_dvp_plan_audit.py, docs/research/dvp/plan-audit-receipt.json, docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/research/dvp/audit-findings.json, docs/research/dvp/AUDIT_RECONCILIATION.md, docs/research/dvp/README.md, docs/research/dvp/M3-3_CONTINUITY.md, scripts/model/dvp.py, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json, docs/project/handoffs/2026-11-25-task-20261125-003-governance-handoff.md, libs/arbit-model/src/arbit_model/feature_specs.py

## Review

Read the final directive (§12 remediation 7, F1-F6) and the existing plan audit (dvp_plan_audit.py: 221 items, 164 checks, DONE/OPEN vocabulary, reruns on scratch copies). Reconciled the inventory: original specification, AUD-01..07, AUD-01a-d, Phase B B0-B8, PB-AUD-01..08, DEC-01..10, eligibility and findings. Identified what each new requirement needs as behavioural proof: reruns from pinned inputs, real functions on constructed cases, live archive and timer state.

Files: scripts/model/dvp_plan_audit.py, docs/research/dvp/PLAN_COMPLETION_SCOPE.md

## Plan

Extend, not replace: 1) the directive's completion statuses with an evidence rule (a claim short of completion without an evidence check is FAILED); 2) a directive module registering the new items and semantic checks; 3) new rerun steps (exploratory v2/v3, league v2 from the pinned bundle, thresholds, a deterministic simulation sample and resume, simulation summary, prospective verify, live content re-read); 4) 18 negative controls that must all be detected for PASSED; 5) a fresh receipt with documents, data snapshots, artifact hashes, outcomes, dispositions and the overall assessment; 6) close PB-AUD-08 and update the records.

Files: scripts/model/dvp_plan_audit_directive.py, scripts/model/dvp_plan_audit.py

## Implement

scripts/model/dvp_plan_audit_directive.py (36 items, semantic checks, 18 controls); dvp_plan_audit.py (KIND_STATUS, evidence rule, directive steps, --live, mainPath, receipt v2 fields, controls gate; backtest:variants now requires every configured variant for every group); dvp_simulate.py/dvp_simulate_summary.py (--out target for the summary rerun); dvp.py SCANNED includes the directive module; tests updated. The first full run caught a Phase E docstring in v0 file feature_specs.py (restored to v0 bytes) and the coarse variant check. Second full run: PASSED 257 items, 192/192 checks, 18/18 controls.

Files: scripts/model/dvp_plan_audit_directive.py, scripts/model/dvp_plan_audit.py, scripts/model/dvp_simulate.py, scripts/model/dvp_simulate_summary.py, scripts/model/dvp.py, libs/arbit-model/tests/test_dvp_plan_audit.py, libs/arbit-model/src/arbit_model/feature_specs.py

## Validate

Governance checks all exit 0: foundation, model-tests, point-in-time, lint, format, types, python-suite (1606 passed; 2 skipped only outside the main checkout). The comprehensive audit itself: rerun at ea103b1 with --live on fresh scratch (31 steps, all expected exits; the frozen 2025 holdout from 165d140), then check: PASSED, 257 items (252 COMPLETE_VERIFIED, 2 PENDING_FUTURE_DATA, 2 NOT_APPLICABLE, 1 DEFERRED_APPROVAL), 192/192 checks, 18/18 negative controls detected, 272 model tests with none skipped. Receipt docs/research/dvp/plan-audit-receipt.json.

Files: docs/research/dvp/plan-audit-receipt.json, libs/arbit-model/tests/test_dvp_plan_audit.py

## Document

PLAN_COMPLETION_SCOPE.md rebuilt (statuses, header counts, final directive section with 36 rows, negative controls, corrections); audit-findings.json and AUDIT_RECONCILIATION.md close PB-AUD-08; README, M3-3_CONTINUITY completion state, status, changelog (and its Phase E feature_specs claim corrected), decision register ENG-071.

Files: docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/research/dvp/audit-findings.json, docs/research/dvp/AUDIT_RECONCILIATION.md, docs/research/dvp/README.md, docs/research/dvp/M3-3_CONTINUITY.md, docs/project/status.md, docs/project/changelog.md, docs/project/decision-register.md

## Recorded commands

- `foundation`: exit=0, 2026-11-25T15:03:53Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=03927c84c500bf9e139263a98ba72a5dc31550c42852d23deffa8eca983749d9
- `model-tests`: exit=0, 2026-11-25T15:04:19Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=fbe124a8a386a20fc18bfe4b7bcee3d3944ffb0b1d0ffa3a2ead7f02dc8eaf91
- `point-in-time`: exit=0, 2026-11-25T15:04:21Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=537772f0813ef37798ddece755bfa5cf36cfc238fe0485b18edcbf57424de1d6
- `lint`: exit=0, 2026-11-25T15:04:21Z; argv=["env", "-u", "VIRTUAL_ENV", "uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-25T15:04:21Z; argv=["env", "-u", "VIRTUAL_ENV", "uv", "run", "ruff", "format", "--check", "."]; output SHA-256=0ccd40004adb6a6768747e829f98877ee39c1da053df52031678efa047bf185c
- `types`: exit=0, 2026-11-25T15:04:22Z; argv=["env", "-u", "VIRTUAL_ENV", "uv", "run", "mypy", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_plan_audit_directive.py", "scripts/model/dvp_simulate.py", "scripts/model/dvp_simulate_summary.py"]; output SHA-256=677cdd53a7a744327882d60280be642f3cc81a9729b88a8e705e0cc41e5b0a4e
- `python-suite`: exit=0, 2026-11-25T15:05:44Z; argv=["env", "-u", "VIRTUAL_ENV", "uv", "run", "pytest", "-q"]; output SHA-256=de18b8107928927c779e3dde744377512fdf3dde17f0daae8ce95df727dc5026

## Findings / decisions / contradictions

- 2026-11-25T09:33:18Z [correction] The audit caught a regression from Phase E: a docstring note added to arbit_model/feature_specs.py changed a v0 file that must stay byte-identical (v0:bytes, rerun:continuity, open:owner-weight failed). Restored to its v0 bytes; the note remains in AGENTS.md, RESEARCH_ELIGIBILITY.md and the eligibility module. Scope extended by hand with feature_specs.py. — libs/arbit-model/src/arbit_model/feature_specs.py
- 2026-11-25T09:33:18Z [correction] A negative control found backtest:variants too coarse (it checked variant families pooled across groups, so a variant missing for one group passed). Strengthened to require every configured variant for every group in every stage. — scripts/model/dvp_plan_audit.py
- 2026-11-25T15:07:16Z [next_step] Merge PR for claude/m3-final-rem7 after CI; then no M3-3 development remains. The timer collects weeks 13-18 (week 13 window 2026-12-01 12:00 to 12-04 01:15 UTC); after the regular season evaluate P4P and C05L-2026-PRO with the frozen rules (amendment 1 gate), then the owner decides P5W. — docs/research/dvp/PLAN_COMPLETION_SCOPE.md

## Remaining unresolved / blocked

PENDING_FUTURE_DATA: P4P and C05L-2026-PRO (2026 weeks 12-18 outcomes). DEFERRED_APPROVAL: P5W (owner's D/ST production weight). Reported limitations: A8 declared null failed in the simulation; WR inconclusive. No feature is production-eligible.

## Next executable action

M3-3 development is complete (remediation 7 PASSED: 257 items, 192/192 checks, 18/18 controls). Nothing to build. Monitor the prospective timer (arbit-dvp-prospective.timer; week 13 window 2026-12-01 12:00 to 12-04 01:15 UTC; alerts reach Windows). After the 2026 regular season: evaluate P4P and C05L-2026-PRO with the frozen rules on a COMPLETE window; then the owner's P5W D/ST weight decision. Otherwise resume the roadmap (sit/start advisor work).

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
