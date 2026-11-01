# Repository and Workspace Guide

## Current versus planned contents

M1a implements the Python runtime/core/persistence/health slice with native workspaces, frozen lockfiles, migration and real checks. M1b adds all audited public ESPN routes and manual inspection, with the ignored reference checkout under `.references`. M1c maps/reconciles actual FFA scoring and durably publishes canonical identities/rules/full facts with protected local reads. M1d adds full NFLverse acquisition/storage/manifests, source proofs, exact GSIS/ESPN joins and source-stat reads. M1e adds cached supplemental observations, scoped NFL play contracts/offline replay and asset prerequisite metadata without media acquisition. M2 adds implemented member auth/API/administrator controls and the React Front Office/PWA. Model features remain future work. Generated member contracts and semantic tokens are executable client inputs. [Local development](local-development.md) describes runnable commands.

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
| `apps/web/` | Implemented member shell, Front Office, text-first Live scoreboard and plays, player drawer, watchlist, preferences, device sessions, admin controls and static-only PWA; other workspaces state they aren't built |
| `services/api/` | Health/operator reads, invite/OIDC/session/binding/member/admin facts, live reads and the SSE event stream |
| `services/worker/` | Supervised sync daemon (`arbit-worker run`), durable FFA sync, NFLverse ingestion, safe inspection/replay commands; model jobs remain planned |
| `libs/arbit-core/` | Shared exact scoring, domain identities and league contracts; optimization remains planned |
| `libs/arbit-data/` | Provider acquisition/normalization, immutable objects/manifests, source proofs, crosswalks and canonical persistence |
| `libs/arbit-model/` | Planned features/projections/evaluation/archetypes/advisor policies |
| `packages/contracts/` | JSON schemas and generated private member OpenAPI/TypeScript source |
| `packages/design-tokens/` | Implemented semantic visual/typography tokens, generated CSS and contrast checks |
| `tests/fixtures/` | Clearly synthetic contract examples; sanitized provider fixtures added later |
| `scripts/` | Foundation validation; add actual local tools rather than undocumented one-off commands |
| `infra/` | Pinned local PostgreSQL Compose configuration and systemd user units; external deployment remains planned |
| `.github/workflows/` | Foundation and isolated PostgreSQL runtime checks; no deployment or private provider credentials |

## Dependency direction and boundaries

Core imports no data/model/service/provider module. Data imports core; Model imports core and normalized data contracts, not HTTP provider response types. API/worker compose these modules. Web imports public generated contracts and tokens; no Python/provider/secret dependency. Advisors are policy modules under the shared Model ownership and use core constraints; Front Office composes their outputs. Feature UI can be lazy-loaded by route.

Use one pnpm JS workspace and one uv Python workspace as adopted by the owner. Internal JS packages initially export source; no independent publication workflow is needed. Python library directories use distributable import packages under `src/` at bootstrap. Root/member package manifests and pnpm/uv lockfiles now define the runtime; pure core/data libraries and service imports are installed from the workspace. Do not add artificial build/test targets that pass without executing real checks.

## Local tasks

`python3 scripts/validate_foundation.py` and `make check` verify artifacts; `make runtime-check` adds lint/types/contracts and PostgreSQL-backed tests. Follow [M1a plan](../superpowers/plans/2026-10-30-data-foundation.md) to add real local API/worker/PostgreSQL/contract tooling. Data downloads go in ignored local storage with manifest references; approved fixtures are small and sanitized. Keep `.env.example` empty of secrets; supply local runtime secrets only through ignored configuration.

## Source control and publication

The owner published the initialized repository and pushed baseline commit `cab6bd8` to main. Current development is on `claude/platform-reset`; no branch push, merge or deployment is implied by local development. No commit is required merely to review the proposals. When implementation starts, use small traceable commits and task/handoff records. Root `.gitignore` excludes credentials, caches, build outputs, local data and model artifacts. Add any future licensing/distribution choice explicitly; the owner has not selected an open-source license.
