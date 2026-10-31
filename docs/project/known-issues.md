# Known Issues and Risks

Updated 2026-10-31. M1a–d data/runtime slices are implemented and locally verified; supplemental/live source, member and full feature/model validation remain open.

| ID | Evidence / risk | Effect and mitigation | Owner / milestone |
| --- | --- | --- | --- |
| R-001 | Historical private-setting 401; current public core reads verified 200 | Public reader implemented and live-verified. Message boards excluded by owner; private credentials only become relevant if visibility changes | Integration / M1 |
| R-002 | Unofficial ESPN endpoints have no service contract | Adapter contracts, bounded polling, drift quarantine, last-complete snapshot, explicit degraded state | Integration / M1/M6 |
| R-003 | nflverse publication/feature coverage differs by dataset and season | Full 1,140-file audit is recorded; no 2026 participation file, FTN charting through week 7, depth timestamps not weeks. Local observation/confirmation is not historical vintage proof; M3 needs an explicit validation policy | Data/Model / M1/M3 |
| R-004 | Sleeper public docs do not prove a supported live scoring/PBP endpoint | Supplemental documented inputs; unproven endpoints cannot be a core dependency | Integration / M1 |
| R-005 | Gridiron exact owner links/asset permission unconfirmed | Candidate sites only; asset manifests and permission record; labeled schematic/generic fallback until confirmed | Design/Integration / M1/M6 |
| R-006 | FFA inaugural history is sparse | No learned trade acceptance or FFA draft behavior claimed; clearly labeled priors and qualitative feasibility | Model / M5 |
| R-007 | Alias ambiguity, unknown stat/slot IDs and score corrections | Dated aliases, unresolved queue, unknown-rule blocks, exact Decimal rules, replay/reconciliation tests | Core/Data / M1 |
| R-008 | Auth choice and deployment capacity are open | Keep provider-independent server sessions and portable local storage; select before the relevant milestone | Owner/Engineering / M2/release |
| R-009 | Normal command isolation is unavailable in this session | Local command runner reported missing `bwrap`; scoped host execution used for file preparation and validation. This is an execution environment issue, not an Arbit dependency | Environment / current session |
| R-012 | Reference docs differ from FFA: missing mSchedule/standings fields, wrong pro-schedule/news scope, unsupported IR availability enum, incorrect football stat IDs and appliedStats description | Implemented contracts validate actual FFA league/player shapes and missing-data failures; all audited routes now have verified retrieval contracts; actual mapping now uses observed raw stats and pinned independent provenance, with source rule support and reconciliation checks | Integration / M1b–c |
| R-011 | Native worktree helper cannot recognize Linux checkout; global Corepack cache points into Windows | Dedicated feature branch and pinned npm-exec tooling; no global installation changes | Environment / current session |
| R-010 | Proposed SLO/model gates are unmeasured | Treat as budgets/policies; release evidence must contain actual results, not inferred success from architecture | Engineering / relevant milestone |

| R-013 | Standalone manual research budget is per instance; automatic workers now share PostgreSQL pacing/cooldown. Source reads still span a capture window | Do not mix standalone manual research with automatic polling. Stable bracketing cannot rule out change-and-revert or silent omissions; no atomic provider snapshot claim | Integration / M1c |

| R-014 | Eleven configured categories have no nonzero observed contribution in rostered weeks 1–7 | Mappings/formulas have hand/boundary tests; keep empirical coverage explicit and add anonymized fixtures as real examples occur. Advice remains disabled pending downstream prerequisites | Data/Model / M1c/M3 |

| R-015 | New-season/preseason sync currently requires nonempty completed-period scoring proof; missing draft profiles fail closed | Explicit rollover validation and bounded profile enrichment before adopting a changed source state; no guessing/projection fallback | Integration / season rollover |
| R-016 | M1d exact GSIS/ESPN joins cover 121/121 owned athletes; two lack weekly rows; wider directory ambiguities remain | Preserve unresolved records and missing rows; no zero-fill/name merge or guessed NFL-team/DST joins. Five conflicting supplemental aliases closed with backed-up preserved history | Data/Model / M3 |
| R-017 | Uppercase format suffixes currently classify as opaque | Deferred review minor; zero selected current files affected. Add compatibility support when a real source requires it | Data / future compatibility |
| R-018 | 786 imported assets lack upstream hashes; metadata bracket confirms all unchanged | Local byte hashes plus immutable pre/post catalog proof; cannot detect upstream change-and-revert/inaccurate metadata. As-of requires confirmation; no historical publication claim | Data/Model / M1/M3 |
| R-019 | Legacy participation `old_2023` has a distinct retained source shape | Confirm exact source-specific provenance/terms before promoting this variant into model features; original bytes are retained | Data/Model / M3 |

Add discovered bugs with a reproduction, affected requirement, expected behavior, observed result, evidence and next step. Do not put secrets or raw member payloads in this file.
