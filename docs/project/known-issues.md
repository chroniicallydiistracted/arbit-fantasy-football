# Known Issues and Risks

Updated 2026-10-31. M1a–e data/runtime slices are implemented and locally verified; real-member/full feature/model validation and expanded empirical Live/asset proof remain open.

| ID | Evidence / risk | Effect and mitigation | Owner / milestone |
| --- | --- | --- | --- |
| R-001 | Historical private-setting 401; current public core reads verified 200 | Public reader implemented and live-verified. Message boards excluded by owner; private credentials only become relevant if visibility changes | Integration / M1 |
| R-002 | Unofficial ESPN endpoints have no service contract | Adapter contracts, bounded polling, drift quarantine, last-complete snapshot, explicit degraded state | Integration / M1/M6 |
| R-003 | nflverse publication/feature coverage differs by dataset and season | Full 1,140-file audit is recorded; no 2026 participation file, FTN charting through week 7, depth timestamps not weeks. Local observation/confirmation is not historical vintage proof; M3 needs an explicit validation policy | Data/Model / M1/M3 |
| R-004 | Owner limits Sleeper to verified NFL live-game/PBP only; no eligible route enabled | All former fantasy acquisition/hint paths retired; retain historical receipts only. Verify an eligible route before adoption | Integration / M6 |
| R-005 | Owner has private permission for all Gridiron assets, personal use only (OWN-015). URL patterns and per-game variants remain unresearched | Manifest stays empty until patterns and variants are verified. Assets stay inside the invite-only app. Generic fallback stays labeled | Design/Integration / M6 |
| R-006 | FFA inaugural history is sparse | No learned trade acceptance or FFA draft behavior claimed; clearly labeled priors and qualitative feasibility | Model / M5 |
| R-007 | Alias ambiguity, unknown stat/slot IDs and score corrections | Dated aliases, unresolved queue, unknown-rule blocks, exact Decimal rules, replay/reconciliation tests | Core/Data / M1 |
| R-008 | Owner verified first real Google sign-in. Second-member proof needs the hosted origin or a sign-in on the owner's machine | Moves to the release gate with hosting (OWN-014). Production needs `https://ffa.westfam.media/auth/callback` registered | Owner/Engineering / release |
| R-009 | Historical: an earlier agent's command runner lacked `bwrap` | Not observed since 2026-10-31; not an Arbit dependency | Environment / closed |
| R-012 | Reference docs differ from FFA: missing mSchedule/standings fields, wrong pro-schedule/news scope, unsupported IR availability enum, incorrect football stat IDs and appliedStats description | Implemented contracts validate actual FFA league/player shapes and missing-data failures; all audited routes now have verified retrieval contracts; actual mapping now uses observed raw stats and pinned independent provenance, with source rule support and reconciliation checks | Integration / M1b–c |
| R-011 | Historical: an earlier agent's Corepack pointed into a Windows cache | Pinned `pnpm` works directly on this host as of 2026-10-31; the `npm exec` workaround remains documented | Environment / closed |
| R-010 | Proposed SLO/model gates are unmeasured | Treat as budgets/policies; release evidence must contain actual results, not inferred success from architecture | Engineering / relevant milestone |

| R-013 | Standalone manual research budget is per instance; automatic workers now share PostgreSQL pacing/cooldown. Source reads still span a capture window | Do not mix standalone manual research with automatic polling. Stable bracketing cannot rule out change-and-revert or silent omissions; no atomic provider snapshot claim | Integration / M1c |

| R-014 | Eleven configured categories have no nonzero observed contribution in rostered weeks 1–7 | Mappings/formulas have hand/boundary tests; keep empirical coverage explicit and add anonymized fixtures as real examples occur. Advice remains disabled pending downstream prerequisites | Data/Model / M1c/M3 |

| R-015 | New-season/preseason sync currently requires nonempty completed-period scoring proof; missing draft profiles fail closed | Explicit rollover validation and bounded profile enrichment before adopting a changed source state; no guessing/projection fallback | Integration / season rollover |
| R-016 | M1d exact GSIS/ESPN joins cover 121/121 owned athletes; two lack weekly rows; wider directory ambiguities remain | Preserve unresolved records and missing rows; no zero-fill/name merge or guessed NFL-team/DST joins. Five conflicting supplemental aliases closed with backed-up preserved history | Data/Model / M3 |
| R-017 | Uppercase format suffixes currently classify as opaque | Deferred review minor; zero selected current files affected. Add compatibility support when a real source requires it | Data / future compatibility |
| R-018 | 786 imported assets lack upstream hashes; metadata bracket confirms all unchanged | Local byte hashes plus immutable pre/post catalog proof; cannot detect upstream change-and-revert/inaccurate metadata. As-of requires confirmation; no historical publication claim | Data/Model / M1/M3 |
| R-019 | Legacy participation `old_2023` has a distinct retained source shape | Confirm exact source-specific provenance/terms before promoting this variant into model features; original bytes are retained | Data/Model / M3 |

Add discovered bugs with a reproduction, affected requirement, expected behavior, observed result, evidence and next step. Do not put secrets or raw member payloads in this file.

| R-020 | Historical Sleeper hints were incomplete and are now outside owner scope | No Sleeper fantasy hints feed identity/models; NFLverse exact GSIS/ESPN bridge remains authoritative statistical foundation | Data/Model / M3 |
| R-021 | M1e observed final/pregame/overtime/tie and factual play classes; no active latency, real correction pair or explicit sneak label | Synthetic regression behavior is distinguished; collect source captures/timing before full Live release | Integration / M6 |
| R-022 | Proposed serving freshness windows are longer than strict M1e batch-cache intervals | Actual one-interval/failed-refresh policy is documented; defer measured serving-threshold tuning. No automatic supplemental/live scheduler exists | Engineering / M6 |

| R-023 | M2 automated accessibility/keyboard/reflow/PWA checks are local fictional evidence | Human assistive-technology and native OS install acceptance remain release checks; no WCAG certification or real-provider proof claimed | Product/Engineering / M2 release |

| R-024 | **Closed 2026-11-01.** The real-time platform was verified only on a restored copy | Applied to the running app by the owner's decision; results are in the [handoff](handoffs/2026-10-31-platform-reset.md) | Done |
| R-025 | Active-game behavior is untested against the real source: no game was live during the proof. Synthetic tests cover correction and failure paths | First real slate gives latency, budget and correction evidence for R-021. Record a receipt in research | Integration / next NFL slate |
| R-026 | The statistics lane has only run against fakes; its first real daily import could be long and uses disk for changed files | Failures are recorded and retried after 2 hours; `--lanes league,live` disables it. Watch the first run, due about 2026-11-01 09:57 UTC | Data / first scheduled import |
| R-027 | No sync yet for FFA transactions and waiver results, player news or ESPN positional ratings | No consumer exists. Add to `arbit_data/freshness.py` when M3/M4 ship them | Data / M3–M4 |
| R-028 | New visual character is the developer's direction, accepted in ADR-005 subject to owner review | Automated checks cannot judge originality. Owner review is the acceptance gate for UX-005 | Owner / now |
| R-029 | The services stop with WSL. After a Windows restart nothing returns until WSL starts, and the Postgres container has restart policy `no` under Docker Desktop. Sleep also pauses live capture | Start Ubuntu and run `make db-up`; the units retry every 5-10 seconds. Recovery is untested. A real host replaces this at release (OWN-014) | Engineering / release |
