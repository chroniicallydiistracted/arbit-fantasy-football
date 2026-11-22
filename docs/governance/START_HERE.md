# Arbit: start here (Codex / Claude / fresh agent)

This is the persistent restart entry point. Never assume chat history, another
agent's summary, or this snapshot of the repository reflects the running service.

## First five commands and reads

1. `python scripts/governance.py brief` — active/blocked tasks, next action, status and handoff pointers.
2. `python scripts/governance.py doctor` — structural problems and governance drift.
3. Read [current status](../project/status.md), [existing issues](../project/known-issues.md), [roadmap](../project/roadmap.md), and the exact handoff identified by `brief`.
4. Read the task record in `docs/governance/tasks/`, [requirements](../product/requirements.json), [owner decisions](../project/decision-register.md), [ADRs](../architecture/decisions/README.md), and relevant source/tests; use the [code map](REPO_MAP.md) to locate ownership.
5. If no task is active, identify the next *authorized* objective in status/roadmap; create a task record via `start` before editing. If no objective can be proven, record the gap and ask only for the specific missing decision.

## Source-of-truth order

Current explicit owner authorization > recorded accepted owner decisions and
ADRs > original immutable brief / product registry > inspected code and
reproducible observed test evidence > current status/accepted handoffs > proposed
plans > speculation. The application’s actual runtime state can differ from the
repository and must be verified separately before release claims. See
[authority matrix](SOURCE_OF_TRUTH.md).

## Open product boundaries

- ESPN FFA league `1729878439`, 2026 annual redraft; the actual league rules are authoritative.
- M3 is in progress. The shared `arbit-model` library currently provides field
  catalog / statistical targets, **not a trained or released prediction engine**.
- [ADR-006](../architecture/decisions/006-model-architecture.md) is accepted:
  nflverse-only statistical model inputs, team-first simulations, exact FFA scoring.
  [ADR-007](../architecture/decisions/007-model-availability.md) is **proposed**, not accepted.
- Model training/backtest providers are more restricted than a future advisor's
  external **research**. Research must not silently contaminate model features,
  training targets, benchmarks or the canonical scorer.
- M4 lineup/waivers, M5 trades/draft, and full advice are not delivered. M6 Live
  has separately running and unreleased slices. Do not call an unfinished module finished.
- The latest recorded M3 integration handoff states that GitHub integration was
  requested, but database-backed local proof was unavailable and worker activation
  required a separate owner operation. Verify repository and deployment state before updating this.

## How to use a task record

Use `python scripts/governance.py --help`. Minimal flow:

```sh
python scripts/governance.py start --id TASK-20261122-001 --title "Example change" --objective "Observable user outcome" --class docs --requirements GOVAI-002 --files docs/example.md docs/project/status.md docs/project/changelog.md
python scripts/governance.py update --section review --summary "Read status, decisions, impacted code and tests" --files docs/project/status.md
python scripts/governance.py advance --to plan
python scripts/governance.py update --section plan --summary "Implementation, acceptance, rollback, risks" --files docs/example.md
python scripts/governance.py advance --to implement
# Inspect and change only permitted files.
python scripts/governance.py update --section implementation --summary "What actually changed" --files docs/example.md
python scripts/governance.py advance --to validate
python scripts/governance.py run-check --name foundation
python scripts/governance.py update --section validation --summary "Measured results and limitations"
python scripts/governance.py advance --to document
# Update status/changelog and any source-of-truth records impacted by the change.
python scripts/governance.py update --section documentation --summary "Reconciled project record" --files docs/project/status.md docs/project/changelog.md
# Re-run named checks after any scoped documentation files change.
python scripts/governance.py run-check --name foundation
python scripts/governance.py advance --to handoff
python scripts/governance.py handoff --next "Concrete next action and prerequisites" --unresolved "Remaining gaps or none"
python scripts/governance.py finish
```

This flow is an example; do not create the example task unless doing that work.
`amend --section validation --summary "..." --reason "..."` records later corrections to an earlier stage instead of silently replacing history. `advance` never confers owner authorization. Record new owner choices separately
in the [decision register](../project/decision-register.md); an AI suggestion or
proposed ADR is not owner approval.

## Recovery after interruption

Run `brief` again. The active task and every section entry survive independently
of the model's context. If stopped or blocked, use `park --reason ... --next ...`;
`resume --id ...` later continues the same record. A fresh agent must verify
any *uncommitted* code state and execution environment before acting on recorded
progress. Do not overwrite another active worktree or infer a test result from a handoff.

## Limits of enforcement

Python/CI can check structure, document presence, path traceability, command exit
codes and recorded task coverage. They cannot prove semantic correctness,
authorization authenticity, live provider freshness, or agent honesty. The
[implementation guide](README.md) explains installing global rules and branch protection.
