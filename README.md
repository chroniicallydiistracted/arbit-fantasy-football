# Arbit

**FFA Fantasy Football Companion** — a league-aware football intelligence platform for the Family Football Association.

## Current state

The initial planning foundation and documentation scaffold are present. There is no running application, installed product dependency, connected private ESPN session, or trained model. The architecture and design choices below are **proposed**, not owner-approved or implemented. FFA is ESPN league **1729878439**, season **2026**. Deployment preference: portable and local-first.

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

The [unaltered owner brief](docs/product/vision-source.txt) remains the source of product intent. [Requirement traceability](docs/product/requirements.md) preserves its scope. Start a new development session with [project status](docs/project/status.md), [decisions and unknowns](docs/project/decision-register.md), and the [latest handoff](docs/project/handoffs/2026-10-30-foundation.md).

## Verify the foundation

Requires Python 3.12 or later; no third-party packages or network access:

```sh
python3 scripts/validate_foundation.py
```

`make check` runs the same check if Make is available. The check verifies document paths, required deliverables, requirement coverage, configuration, JSON contract examples, and design-token contrast. It does not validate provider availability, model quality, authentication, or an application build. CI runs the same foundation check.

## Proposed runtime layout

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

These directories contain responsibility guides rather than pretend implementations. Start with the roadmap's M1 provider/scoring proof, then generate runtime projects using the selected versions and commit their lockfiles. No Nx dependency is selected for this small mixed-language workspace.

Provider capabilities and limitations are recorded with sources in the [research register](docs/research/source-register.md). Do not put ESPN cookies, passwords, raw league-member data, or downloaded datasets in Git.
