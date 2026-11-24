# Task handoff — TASK-20261124-005 — M3-3 DvP plan completion audit and scope document

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Audit every action item of the owner's DvP specification v1.1 (docs/research/Arbit_FFA_M3_DvP_Plan.md, OWN-074) against the repository by rerunning its evidence, not by citing old receipts: the test suite with per-test results, v0 reproduction, the Phase 0-1 audit, the reliability lab, all three backtest stages (holdout from the frozen commit), Phase C and verify. Encode the item-to-evidence map as an executable audit that writes a machine-readable receipt, and write a scope document into the repository that lists each completed action item, the code and model logic behind it, and its passing proof. Open items (prospective 2026 scoring, owner weight decision, BLOCKED C03 and league lineups) are stated as open. No production, weight or canonical-table change.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** scripts/model/dvp_plan_audit.py, libs/arbit-model/tests/test_dvp_plan_audit.py, docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/research/dvp/plan-audit-receipt.json, docs/research/dvp/README.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json, libs/arbit-model/tests/test_dvp_firewall.py, scripts/model/dvp.py, docs/research/dvp/DATA_QUALITY.md, docs/research/dvp/V0_REPRODUCTION.md, docs/project/handoffs/2026-11-24-task-20261124-005-governance-handoff.md

## Review

Read the owner's DvP specification v1.1 in full (sections 0-14) and the repository's DvP code, tests, configs, receipts and documents. Mapped every action item to evidence: 14 operating rules, RQ1-RQ7, definitions, the data boundary and eligibility table, datasets and reconciliation checks, v0 items, A00-A12, B00-B12, C00-C05, statistics, metrics and decision rules, T01-T40, phases 0-5, CLI contracts and modes, config and record fields, section 11 deliverables and before-completion checks, the section 12 decision chain and the section 13 caveats. Reran every stage on scratch copies (audit, reproduce-v0, reliability, development, validation from main; 2025 holdout from the frozen tree 165d140; holdout refused from main; sitstart; verify; report; registry): every receipt equals its committed version apart from code, time, run ID, byte hashes of Parquet files and fields added after a receipt was made; holdout forecasts equal within 7.1e-15 (18 values). Found: DATA_QUALITY.md and V0_REPRODUCTION.md cite an earlier audit run (021910Z, bc414a0) than their receipts (024442Z, 3a1fe11); dry-run and resume modes were never built; the project next action still says to merge PR #12, which is merged.

Files: docs/research/dvp/DATA_QUALITY.md, docs/research/dvp/V0_REPRODUCTION.md

## Plan

1) Encode the item-to-evidence map as an executable audit, scripts/model/dvp_plan_audit.py: 'rerun' copies the frozen audit run and receipts to scratch and reruns every stage (holdout from a worktree at 165d140; the holdout's refusal from this tree) plus the model tests with JUnit results; 'check' evaluates every item's checks and writes docs/research/dvp/plan-audit-receipt.json (DONE / OPEN / FAILED per item; exit 1 on any failure). Open items (prospective 2026 scoring, owner weight, C03, league lineups, dry-run/resume) are kind 'open': their checks prove the open state is recorded, never count as done. 2) Tests (test_dvp_plan_audit.py): catalog covers every specified ID; every check defined and used; every T tag names real tests; open items never count as done; receipt comparison and forecast-difference logic; committed receipt passes, matches the catalog and the specification hash; the scope document has a row for every item. 3) Commit code first, then run the audit so the receipt names a clean commit. 4) Write PLAN_COMPLETION_SCOPE.md (every item: status, code/model logic, proof) from the receipt. 5) Fix the stale run IDs; update README, status, changelog, state.json next action; handoff.

Files: scripts/model/dvp_plan_audit.py, libs/arbit-model/tests/test_dvp_plan_audit.py, docs/research/dvp/PLAN_COMPLETION_SCOPE.md

## Implement

scripts/model/dvp_plan_audit.py (committed db0d802): ITEMS, 214 action items in specification order, each with its checks and kind (done/open); CHECKS, 156 checks: per-tag test results from JUnit (T01-T40, B11, Phase C, Phase 4 rule, whole suite), field-by-field rerun comparisons with explicit allowed fields per receipt, observation-table equality, forecast equality within 1e-9 (holdout: 18 values, at most 7.1e-15), byte identity of report outputs, holdout refusal from this tree, untouched committed run and config, v0 hashes, audit/provenance/finality/registry/reliability/backtest/verify/Phase C receipts, the frozen timeline, Phase C rule committed before results, config keys, deliverables, model card table and flags, and the open states. 'rerun' writes only to scratch and hashes the committed run and config/dvp before and after. Audit result at db0d802: PASSED, 209 done, 5 open, 156/156 checks, 157 tests 0 skipped. tests/test_dvp_plan_audit.py (9 tests). PLAN_COMPLETION_SCOPE.md: every item with status, logic and proof. DATA_QUALITY.md and V0_REPRODUCTION.md now cite run 024442Z (code 3a1fe11); the earlier run 021910Z built an identical observation table (verified).

Files: scripts/model/dvp_plan_audit.py, libs/arbit-model/tests/test_dvp_plan_audit.py, docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/research/dvp/plan-audit-receipt.json, docs/research/dvp/DATA_QUALITY.md, docs/research/dvp/V0_REPRODUCTION.md

## Validate

Plan audit at db0d802: PASSED, 214 items (209 done, 5 open), 156/156 checks; reruns: audit 1.5 s, reproduce-v0 6.9 s, reliability 72.2 s, development 26.1 s, validation 7.0 s, holdout from 165d140 4.3 s, holdout refused from this tree (exit 1, expected), sitstart, verify, report, registry, model tests 157 passed 0 skipped. Every rerun receipt equal to its committed version except allowed fields; observation table identical (31,668 rows); development and validation forecast files left byte-identical; holdout forecasts within 7.1e-15 (18 values); METRICS.csv and 15 plots byte-identical; committed run and config/dvp unchanged. Governance checks on the final tree: foundation, model-tests (with ARBIT_DVP_AUDIT_RUN), point-in-time, lint, format, types (mypy including dvp_plan_audit.py), python-suite: all exit 0. Without the audit run (as CI): 1491 passed, 2 skipped (the real-artifact tests).

Files: docs/research/dvp/plan-audit-receipt.json, libs/arbit-model/tests/test_dvp_plan_audit.py

## Document

PLAN_COMPLETION_SCOPE.md (new): result, method, how the slice fits together, rerun table, and every item of sections 0-13 with status, code/model logic and proof check IDs with observed values; open items; corrections; how to reproduce. DvP README: status row, documents row and audit commands. DATA_QUALITY.md and V0_REPRODUCTION.md: correct audit run. Project: status (PR #12 on main; this task), changelog, state.json next action.

Files: docs/research/dvp/PLAN_COMPLETION_SCOPE.md, docs/research/dvp/README.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Recorded commands

- `foundation`: exit=0, 2026-11-24T21:38:31Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=af7079ec74072414a2455ce54e85a74dd9a7045b346cbbcba957aab8c0094cc8
- `model-tests`: exit=0, 2026-11-24T21:38:39Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=156ece136dd4e81a25556f4a29fecc354b0e9ae0975bae9e36be61ac6f007624
- `point-in-time`: exit=0, 2026-11-24T21:38:41Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=99ea0c98314503c11516d1ec256e687d684016ed9ac413fbc86c1d4ba36cc020
- `lint`: exit=0, 2026-11-24T21:38:41Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-24T21:38:41Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=f8b70b44179ea8bfc8a9879b9cda05be677d2e1782928711c970613714ee12a0
- `types`: exit=0, 2026-11-24T21:38:44Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py"]; output SHA-256=501f59ebd183d787086d4593129606e11d6cf6903f6cc2a9151dc25d860a0f47
- `python-suite`: exit=0, 2026-11-24T21:39:51Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=7bdd263cbf3433c356f1a4e0489a717c369fe476fed9c7f7a81d018505e2094c

## Findings / decisions / contradictions

- 2026-11-24T21:30:16Z [correction] Scope extended by hand (governance has no scope command) with docs/research/dvp/DATA_QUALITY.md and V0_REPRODUCTION.md, which cite audit run phase1-audit-20261124T021910Z (code bc414a0) while their receipts come from phase1-audit-20261124T024442Z (code 3a1fe11), and with this task's handoff file. — docs/research/dvp/DATA_QUALITY.md
- 2026-11-24T21:41:19Z [observation] Plan completion audit PASSED: 214 action items (209 done, 5 open), 156/156 checks, from reruns of every stage (holdout from the frozen commit) compared field by field with the committed receipts. — docs/research/dvp/plan-audit-receipt.json
- 2026-11-24T21:41:19Z [question] Dry-run and resume modes (spec section 9, 'when appropriate') were never built; stages take 0.5-72 s and verify plus pre-write hash checks cover a dry run's purpose. Recorded as NOT BUILT; build them if the owner wants them. — docs/research/dvp/PLAN_COMPLETION_SCOPE.md

## Remaining unresolved / blocked

Prospective 2026 weeks 12-18 scoring (after the season); owner decision on a D/ST production weight (OWN-074); C03 and league-constrained lineups BLOCKED (no meaning for D/ST; no FFA lineups before 2026); dry-run and resume modes not built.

## Next executable action

Merge the DvP plan-audit PR (branch claude/m3-dvp-scope-audit, TASK-20261124-005). DvP research then waits only on the 2026 regular season: rebuild the targets with 2026, score the frozen weeks 12-18 at both levels from the frozen commit 165d140 (docs/research/dvp/PROSPECTIVE_2026.md), rerun scripts/model/dvp_plan_audit.py, and put the D/ST weight decision to the owner (OWN-074). Meanwhile, M3 slices 3c-3e and weather W1; NWS User-Agent contact from the owner before W3.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
