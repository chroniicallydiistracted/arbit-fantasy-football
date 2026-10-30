# ADR-001: Modular runtime with React and Python

Status: Proposed · 2026-10-30 · Owner: architecture proposal; adoption pending.

## Context

One family league needs rich web interactions plus substantial nflverse data/statistical work. Owner wants a portable, local-first proposal; no existing runtime constrains the choice.

## Decision

Recommend React/TypeScript SPA with Vite, Python FastAPI API and worker processes sharing a modular core/data/model library set, PostgreSQL and file/object storage. Use pnpm and uv native workspaces with one lockfile per ecosystem; Make is optional orchestration. No Nx, microservice broker, Kubernetes or LLM dependency initially.

## Alternatives and consequences

Next.js or another React framework provides routing/SSR conventions, but still requires Python analytical jobs and a second server responsibility. A TypeScript API plus Python model service creates more contracts/deployment units now. An all-Python UI reduces web flexibility for dense comparisons/field interactions. SPA choice explicitly takes ownership of routing/data/error/loading behaviors; it is not an assertion that frameworks cannot statically deploy.

## Adoption and evidence

Record architecture review and adopt before runtime installation. Pin Node 24 LTS target, Python 3.12 baseline, package manager/dependency/image versions after compatibility checks. Prove local API/worker/DB path and generate contracts before feature work. Related: ENG-001/002, OWN-003; [system architecture](../system-architecture.md).
