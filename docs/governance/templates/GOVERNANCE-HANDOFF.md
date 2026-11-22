# Task handoff template

Generated handoffs are placed under `docs/project/handoffs/` and preserve task ID.

- Objective, owner authorization, affected requirement IDs and task phase.
- Sources/decisions reviewed, assumptions and conflicts.
- Files/interfaces changed; exact observed result and change classification.
- Executed validation commands (exit codes, UTC dates, exact scope) and unrun checks.
- Documentation/status/issue/ADR updates.
- Blockers/risks/rollback, deployment state (not inferred from tests).
- Single next executable action and prerequisites for a fresh agent.

A handoff is not an approval record and cannot by itself prove production state.
