# Project Status

Updated **2026-10-30**. Phase: **M1 data/runtime foundation**.

## Confirmed context

FFA ESPN league **1729878439**, season **2026**. Owner approved the architecture/stack and additional dependencies, especially UX/UI. Deployment remains portable and local-first. High-quality, deliberate product design and engineering are required. Owner temporarily made FFA publicly viewable for the API audit; final access policy is still undecided. Exact owner Gridiron asset links are still unavailable.

## Current implementation

M1a is implemented: pinned native Python/JS workspaces, exact scoring and temporal identity, PostgreSQL migration/snapshot/outbox persistence, fenced durable jobs, guarded synthetic worker path and health-only API. See [local development](../engineering/local-development.md) for reproducible commands. Runtime verification currently has **45 passing tests**, including real PostgreSQL integration, plus Ruff/strict mypy/AJV/artifact checks. Fresh branch review completed; two important isolation/queue findings were fixed with RED→GREEN regressions and no deferred findings.

No frontend UI, real FFA sync, member authentication, persisted cross-provider mappings, football model or deployment exists yet. Actual FFA settings and public read access are now observed: eight teams, 46 scoring items, 128 picks, 132 owned and 923 available players. Arbit scoring tests still use synthetic rules; actual rule normalization/reconciliation remains open. The earlier private-setting 401 is historical; current settings requests return 200 without cookies, while communication remains 401. See the [full audit](../research/espn-public-api-audit-2026-10-30.md).

## Milestones

| Milestone | State |
| --- | --- |
| M0 foundation | Delivered; architecture/stack accepted by owner |
| M1a runtime/core/snapshot | Implemented, reviewed and locally verified |
| M1b FFA access/capability inventory | Public manual audit complete; typed contracts/read adapter and production sync remain |
| M1c–e normalization/crosswalks/statistical sources | Planned |
| M2 application/auth/Front Office/PWA | Not started |
| M3 Model/Scout | Not started |
| M4 Lineup/waivers | Not started |
| M5 trade/Draft | Not started |
| M6 Live | Not started |
| M7 Archive/refinement | Not started |

## Repository and verification

Owner published baseline commit `cab6bd8` on main. Current work: local branch `codex/m1a-foundation`; no new push, merge or deployment. Aggregate validation: `make runtime-check` after frozen installs and `make db-up`. On this host use the pinned npm-exec workaround in the development guide if Corepack is misconfigured. Local PostgreSQL service remains available; HTTP smoke process has been stopped.

Latest [public API handoff](handoffs/2026-10-30-espn-public.md) records the 81-probe audit. [M1a handoff](handoffs/2026-10-30-m1a.md) records runtime tests, code scope, environment adaptations and review results. [Initial foundation handoff](handoffs/2026-10-30-foundation.md) is historical. [Roadmap](roadmap.md), [decisions](decision-register.md), [known issues](known-issues.md), [research](../research/source-register.md) and [changelog](changelog.md) preserve continuity.
