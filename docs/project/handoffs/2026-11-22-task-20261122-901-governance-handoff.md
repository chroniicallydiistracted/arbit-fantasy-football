# Task handoff — TASK-20261122-901 — Build cross-agent durable context governance for Arbit

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Implement a project-native authoritative knowledge, accountable task lifecycle, transparent agent recovery and CI traceability system without changing accepted statistical Model rules or deploying services.

**Requirements:** GOVAI-001, GOVAI-004, GOVAI-005, GOVAI-007, GOVAI-009, GOVAI-018, GOVAI-019

**Change class:** governance

**Scoped files:** .claude/rules/model-integrity.md, .claude/rules/operations-safety.md, .claude/settings.json, .github/workflows/context-governance.yml, AGENTS.md, CLAUDE.md, Makefile, apps/web/AGENTS.md, docs/engineering/agentic-development-standard.md, docs/governance/AUDIT_2026-11-22.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, docs/governance/README.md, docs/governance/REPO_MAP.md, docs/governance/SOURCE_OF_TRUTH.md, docs/governance/START_HERE.md, docs/governance/change-gates.json, docs/governance/check-commands.json, docs/governance/global/claude/CLAUDE.md, docs/governance/global/codex/AGENTS.md, docs/governance/requirements.json, docs/governance/state.json, docs/governance/tasks/.gitkeep, docs/governance/templates/GOVERNANCE-HANDOFF.md, docs/project/changelog.md, docs/project/known-issues.md, docs/project/status.md, foundation-manifest.json, libs/arbit-model/AGENTS.md, scripts/governance.py, scripts/governance_hook.py, scripts/install_global_instructions.py, services/api/AGENTS.md, services/worker/AGENTS.md, tests/governance/test_governance.py

## Review

Reviewed original instructions, project status, model design ADR-006/007, Model source code, API unavailable contract, CI, foundation checker, newest handoff, and existing project requirements.

Files: AGENTS.md, CLAUDE.md, docs/project/status.md, docs/project/handoffs/2026-11-22-m3-integration.md, docs/architecture/decisions/006-model-architecture.md, docs/architecture/decisions/007-model-availability.md, scripts/validate_foundation.py, libs/arbit-model/src/arbit_model/inputs.py

## Plan

Extend but do not overwrite accepted project decisions; add governance requirements, restart index, task state+journal, pinned command check profiles, scoped instructions, CLAUDE hooks, opt-in global templates, offline unit tests, and PR diff coverage. Owner deployment remains out of scope.

Files: .claude/rules/model-integrity.md, .claude/rules/operations-safety.md, .claude/settings.json, .github/workflows/context-governance.yml, AGENTS.md, CLAUDE.md, Makefile, apps/web/AGENTS.md, docs/engineering/agentic-development-standard.md, docs/governance/AUDIT_2026-11-22.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, docs/governance/README.md, docs/governance/REPO_MAP.md, docs/governance/SOURCE_OF_TRUTH.md, docs/governance/START_HERE.md, docs/governance/change-gates.json, docs/governance/check-commands.json, docs/governance/global/claude/CLAUDE.md, docs/governance/global/codex/AGENTS.md, docs/governance/requirements.json, docs/governance/state.json, docs/governance/tasks/.gitkeep, docs/governance/templates/GOVERNANCE-HANDOFF.md, docs/project/changelog.md, docs/project/known-issues.md, docs/project/status.md, foundation-manifest.json, libs/arbit-model/AGENTS.md, scripts/governance.py, scripts/governance_hook.py, scripts/install_global_instructions.py, services/api/AGENTS.md, services/worker/AGENTS.md, tests/governance/test_governance.py

## Implement

Added cross-provider context policy, 20 governance obligations, future advisor charter, scoped model/API/web/worker instructions, validated task stages and blocked-task resumption, pinned command receipt hashing, CI diff gate, opt-in global installer, and source audit. Existing Model code unchanged.

Files: .claude/rules/model-integrity.md, .claude/rules/operations-safety.md, .claude/settings.json, .github/workflows/context-governance.yml, AGENTS.md, CLAUDE.md, Makefile, apps/web/AGENTS.md, docs/engineering/agentic-development-standard.md, docs/governance/AUDIT_2026-11-22.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, docs/governance/README.md, docs/governance/REPO_MAP.md, docs/governance/SOURCE_OF_TRUTH.md, docs/governance/START_HERE.md, docs/governance/change-gates.json, docs/governance/check-commands.json, docs/governance/global/claude/CLAUDE.md, docs/governance/global/codex/AGENTS.md, docs/governance/requirements.json, docs/governance/state.json, docs/governance/tasks/.gitkeep, docs/governance/templates/GOVERNANCE-HANDOFF.md, docs/project/changelog.md, docs/project/known-issues.md, docs/project/status.md, foundation-manifest.json, libs/arbit-model/AGENTS.md, scripts/governance.py, scripts/governance_hook.py, scripts/install_global_instructions.py, services/api/AGENTS.md, services/worker/AGENTS.md, tests/governance/test_governance.py

## Validate

Foundation validator, governance doctor and 14 isolated CLI tests executed successfully against extracted source. Added CLI-dispatch and PR-diff regression coverage after discovering a real argparse collision; production runtime, database, browser and live provider integrations remain untested here.

Files: not separately listed

## Document

Updated status/changelog to identify prepared governance artifacts, recorded R-067 source-policy clarification risk, authored source audit, authority map, resume instructions and portable global templates. Preserved original product brief and accepted ADRs.

Files: docs/project/status.md, docs/project/changelog.md, docs/project/known-issues.md, docs/governance/AUDIT_2026-11-22.md

## Recorded commands

- `governance`: exit=0, 2026-11-22T22:31:37Z; argv=["python", "scripts/governance.py", "doctor"]; output SHA-256=828a81d5d73f64c19b1857df41ebf03677d9c68bf0b30966137359239adc446a
- `foundation`: exit=0, 2026-11-22T22:31:38Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=367d94fd83ffea437e76e2b9358a349b01f3ffd206c15853f943e8dec63585a8
- `governance-tests`: exit=0, 2026-11-22T22:31:41Z; argv=["python", "-m", "unittest", "discover", "-s", "tests/governance", "-p", "test_*.py"]; output SHA-256=08819bfa7e324146f3569876efd0126652ba1ab1228f4961d0ba140b0fd01135
- `governance`: exit=0, 2026-11-22T22:32:51Z; argv=["python", "scripts/governance.py", "doctor"]; output SHA-256=828a81d5d73f64c19b1857df41ebf03677d9c68bf0b30966137359239adc446a
- `foundation`: exit=0, 2026-11-22T22:32:52Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=367d94fd83ffea437e76e2b9358a349b01f3ffd206c15853f943e8dec63585a8
- `governance-tests`: exit=0, 2026-11-22T22:32:55Z; argv=["python", "-m", "unittest", "discover", "-s", "tests/governance", "-p", "test_*.py"]; output SHA-256=8c52abee477efe74f695f23c11b024a6c32f76b28a79c4bde82b39c0f09406d2

## Findings / decisions / contradictions

- 2026-11-22T22:31:14Z [observation] Original root AGENTS.md had a stale latest handoff pointer; original foundation validator passed without a task or PR traceability gate. — Uploaded source AGENTS.md, scripts/validate_foundation.py, docs/project/handoffs/2026-11-22-m3-integration.md
- 2026-11-22T22:31:15Z [risk] ADR-007 remains proposed and model predictions are unimplemented; production runtime, model and end-to-end auth/browser tests were not exercised in this audit environment. — docs/architecture/decisions/007-model-availability.md; libs/arbit-model/README.md; docs/governance/AUDIT_2026-11-22.md
- 2026-11-22T22:31:16Z [next_step] User must apply archive to actual repository, review diff, enable branch protection and separately validate runtime in pinned developer environment. — docs/governance/README.md
- 2026-11-22T22:32:48Z [correction] Amended validation: Additional CLI coverage found and fixed a command-dispatch bug, then expanded tests to 14 — previous_summary_sha256=174ef7062455841098b85367399c92eadafff22ed3014c83407976fd66acd247
- 2026-11-22T22:32:49Z [correction] Validation exposed a CLI parser collision in run-check dispatch; it was fixed, and 14 standard-library tests now include CLI dispatch and GitHub PR diff-gate evidence. — scripts/governance.py; tests/governance/test_governance.py

## Remaining unresolved / blocked

No live deployment, database integration, model forecasting or provider freshness was tested by this package. Actual protected-branch configuration must be enabled in user repository; Q-012 historical NFL API wording needs scoped reconciliation and ADR-007 needs owner acceptance before model backtests.

## Next executable action

Integrate the overlay in a reviewable real Git branch. Require Context governance CI and run make governance-check, then run full pinned runtime and browser validation. Independently check M3 PR/release status; do not adopt proposed ADR-007 without owner approval.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
