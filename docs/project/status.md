# Project Status

Updated **2026-10-30**. Phase: **M1 data/runtime foundation**.

## Confirmed context

FFA ESPN league **1729878439**, season **2026**. Owner approved the architecture/stack and additional dependencies, especially UX/UI. Deployment remains portable and local-first. High-quality, deliberate product design and engineering are required. Owner authorized development using the verified public FFA access and excluded message boards from product scope. Exact owner Gridiron asset links are still unavailable.

## Current implementation

M1a is implemented: pinned native Python/JS workspaces, exact scoring and temporal identity, PostgreSQL migration/snapshot/outbox persistence, fenced durable jobs, guarded synthetic worker path and health-only API. See [local development](../engineering/local-development.md) for reproducible commands. Runtime verification currently has **110 passing tests**, including real PostgreSQL integration, plus Ruff/strict mypy/AJV/artifact checks. M1a review fixes remain covered; M1b independent review found two Important transport issues, both fixed with RED→GREEN HTTP regressions; no findings remain deferred.

M1b implements the public transport, observed league/player contracts, bounded complete pagination, ownership/context checks and `arbit-worker espn-inspect`. A fresh live read returned eight teams, 132 owned, 923 available, 46 scoring items, 128 picks and 56 matchups through seven cookie-free GETs. [Reader receipt](../research/espn-reader-live-2026-10-30.json). The pinned reference checkout is available under ignored `.references`.

No frontend UI, durable canonical FFA sync, member authentication, persisted cross-provider mappings, football model or deployment exists yet. Arbit scoring tests still use synthetic rules; actual rule normalization/reconciliation remains open. The earlier private-setting 401 is historical; current settings requests return 200 without cookies, and message-board availability is outside product scope. See the [full audit](../research/espn-public-api-audit-2026-10-30.md).

## Milestones

| Milestone | State |
| --- | --- |
| M0 foundation | Delivered; architecture/stack accepted by owner |
| M1a runtime/core/snapshot | Implemented, reviewed and locally verified |
| M1b FFA access/capability inventory | Typed public reader/manual inspection implemented and live-verified; canonical production sync remains |
| M1c–e normalization/crosswalks/statistical sources | Planned |
| M2 application/auth/Front Office/PWA | Not started |
| M3 Model/Scout | Not started |
| M4 Lineup/waivers | Not started |
| M5 trade/Draft | Not started |
| M6 Live | Not started |
| M7 Archive/refinement | Not started |

## Repository and verification

Owner published baseline commit `cab6bd8` on main. Current work: local branch `codex/m1b-public-espn`; no new push, merge or deployment. Aggregate validation: `make runtime-check` after frozen installs and `make db-up`. On this host use the pinned npm-exec workaround in the development guide if Corepack is misconfigured. Local PostgreSQL service remains available; HTTP smoke process has been stopped.

Latest [reader handoff](handoffs/2026-10-30-public-reader.md) records this slice; [public API handoff](handoffs/2026-10-30-espn-public.md) records the earlier 81-probe audit. [M1a handoff](handoffs/2026-10-30-m1a.md) records runtime tests, code scope, environment adaptations and review results. [Initial foundation handoff](handoffs/2026-10-30-foundation.md) is historical. [Roadmap](roadmap.md), [decisions](decision-register.md), [known issues](known-issues.md), [research](../research/source-register.md) and [changelog](changelog.md) preserve continuity.
