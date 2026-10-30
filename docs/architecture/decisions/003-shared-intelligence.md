# ADR-003: One scoring and intelligence foundation

Status: Proposed · 2026-10-30 · Adoption pending.

## Context

The brief requires deep nflverse-driven analysis reused across Draft/Scout/Lineup/Market. FFA rules are currently unverified; inaugural league history cannot justify learned acceptance probabilities.

## Decision

A pure core service computes exact Decimal fantasy scoring under versioned imported rules. Unknown categories block affected advice. Shared point-in-time features and projection distributions feed advisor policies with one lineage contract. Start with evaluated interpretable baselines, then promote ML only against predeclared temporal holdout/subgroup/calibration gates. Draft availability priors and trade feasibility disclose uncertainty; numerical acceptance requires genuine labeled evidence.

## Alternatives and consequences

Platform projections or per-feature scoring/rankings create incoherent advice and do not meet product depth. Complex ML without temporal validation creates confident leakage. Shared models reduce drift but require invalidation, manifest retention and explicit horizons. Some outputs must abstain until data/rules are sufficient; this is better evidence discipline, not a reduction in final feature scope.

## Evidence

M1 supported-rule reconciliation; M3 reproducible model/backtest release; M4 legal optimizer; M5 calibrated or labeled scenario/feasibility policies. Related: DATA-007, MD-001–004, DR-004, TR-003; [Model specification](../model-specification.md).
