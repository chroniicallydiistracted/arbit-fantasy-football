# ADR-002: Versioned data and canonical aliases

Status: Proposed · 2026-10-30 · Adoption pending.

## Context

ESPN, nflverse and Sleeper use different identifiers, timestamps, statistical grains and correction semantics. A player changing NFL teams is not a new person; a fantasy D/ST is not an athlete.

## Decision

PostgreSQL stores transactional league/user/history and serving state; immutable manifests and versioned Parquet/files hold raw/statistical/model inputs. Canonical UUID entities use dated provider aliases. Atomic complete league snapshots and rule hashes pin advisor inputs. Unknown identity stays unresolved instead of name-only merging. Historical outputs retain observation-time versions.

## Alternatives and consequences

One PostgreSQL table for every PBP feature would mix serving and bulk analytics needs. Files alone do not provide authorization, snapshot pointer and job transaction semantics. Using an ESPN ID as universal identity couples analysis to one provider and complicates D/ST/team changes. Dual storage adds manifest/backup discipline; reproducibility and adapter boundaries justify it.

## Evidence

M1 must prove completeness/pagination, alias uniqueness, ambiguous-name handling, duplicate snapshot replay, correction publication, manifest checksums and restore semantics. Related: DATA-001/002/005/006; [data architecture](../data-architecture.md).
