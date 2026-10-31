# Decisions, Inputs and Open Questions

Updated 2026-10-30. Architecture and recommended stack approved by the owner on 2026-10-30; additional development dependencies are authorized, especially for UX/UI work.

## Confirmed product decisions

| ID | Decision | Evidence |
| --- | --- | --- |
| OWN-001 | Arbit, FFA companion, Front Office headquarters, eight-capability family, one redraft league | Owner brief v1.0 |
| OWN-002 | ESPN league ID `1729878439`, season `2026` | Owner reply 2026-10-30 |
| OWN-003 | Portable, local-first proposal | Owner reply 2026-10-30 |
| OWN-004 | Owner's prior Gridiron direct asset URL patterns are not yet available | Owner reply 2026-10-30 |
| OWN-007 | Owner made FFA public, reviewed the successful API audit and authorized development using public access; message boards are not required | Owner request 2026-10-30 |
| OWN-006 | Architecture/stack approved; additional dependencies approved; deliberate, high-quality UX/UI and engineering required | Owner reply 2026-10-30 |
| OWN-005 | nflverse primary statistics; ESPN league truth; Sleeper supplemental; ESPN-first live research | Owner brief §§5–6 |
| OWN-008 | Every successful usable endpoint must be wired before mapping actual FFA rules and verifying ESPN totals; recommendations stay disabled until verification | Owner continuation 2026-10-30 |

## Accepted architecture decisions

| Record | Proposal | Status / adoption point |
| --- | --- | --- |
| [ADR-001](../architecture/decisions/001-modular-runtime.md) | React client + modular Python API/worker, native workspace tools | Accepted by owner 2026-10-30 |
| [ADR-002](../architecture/decisions/002-data-and-identity.md) | PostgreSQL + versioned Parquet, explicit aliases and immutable publication | Accepted; M1 data implementation |
| [ADR-003](../architecture/decisions/003-shared-intelligence.md) | Shared exact scoring and point-in-time evaluated models; no fabricated probabilities | Accepted; M1 scoring and M3 model implementation |
| [ADR-004](../architecture/decisions/004-access-live-and-pwa.md) | Separate invite/OIDC auth, server-only ESPN read access, SSE, static-only PWA caching | Accepted; M1 integration/M2 authentication |

Owner approval adopts these runtime choices. Hosting remains portable/local-first and no paid hosting is provisioned. Exact dependency versions are resolved and locked when the runtime is bootstrapped.

## Open inputs and decision rules

| ID | Missing input / unresolved capability | Impact | Next action and decision owner |
| --- | --- | --- | --- |
| Q-001 | Public source mode authorized for the current development phase; future private visibility is an optional change | Core reads work without cookies; message-board availability has no product impact | Public reader implemented and live-verified; configure and test server-side credentials only if visibility later becomes private |
| Q-002 | Actual settings retrieved; rule/category normalization, membership binding and scoring reconciliation remain | 46 scoring items, OFFLINE draft, actual slots/waivers/locks observed; usable normalized advice still requires validation | M1c mapped all46 rules and reconciled completed weeks; canonical persistence, membership and full eligibility/lock handling remain |
| Q-003 | OIDC provider and invited account roster | Blocks real member sign-in, not data/schema work | Before M2: owner chooses provider/account invite policy; proposal favors maintained OIDC library with server sessions |
| Q-004 | Exact Gridiron asset patterns and reuse/variant verification | Blocks final weekly field/uniform integration | M1 research/M6: owner shares links when available; engineer verifies candidate sites and records permissions/attribution; generic fallback stays labeled |
| Q-005 | nflverse per-dataset coverage and available historical release metadata | Determines usable in-season features and holdout periods | M1: engineer audits manifests/schemas/coverage and publication times; no future features in M3 |
| Q-006 | Sleeper supported scoring/play/game capability beyond public docs | Cannot depend on a supported live feed | M1: engineer records read-only proof if available; use documented metadata/state/trends meanwhile |
| Q-007 | ESPN live endpoint coverage across event types/corrections | Determines exact Live event/graphic fidelity | M1: engineer collects sanitized fixtures and coverage matrix; single final-game observation is insufficient |
| Q-008 | Target host capacity, backup location, budget, domain | Blocks external deployment decisions only | Before external provisioning: owner selects limits; keep local containers and storage portable |
| Q-009 | Empirical FFA draft/trade history and optional ADP source | Limits learned selection/acceptance likelihood | M5: use labeled scenario priors and qualitative feasibility until enough validated data exists |
| Q-010 | Exact first FFA season and archive finalization detail | Limits any imported prior results/Cup entry | M1/M7: confirm source history and actual championship outcome; preserve inaugural-season empty state |

These are milestone prerequisites, not a demand for the owner to answer every question now. Engineering can proceed with contracts, sanitized fixtures and local runtime tasks while the remaining source/model/auth prerequisites are resolved. Material alternatives are documented before changing scope or cost.
