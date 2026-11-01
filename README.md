# Arbit

**FFA Fantasy Football Companion** — a league-aware football intelligence platform for the Family Football Association.

## Current state

FFA is ESPN league **1729878439**, season **2026**. The owner approved the architecture/stack; deployment remains portable and local-first.

**M2 is implemented locally:** invited Google-compatible sign-in, opaque sessions, administrator-approved FFA team binding, Front Office saved facts, player drawer/search, watchlist/themes, administrator access controls and a static-only PWA. Start with [member application operations](docs/engineering/member-application.md) and the [M2 handoff](docs/project/handoffs/2026-10-31-member-application.md). Google is selected; private client configuration and a real invited member/team round trip remain the operational release gate. No external service or deployment was created.

M1 foundations remain verified: [all 68 usable ESPN audit variants](docs/research/espn-endpoint-coverage-2026-10-30.md) across 19 route families; all 46 actual FFA scoring definitions, 797 played player-games and 56 lineup totals reconciled; [durable canonical FFA sync](docs/engineering/ffa-synchronization.md); and [all 1,140 NFLverse files](docs/engineering/nflverse-ingestion.md) across 28 families, including 11,973,952 stored rows. All 121 owned athletes map exactly to GSIS; two lack observed weekly rows. [Research register](docs/research/source-register.md) records provenance and coverage limits.

ESPN remains league authority, NFLverse the statistical foundation. Sleeper is eligible only for verified relevant NFL live-game/PBP; all former fantasy/hint paths are retired and no eligible Sleeper live route is enabled. [M1e research](docs/research/m1e-source-audit-2026-10-31.md) remains historical evidence. Gridiron media still needs exact variants and reuse permission. Message boards are out of scope. No model or recommendation is enabled.

## Start here

| Deliverable | Authoritative document |
| --- | --- |
| Product specification | [Product specification](docs/product/product-specification.md) and [feature experiences](docs/product/feature-experiences.md) |
| Architecture specification | [System architecture](docs/architecture/system-architecture.md) |
| Data architecture specification | [Data architecture](docs/architecture/data-architecture.md) and [API contracts](docs/architecture/api-contracts.md) |
| Design system specification | [Design system](docs/design/design-system.md) |
| Agentic development standard | [Development standard](docs/engineering/agentic-development-standard.md) and [AGENTS.md](AGENTS.md) |
| Implementation roadmap | [Roadmap](docs/project/roadmap.md) and [first implementation plan](docs/superpowers/plans/2026-10-30-data-foundation.md) |
| Repository and workspace scaffold | [Repository guide](docs/engineering/repository-guide.md) |

The [unaltered owner brief](docs/product/vision-source.txt) remains the source of product intent. [Requirement traceability](docs/product/requirements.md) preserves its scope. Start a new development session with [project status](docs/project/status.md), [decisions and unknowns](docs/project/decision-register.md), and the [latest handoff](docs/project/handoffs/2026-10-31-supplemental-live.md).

## Verify the foundation and runtime

Requires Python 3.12 or later; no third-party packages or network access:

```sh
python3 scripts/validate_foundation.py
```

`make check` runs the same check if Make is available. For runtime checks, install frozen dependencies, run `make db-up`, then `make runtime-check`; see the local development guide. The check verifies document paths, required deliverables, requirement coverage, configuration, JSON contract examples, and design-token contrast. It does not validate provider availability, model quality, authentication, or an application build. CI includes the foundation check and a separate PostgreSQL-backed runtime workflow.

## Runtime layout

```text
apps/web/           React and TypeScript desktop/PWA client
services/api/       FastAPI HTTP, sessions, authorization, SSE
services/worker/    Ingestion, synchronization, features, model jobs
libs/arbit-core/    Canonical identity, league rules, scoring, eligibility
libs/arbit-data/    Provider adapters, normalization, data lineage
libs/arbit-model/   Features, projections, evaluation, recommendations
packages/          API schemas and design tokens
infra/             Local and deployment configuration, added with runtime
```

The Python services/core/data libraries and native workspaces now contain the verified runtime and canonical FFA synchronization slices; the web application now implements M2; analytical Model features remain future work. No Nx dependency is selected for this small mixed-language workspace.

Provider capabilities and limitations are recorded with sources in the [research register](docs/research/source-register.md). Do not put ESPN cookies, passwords, raw league-member data, or downloaded datasets in Git.
