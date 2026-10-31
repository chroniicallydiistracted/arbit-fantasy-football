# Known Issues and Risks

Updated 2026-10-30. M1a is implemented; provider access and full feature validation remain open.

| ID | Evidence / risk | Effect and mitigation | Owner / milestone |
| --- | --- | --- | --- |
| R-001 | Historical private-setting 401; public audit now returns 200 core reads and 401 communication | Public source access verified. Private credentials remain untested if owner restores private visibility; production adapter still required | Integration / M1 |
| R-002 | Unofficial ESPN endpoints have no service contract | Adapter contracts, bounded polling, drift quarantine, last-complete snapshot, explicit degraded state | Integration / M1/M6 |
| R-003 | nflverse publication/feature coverage differs by dataset and season | Coverage inventory and observation-time cutoffs; no assumed in-season participation/routes or latest injuries | Data/Model / M1/M3 |
| R-004 | Sleeper public docs do not prove a supported live scoring/PBP endpoint | Supplemental documented inputs; unproven endpoints cannot be a core dependency | Integration / M1 |
| R-005 | Gridiron exact owner links/asset permission unconfirmed | Candidate sites only; asset manifests and permission record; labeled schematic/generic fallback until confirmed | Design/Integration / M1/M6 |
| R-006 | FFA inaugural history is sparse | No learned trade acceptance or FFA draft behavior claimed; clearly labeled priors and qualitative feasibility | Model / M5 |
| R-007 | Alias ambiguity, unknown stat/slot IDs and score corrections | Dated aliases, unresolved queue, unknown-rule blocks, exact Decimal rules, replay/reconciliation tests | Core/Data / M1 |
| R-008 | Auth choice and deployment capacity are open | Keep provider-independent server sessions and portable local storage; select before the relevant milestone | Owner/Engineering / M2/release |
| R-009 | Normal command isolation is unavailable in this session | Local command runner reported missing `bwrap`; scoped host execution used for file preparation and validation. This is an execution environment issue, not an Arbit dependency | Environment / current session |
| R-012 | Reference docs differ from FFA: missing mSchedule/standings fields, wrong pro-schedule/news scope, unsupported IR availability enum | Audit preserves actual outcomes; typed contracts must use observed FFA shapes and reject missing data explicitly | Integration / M1b–c |
| R-011 | Native worktree helper cannot recognize Linux checkout; global Corepack cache points into Windows | Dedicated feature branch and pinned npm-exec tooling; no global installation changes | Environment / current session |
| R-010 | Proposed SLO/model gates are unmeasured | Treat as budgets/policies; release evidence must contain actual results, not inferred success from architecture | Engineering / relevant milestone |

Add discovered bugs with a reproduction, affected requirement, expected behavior, observed result, evidence and next step. Do not put secrets or raw member payloads in this file.
