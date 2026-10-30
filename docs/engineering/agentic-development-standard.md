# Arbit Agentic Development Standard

Version 0.1 · 2026-10-30 · Applies to every human or AI contributor, independent of model vendor.

## Authority and continuity

Order: owner's explicit current instructions → original product intent and recorded owner decisions → accepted ADRs/specifications → this standard → task plans/local conventions. A proposed architectural choice is not an accepted decision. Log conflicts and resolve material product differences with the owner. Session context can explain a decision but cannot substitute for a persistent record.

The repository is the durable engineering memory. [AGENTS.md](../../AGENTS.md) is the entry point; [status](../project/status.md) names the current phase/active work; [roadmap](../project/roadmap.md) holds dependencies; [requirements](../product/requirements.json) names obligations; [decision register](../project/decision-register.md) holds assumptions and owner inputs; ADRs record why; research holds source/date/evidence; handoffs carry exact verification and next actions. `CLAUDE.md` points to AGENTS.md to avoid conflicting provider-specific instructions. New provider entry points must do the same.

## Review → Plan → Implement → Validate → Document → Handoff

| Gate | Required evidence | Proceed when |
| --- | --- | --- |
| Review | Relevant requirement IDs/specs/ADRs, affected source and tests, current status/handoff, baseline working-tree state | No unresolved contradiction affects the task |
| Plan | Small objective, affected files/interfaces, dependencies, validation and acceptance, risks/rollback | Task fits authorized scope; material new choices recorded |
| Implement | Focused changes following ownership/dependency rules; behavioral repro or meaningful test when appropriate | No silent contract/scope change or unrelated edits |
| Validate | Actual commands/results; unit/integration/contract/browser checks appropriate to change; failed/skipped evidence stated | Required checks pass, or remaining issue is explicitly unresolved and work is not marked done |
| Document | Specs/contracts/ADRs/status/known issues/changelog changed where behavior or context changed | Documentation reflects what exists, not what was hoped for |
| Handoff | Completed scope, evidence, files/decisions, unresolved questions, next executable task, limitations | Another contributor can resume without chat memory |

Gates are evidence requirements, not six permission prompts. Prior authorization continues to apply. Routine reversible fixes, documentation updates, local checks and scoped scaffolding do not require repeated approval. Owner confirmation is needed for product scope changes, unapproved spending, external publication or actions beyond authorized access. Do the reviewable local preparation first.

## Planning and task records

Use [task template](task-template.md) for each meaningful implementation slice. Include exact interfaces where later work relies on them; list requirement IDs and acceptance fixtures. Separate product completeness from partial milestones. Define dependencies and a safe fallback for uncertain providers. Tasks can use synthetic data while access is unresolved, but synthetic evidence never proves the actual integration.

Parallel contributors, if explicitly requested, receive non-overlapping file ownership and shared interface contracts; integration owner verifies combined changes. Do not create user-facing chats just to split engineering work. Record concurrent work in status and respect existing edits. Rebase/merge/commit only within current authorization; avoid rewriting shared history.

## Coding and module conventions

Owner-approved runtime conventions; Python tooling/lockfiles are implemented at M1a, web tooling follows with the UI slice: strict TypeScript in the client, Pydantic boundary validation, Python type annotations, Ruff formatting/linting, a Python type checker, ESLint/TypeScript checks, Vitest/component tests and pytest for core/data/model. Generated OpenAPI types carry a do-not-edit banner. Choose one formatting/lint configuration and record exact commands; don't list aspirational commands as available.

Name domain concepts consistently with the glossary/contracts: NFL `athlete` and `nfl_team`, team `defense_unit`, FFA `fantasy_team`, `league_snapshot`, rule version and scoring/matchup periods. Keep scoring/rules pure and deterministic. Use Decimal for exact contributions. Provider adapters parse once into canonical contracts; feature modules cannot import raw provider payload types. No hardcoded league scoring defaults or stat-ID mappings without tested provenance.

Validate all external/network/file boundaries. Set timeouts and size bounds, retry only appropriate errors, and preserve typed failure states. Log safe request/run IDs rather than secret/raw objects. Avoid generic exceptions that hide failed syncs. Keep browser bundles free from private configuration. Add migrations for schema changes; never edit an applied migration. Job completion and publication use transaction/idempotency semantics documented in data architecture.

Keep feature-specific code together, with small focused functions and explicit dependencies. Introduce abstraction for demonstrated shared behavior, especially identity/scoring/evaluation; don't create frameworks speculatively. Avoid one giant dashboard component, one giant adapter or one giant model notebook. Exploration notebooks, if added, export reproducible code/data manifests before serving production output.

## Modification boundaries

Do not change the unaltered brief, live provider state, credentials, actual commissioner settings, private production data, or published historical results without explicit scope. Never commit raw private responses, secrets, model datasets, dependency directories or generated binaries. Record intentional regenerated contracts/tokens with their generator/version. Do not disable failing checks to make a gate pass. Destructive migrations, data deletion, alias merges and final-record corrections need a reviewed plan and recovery path; user authorization governs the action.

## Verification and release

[Validation guide](validation.md) maps change type to evidence. Source calls are opt-in smoke checks outside deterministic CI. Data/model changes need point-in-time lineage, coverage and failure-path checks. UI changes need keyboard/reflow/error states. Small documentation changes do not need product tests. Feature completion requires user-visible behavior and useful failures, not only passing unit tests.

PRs, if requested, lead with the problem/result and include affected requirements, verification and material limits. Every release records build/code/lock/schema/model/rules versions and migration compatibility, then uses the security/operations runbook. No automatic deploy or external messaging is authorized by this standard itself.

## Completion, uncertainty and handoff

Statuses are proposed, specified, in progress, implemented, verified, or blocked with a concrete prerequisite. Never equate an implemented adapter with proven full FFA coverage, or a trained model with useful advice. A source gap has an owner, evidence, impact, next experiment and milestone. Proposed performance budgets are separate from measurements.

At session end: update [status](../project/status.md), [changelog](../project/changelog.md), applicable ADR/research/issues and a dated handoff using [handoff template](handoff-template.md). The handoff records exact commands/exit status, not “tested successfully” without evidence. Report any external state changed and any command unavailable in the environment. A fresh agent should be able to choose the next task within ten minutes using repository documents alone.
