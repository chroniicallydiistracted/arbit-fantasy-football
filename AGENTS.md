# Arbit agent entry point

Arbit is the FFA Fantasy Football Companion for ESPN league **1729878439**, season **2026**. The owner brief is authoritative; M1a runtime/core/persistence/health behavior is implemented; the frontend, real FFA ingestion, authentication and models remain future work. Deployment preference: portable and local-first.

## Read before changing work

1. [README](README.md), [current status](docs/project/status.md), and [latest handoff](docs/project/handoffs/2026-10-30-espn-public.md).
2. [Requirement registry](docs/product/requirements.md), affected [feature experience](docs/product/feature-experiences.md), and applicable architecture/design documents.
3. [Decision register](docs/project/decision-register.md), [ADRs](docs/architecture/decisions/README.md), [research](docs/research/source-register.md), and [development standard](docs/engineering/agentic-development-standard.md).
4. The active implementation plan and existing affected code, once code exists. Chat history is not authoritative project memory.

## Non-negotiable project invariants

- Single FFA league, annual redraft; do not add tenancy or a second league provider. Never guess PPR, roster slots, draft structure, waiver rules or first-season history.
- ESPN is league authority; nflverse is the primary statistical foundation. Sleeper is supplemental. Gridiron assets require verified variants and reuse permission.
- Shared identity, scoring, eligibility and versioned player evaluations serve all modules. No advisor or client duplicates provider parsing or fantasy arithmetic.
- Unknown data is not zero. Unknown rules/identity or stale ownership must limit or block affected advice explicitly. Official ESPN totals, live estimates and model projections are visibly distinct.
- Preserve point-in-time lineage and corrections. No future information in a model backtest, fabricated route tracking, or unsupported numerical acceptance probability.
- All ESPN interactions are read-only in the initial scope. Credentials remain server-side and outside source, fixtures, logs and browser bundles.
- Architecture/stack were approved on 2026-10-30. Additional development dependencies are authorized, especially UX/UI. Preserve deliberate, high-quality product design and engineering; generic dashboard filler is not acceptable. Do not report fixtures or documentation as a shipped feature.

## Work and validation

Follow Review → Plan → Implement → Validate → Document → Handoff. A plan names affected requirement IDs, files, interfaces and evidence. Use meaningful focused tests for behavioral changes; documentation/token changes use the foundation validator. Do not add redundant tests that merely repeat implementation. Use approved scope and judgment for routine reversible changes; gates require evidence, not repeated user permission. Ask before changing product scope or provisioning/publishing services without prior authorization.

Current executable check:

```sh
python3 scripts/validate_foundation.py
```

Runtime check: `make runtime-check` after frozen installs and `make db-up`; see [local development](docs/engineering/local-development.md). The first slice is backend-only; frontend build targets do not exist yet. Never fabricate a successful build or use private provider calls as mandatory CI tests.

Before handoff update status, changelog, decision/issue records as relevant, and a dated handoff with actual commands/results and remaining work. Make uncertainties actionable by naming the milestone they block. Keep the source brief unchanged; record interpretations in specifications/ADRs. Never overwrite another agent's work or claim it as verified without reading the diff and evidence.
