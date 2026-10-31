# Arbit

**FFA Fantasy Football Companion** — a league-aware football intelligence platform for the Family Football Association.

## Current state

Architecture and the recommended stack were approved by the owner on 2026-10-30. **M1a runtime/core/snapshot foundation is implemented:** pinned workspaces, exact scoring, temporal identity resolution, PostgreSQL migrations/snapshots/outbox, durable job leases, a guarded synthetic worker path and health-only API. FFA is ESPN league **1729878439**, season **2026**. Deployment preference: portable and local-first.

Public ESPN access is now verified by an [81-probe capability audit](docs/research/espn-public-api-audit-2026-10-30.md); a typed public reader and safe `uv run arbit-worker espn-inspect` command are now implemented and live-verified. All 68 recognized successful audit variants across 19 route families are wired and live-verified; see [coverage](docs/research/espn-endpoint-coverage-2026-10-30.md). Canonical production synchronization remains future work. Message boards are outside scope. The audited reference is cloned under ignored `.references`; see [provenance](docs/research/espn-reference.md). No frontend UI, member authentication or trained model exists yet. The owner authorizes additional dependencies, especially UX/UI, and requires deliberate, high-quality design and engineering. Begin with the [local development guide](docs/engineering/local-development.md) for installation, tests and the synthetic smoke path.

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

The [unaltered owner brief](docs/product/vision-source.txt) remains the source of product intent. [Requirement traceability](docs/product/requirements.md) preserves its scope. Start a new development session with [project status](docs/project/status.md), [decisions and unknowns](docs/project/decision-register.md), and the [latest handoff](docs/project/handoffs/2026-10-30-endpoint-coverage.md).

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

The Python services/core/data libraries and native workspaces now contain the first runtime slice; the web and analytical Model directories remain future work. No Nx dependency is selected for this small mixed-language workspace.

Provider capabilities and limitations are recorded with sources in the [research register](docs/research/source-register.md). Do not put ESPN cookies, passwords, raw league-member data, or downloaded datasets in Git.
