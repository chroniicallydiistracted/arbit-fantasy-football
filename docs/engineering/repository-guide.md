# Repository and Workspace Guide

## Current versus planned contents

This is a documentation-first scaffold. Responsibility READMEs reserve coherent runtime locations; they do not claim a running app. Current executable tooling is the Python-standard-library foundation validator. JSON schemas/examples and design tokens are initial reviewable contracts. Product dependencies, package manifests, migrations, generated API types and application runtime are added by the first implementation slices, with exact versions and frozen lockfiles.

| Path | Responsibility |
| --- | --- |
| `README.md`, `AGENTS.md`, `CLAUDE.md` | Product entry, vendor-independent developer rules, provider pointer |
| `config/league.json` | Confirmed FFA provider ID/season/local-first preference; no inferred scoring defaults |
| `docs/product/` | Unmodified brief, formal product/feature specs, stable requirement registry |
| `docs/architecture/` | System/data/API/model specs and proposed/accepted ADRs |
| `docs/design/` | Visual/interaction/responsive/accessibility standards |
| `docs/engineering/` | Workflow, conventions, checks, security/operations, templates |
| `docs/project/` | Status, roadmap, decisions, issues, changelog and dated handoffs |
| `docs/research/` | Dated source evidence, probes and future validation work |
| `docs/superpowers/` | Composite foundation design and first concrete implementation plan |
| `apps/web/` | Planned React client routes, components and PWA lifecycle |
| `services/api/` | Planned API/auth/authorization/generated OpenAPI/SSE |
| `services/worker/` | Planned scheduling, ingestion/model work and jobs |
| `libs/arbit-core/` | Planned shared domain identity/rules/scoring/eligibility |
| `libs/arbit-data/` | Planned adapters/reconciliation/snapshots/manifests/persistence |
| `libs/arbit-model/` | Planned features/projections/evaluation/archetypes/advisor policies |
| `packages/contracts/` | Initial local JSON schemas; generated client/OpenAPI added with API |
| `packages/design-tokens/` | Initial machine-readable semantic visual tokens and tested contrast pairs |
| `tests/fixtures/` | Clearly synthetic contract examples; sanitized provider fixtures added later |
| `scripts/` | Foundation validation; add actual local tools rather than undocumented one-off commands |
| `infra/` | Deployment boundaries/runbook; real Compose/container configs added with runtime |
| `.github/workflows/` | Foundation check, no deployment or access to private provider credentials |

## Dependency direction and boundaries

Core imports no data/model/service/provider module. Data imports core; Model imports core and normalized data contracts, not HTTP provider response types. API/worker compose these modules. Web imports public generated contracts and tokens; no Python/provider/secret dependency. Advisors are policy modules under the shared Model ownership and use core constraints; Front Office composes their outputs. Feature UI can be lazy-loaded by route.

Use one pnpm JS workspace and one uv Python workspace if the proposal is adopted. Internal JS packages initially export source; no independent publication workflow is needed. Python library directories use distributable import packages under `src/` at bootstrap. No root `package.json` or Python runtime `pyproject.toml` exists yet because no product dependencies have been chosen or installed. Do not add artificial build/test targets that pass without executing real checks.

## Local tasks

`python3 scripts/validate_foundation.py` works now. `make check` is optional shorthand. Follow [M1a plan](../superpowers/plans/2026-10-30-data-foundation.md) to add real local API/worker/PostgreSQL/contract tooling. Data downloads go in ignored local storage with manifest references; approved fixtures are small and sanitized. Keep `.env.example` empty of secrets; supply local runtime secrets only through ignored configuration.

## Source control and publication

Repository initialization is local only; there is no configured remote, hosted CI run or deployment. No commit is required merely to review the proposals. When implementation starts, use small traceable commits and task/handoff records. Root `.gitignore` excludes credentials, caches, build outputs, local data and model artifacts. Add any future licensing/distribution choice explicitly; the owner has not selected an open-source license.
