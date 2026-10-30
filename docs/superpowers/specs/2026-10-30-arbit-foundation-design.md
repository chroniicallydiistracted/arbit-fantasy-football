# Arbit Foundation Design

2026-10-30 · Proposed implementation foundation; architecture/design adoption remains pending.

## Intent and owner's decisions

Deliver the seven initial planning artifacts from the [owner brief](../../product/vision-source.txt), retaining the comprehensive fantasy intelligence scope. Owner confirms ESPN league **1729878439**, season **2026**, and a **portable, local-first proposal**. Owner's earlier Gridiron URL patterns are not available yet. No existing application/codebase constrains architecture.

## Full design

The authoritative design is composed of [product specification](../../product/product-specification.md), [feature experiences](../../product/feature-experiences.md), [system architecture](../../architecture/system-architecture.md), [data architecture](../../architecture/data-architecture.md), [API contracts](../../architecture/api-contracts.md), [Model methodology](../../architecture/model-specification.md), and [design system](../../design/design-system.md). [Requirement traceability](../../product/requirements.md) maps every original section and major obligation; the [roadmap](../../project/roadmap.md) preserves advanced scope across dependencies.

Agent calls, marked as proposals: React/Vite TypeScript client; modular FastAPI Python API/worker; PostgreSQL + versioned Parquet; native pnpm/uv workspaces; invite/OIDC member auth separate from ESPN secrets; shared exact scoring/identity/evaluations; correction-aware SSE; static-only PWA caches. [ADRs](../../architecture/decisions/README.md) compare alternatives and consequences. No runtime dependency or paid hosting choice is installed/provisioned by this document scaffold.

## Constraints and anti-goals

One FFA league, no multi-league architecture priorities. ESPN league truth, nflverse analytical foundation, Sleeper supplementary. No simplified static-ranking substitute for the complete requested advisors. No fabricated scoring/rules/history/advanced data/model confidence. No unvalidated numeric trade acceptance, inferred tracking presented as actual routes, or silent stale-ownership advice. No provider transaction submission. No secret in client/source/artifact/log. All outputs preserve canonical identity, rules/snapshot/model versions and observation cutoff.

## What remains to the builder

Choose exact compatible dependency patches and lock them at bootstrap; implement small vertical slices with real tests and source fixtures; measure dataset coverage and resource budgets. OIDC provider and hosting budget remain owner choices at their implementation milestones. Actual FFA metadata awaits authorized local access: unauthenticated settings returned 401. Gridiron candidate sites are not a verified asset integration. These conditions are recorded in the [decision register](../../project/decision-register.md), not hidden assumptions.

## Review and handoff

A fresh builder check reviews this composite design before handoff. Its resolved findings and current verification are recorded in the [foundation handoff](../../project/handoffs/2026-10-30-foundation.md). The [first implementation plan](../plans/2026-10-30-data-foundation.md) covers the initial runtime/core/snapshot slice only; later feature slices receive focused plans rather than pretending every future code detail is settled now.
