# Task handoff — TASK-20261122-003 — Record owner decisions OWN-066 to OWN-068: ADR-007 accepted with amendments, Q-014 conditionally approved, Sit/Start first

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Every authority document, rule and restart digest states the accepted availability policy with the owner's timing amendments, the evidence-gated betting-line decision and Lineup sit/start as the first advisor, with Q-012/R-067 reconciled and weather questions recorded

**Requirements:** GOVAI-002, GOVAI-003, GOVAI-013, GOVAI-014, GOVAI-017, MD-004, LN-003

**Change class:** governance

**Scoped files:** docs/project/decision-register.md, docs/architecture/decisions/007-model-availability.md, docs/architecture/decisions/README.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/roadmap.md, docs/project/known-issues.md, docs/governance/START_HERE.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, docs/governance/REPO_MAP.md, docs/governance/requirements.json, .claude/rules/model-integrity.md, libs/arbit-model/AGENTS.md, scripts/governance.py, docs/governance/state.json, docs/project/status.md, docs/project/changelog.md

## Review

Owner answers in chat 2026-11-22: (1) ADR-007 approved with caveats: retroactively fetched data that was available at the time still applies; preserve reliable timestamps; define when data applies and how it refreshes rather than barring it. (2) Q-014 approved for integration only if it truly helps, after understanding how lines are set and measuring accuracy. (3) Agreed Lineup sit/start first; projections must explain why (player performance, position vs opposing defense, weather, injuries, depth charts, league scoring). Found ADR-007 called proposed in 9 places (ADR index, START_HERE, charter, REPO_MAP, GOVAI-013, model-integrity rule, arbit-model AGENTS, governance brief text, status), Q-012's 'Nothing fetches from NFL's API' superseded by OWN-040/041 (R-067), and R-063 treating weather as never a pre-game input.

Files: docs/architecture/decisions/007-model-availability.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/research/live-play-detail-2026-11-03.md, libs/arbit-model/src/arbit_model/fields.py

## Plan

Add OWN-066..068 and Q-016 (weather forecast) to the register; mark Q-005 resolved, Q-012 superseded, Q-014 conditionally approved; set ADR-007 Accepted with an Owner amendments section (A1 late fetch counts from source availability: max(source timestamp or family rule, gap start); A2 timing not exclusion; A3 gaps from Arbit's own read records; A4 what stays unknown); update the ADR index, plan (sequencing, Q-014 study, explanation contributions, catalog re-review), roadmap M4, R-063/R-067, governance docs/rules/brief. No Model code or catalog change in this task.

Files: docs/project/decision-register.md, docs/architecture/decisions/007-model-availability.md, docs/architecture/decisions/README.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/roadmap.md, docs/project/known-issues.md, docs/governance/START_HERE.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, docs/governance/REPO_MAP.md, docs/governance/requirements.json, .claude/rules/model-integrity.md, libs/arbit-model/AGENTS.md, scripts/governance.py, docs/governance/state.json

## Implement

ADR-007 set Accepted with an Owner amendments section (A1 late fetch counts from source timestamp or family rule, never before gap start, with labeled basis; A2 timing not exclusion, catalog re-review; A3 gaps from Arbit read records; A4 what stays unknown). Decision register: OWN-066/067/068 with owner quotes, Q-005 resolved, Q-012 superseded with exact api.nfl.com routes, Q-014 conditionally approved (study, capture, ablation), new Q-016 weather forecast. ADR index, M3 plan (sequencing, contributions, defense vs position, gap-aware reader, catalog re-review, Q-014 note), roadmap M4 order, R-063 amended, R-067 resolved, START_HERE, charter, REPO_MAP, GOVAI-013, model-integrity rule, arbit-model AGENTS and the brief's critical-unresolved line updated. No Model code or field catalog changed.

Files: docs/project/decision-register.md, docs/architecture/decisions/007-model-availability.md, docs/architecture/decisions/README.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/roadmap.md, docs/project/known-issues.md, docs/governance/START_HERE.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, docs/governance/REPO_MAP.md, docs/governance/requirements.json, .claude/rules/model-integrity.md, libs/arbit-model/AGENTS.md, scripts/governance.py

## Validate

Observed exit 0: foundation validator (links and registry), governance doctor, 14 governance unit tests. brief prints the updated critical-unresolved line. Repo-wide ruff check and format still pass (scripts/governance.py is outside Ruff's configured include). Documentation-only semantics are reviewed, not machine-proven.

Files: not separately listed

## Document

Status: owner decisions block, slice 2 ADR-007 line, Q-014 line, M3 and M4 milestone rows. Changelog entry. The governance state next action is refreshed at the end of the catch-up task.

Files: docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-22T23:16:06Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=289fe0f41a4600914b5e077d19fc7a3519bd7be7d7d63a3df53dc9807720dc18
- `governance`: exit=0, 2026-11-22T23:16:06Z; argv=["python", "scripts/governance.py", "doctor"]; output SHA-256=828a81d5d73f64c19b1857df41ebf03677d9c68bf0b30966137359239adc446a
- `governance-tests`: exit=0, 2026-11-22T23:16:06Z; argv=["python", "-m", "unittest", "discover", "-s", "tests/governance", "-p", "test_*.py"]; output SHA-256=1407e9ef1b460d1e5c2992a642f0e8b691d103ea81d0f8dcc706eee2de39855f
- `foundation`: exit=0, 2026-11-22T23:16:39Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=289fe0f41a4600914b5e077d19fc7a3519bd7be7d7d63a3df53dc9807720dc18
- `governance`: exit=0, 2026-11-22T23:16:39Z; argv=["python", "scripts/governance.py", "doctor"]; output SHA-256=828a81d5d73f64c19b1857df41ebf03677d9c68bf0b30966137359239adc446a
- `governance-tests`: exit=0, 2026-11-22T23:16:40Z; argv=["python", "-m", "unittest", "discover", "-s", "tests/governance", "-p", "test_*.py"]; output SHA-256=ae753e24191322573e35495fbdeec56f9dbbb946813542c9e3a3df758d2be35e

## Findings / decisions / contradictions

- 2026-11-22T23:16:39Z [observation] Owner decisions recorded verbatim with chat source (2026-11-22): OWN-066 ADR-007 with amendments, OWN-067 betting lines evidence-gated, OWN-068 Lineup sit/start first with explanation requirement. — Owner message in the 2026-11-22 Claude session; docs/project/decision-register.md
- 2026-11-22T23:16:39Z [question] Q-016: weather forecast for the upcoming game (Model exception vs advisor-layer context). Recommendation (b) first; measure (a) on recorded 2016-2025 weather. — docs/project/decision-register.md Q-016

## Remaining unresolved / blocked

Q-016 awaits the owner. The field catalog's betting-lines reason text and timing-only exclusions are re-reviewed in slice 3 (plan).

## Next executable action

Build the catch-up (TASK-20261122-004); then M3 slice 3 under a model-class task: gap-aware ADR-007 reader with labeled bases, features including defense against the position, catalog re-review, and the Q-014 research note.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
