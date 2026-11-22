# Context Governance System (CGS) v1

A repo-native continuity system that extends Arbit's existing rich documentation,
without overwriting the original brief, product requirement registry, accepted
ADRs, data sources, or implementing unfinished product features.

## Components

- `~/.codex/AGENTS.md` global template, root `AGENTS.md` and scoped module AGENTS: instructions, not a security guarantee.
- `~/.claude/CLAUDE.md` global template, root `CLAUDE.md`, `.claude/rules/` and `.claude/settings.json`: Claude-specific loading and reminders.
- [START_HERE](START_HERE.md), [authority matrix](SOURCE_OF_TRUTH.md), [repository map](REPO_MAP.md), [source audit](AUDIT_2026-11-22.md), [requirements](requirements.json), [role charter](FANTASY_ADVISOR_CHARTER.md), [change gates](change-gates.json) and [pinned check commands](check-commands.json): durable policies.
- `state.json` and `tasks/*.json`: one active task, durable objective, sources, findings, steps, evidence, exceptions and next action; `park` stores unresolved work.
- `scripts/governance.py`: `brief`, `doctor`, `start`, `update`, `note`, `advance`, `run-check`, `handoff`, `park`, `resume`, `finish`, `diff-gate`.
- `scripts/governance_hook.py`: Claude session-start context and stop reminder only. It does **not** silently block unrelated conversations, publish code or prove completion.
- `.github/workflows/context-governance.yml`: deterministic structural/CLI unit checks plus PR changed-file-to-task traceability. Use required branch protection to make this gate mandatory.

## Install global guidance (not executed automatically)

Run `python scripts/install_global_instructions.py --dry-run` then `--apply` to
copy the templates into Codex/Claude user-level instruction locations. The
installer refuses to overwrite existing files unless given `--replace`, in which
case it creates timestamped backups. Reopen the tools to load changed instructions.
This repository's rules still work without global installation.

## Enforcement coverage and threat model

**Hard-gated:** task schema, ordered stage progression, designated files and explicitly declared deletions,
unique requirement IDs, linked documents, successful named test commands using pinned command profiles,
rejected stale file fingerprints on finish, complete handoff, PR changed-file
coverage when CI runs, and preservation of approved policy documents.

**Human or privileged-gated:** correctness of all recommendations and data,
provenance honesty, genuine owner authorization, accidental live-service access,
external publications, workspace dirty state, and validity of reported manual
observations. No locally editable script prevents a user with repository write
access from bypassing the checks. Protect `main`, require review and make CI
checks mandatory. Confirm real service state before any release.

**Do not store:** member tokens, OAuth secrets, raw private ESPN data, private
sources, provider credentials, or unredacted logs in governance records.
`run-check` stores argv, status, timestamp, duration, output digest and hashed
scoped files, not stdout/stderr. If the command contains secrets in CLI args,
it is inappropriate for this recorder.

## Existing-document integration

Keep [project status](../project/status.md), [known issues](../project/known-issues.md), [changelog](../project/changelog.md), [existing handoffs](../project/handoffs/) and [ADRs](../architecture/decisions/README.md) as their existing authoritative stores.
Task records point to those instead of re-writing facts into many inconsistent files.
The per-project `state.json` is a navigation pointer, not an alternative model
or deployment truth ledger.
