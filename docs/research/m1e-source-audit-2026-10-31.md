# M1e supplemental and live source audit

Observed **2026-10-31**. M1e is implemented and locally verified: cached supplemental Sleeper acquisition, scoped ESPN game/play normalization and offline replay, plus Gridiron metadata prerequisites. This is source-foundation evidence; member access, the Live interface, scoring estimates, models and recommendations remain later work. [Safe receipt](m1e-live-2026-10-31.json), [per-observation inventory](m1e-source-inventory-2026-10-31.json), [operator guide](../engineering/supplemental-live-sources.md).

## Sleeper documented and candidate capability matrix

The [official API documentation](https://docs.sleeper.com/) describes public read-only access without tokens, a full-directory call at most daily, attribution for trending data, and separate authorization for commercial use. The current local noncommercial research uses fixed public GETs, no Sleeper league, account or ownership integration. The implemented one-second shared gate stays below its general guidance; no provider reliability guarantee is inferred.

| Resource | Actual response | Classification and limits |
| --- | --- | --- |
| `/v1/players/nfl` on `api.sleeper.app` |200; 12,229 keyed records | Documented supplemental directory; one 24-hour reservation across processes; repeat reused the identical hash/time without another directory call |
| `/v1/state/nfl` |200; season 2026, regular, week 8 | Documented supplemental state; configured season is unchanged; mismatches are explicit |
| `/v1/players/nfl/trending/add?lookback_hours=24&limit=25` |200; 25 rows | Documented activity, attributed to Sleeper; not FFA ownership/availability or advice |
| Equivalent `/trending/drop` |200; 25 rows | Same limitations and 15-minute refresh policy |
| `/v1/stats/nfl/regular/2026/7` |200; 2,095 keyed rows | Explicit undocumented research candidate; legacy keyed stat maps lack row-level season/week proof |
| `/stats/nfl/2026/7?season_type=regular` on `api.sleeper.com` |200; 2,095 rows | Explicit undocumented candidate; observed row fields all season 2026/week 7/regular; same player-ID set as the keyed representation |

Candidate fields include passing/rushing/receiving, defense/special teams, snaps and source fantasy-point/rank/bonus columns. The richer representation also supplies player/team/opponent/game and update metadata. All original fields remain archived; import does not certify semantic equality to ESPN, source revision behavior, scoring correctness, projection-vs-actual guarantees or stable support. No documented/supported Sleeper live game/play feed has been established; the observation does not assert that no private or undocumented feed exists. No FFA totals are calculated from these candidates.

Read-only identity evidence: 5,685 linked directory records, 27 conflicts, 6,485 unresolved and 32 excluded D/ST records. The source has 6,736 integer ESPN hints/5,493 nulls and 3,893 GSIS strings/8,336 nulls. Only **40/121 owned athletes** have an exact hint found in the directory; the other 81 have no matching raw ESPN/GSIS hint. No name match or alias mutation fills that gap. NFLverse's existing GSIS path remains 121/121. A separately verified crosswalk bridge is future work before affected supplemental model features; primary FFA ownership and NFLverse statistics are unaffected.

## ESPN NFL capability and empirical coverage

The existing allowlisted ESPN client now supports explicit scoreboard season/type/week and the public core play collection. Provider JSON itself is the primary evidence; these unofficial routes have no service contract. Collection pages are reconstructed from validated inputs rather than dereferencing source URLs.

| Surface | Actual capability | Remaining empirical limit |
| --- | --- | --- |
| Site scoreboard, season 2026/type 2/week 8 |200; 14 events, one final and 13 scheduled | No active NFL game in this observed slate; no latency/freshness service guarantee |
| Site summary, final game |200; header/teams/status/scores, boxscore, drives/scoring plays and field metadata | Summary sample has 196 distinct play IDs but no per-play athlete IDs; do not infer participants from narrative |
| Public core collection `/events/{id}/competitions/{id}/plays?limit=300&page=1` |200; complete 197-play collection for the first game, including 166 plays with athlete references |166/197 is partial per-play participant coverage, not a promise every administrative/football event has an athlete list |
| Final/overtime/tie summaries + collections | Four completed games, 842 game-specific play rows; three include period 5; one final tie | Final overtime evidence does not prove an actively observed overtime feed |
| Scheduled game summary |200; null scores and no core-play request before kickoff | No successful empty play-feed claim; not requested is distinct from unsupported/empty |
| Active/delayed/postponed/cancelled or real revised pair | Not observed in this run | Explicit synthetic failure/state/correction tests support parser behavior only; M6 still needs observed captures and timing/load proof |

| Event | Plays | With athlete IDs | Game-scoped IDs resolved | Observed periods | Notes |
| --- | ---: | ---: | ---: | --- | --- |
| `401873023` | 197 | 166 | 74/74 | 1,2,3,4 | Completed source |
| `401872923` | 227 | 194 | 74/74 | 1,2,3,4,5 | Completed source; period 5 proves played overtime |
| `401872936` | 196 | 162 | 71/71 | 1,2,3,4,5 | Completed source; period 5 proves played overtime |
| `401872988` | 222 | 184 | 74/74 | 1,2,3,4,5 | Completed source; period 5 proves played overtime; final tie |

Across those games, 706/842 plays supplied athletes. All 293 game-scoped unique athlete IDs resolved through existing canonical ESPN aliases; IDs appearing in multiple games are counted per game here. Owned-athlete matches were 9/9/7/5 per game. Missing participants remain missing. These counts do not prove complete FFA fantasy attribution or every scoring contribution.

The [minimal factual fixture](../../tests/fixtures/live/espn-2026-source.examples.json) pins 20 actual provider types, source SHA, completed observation time and event/play IDs. It exercises pass/rush/sack/interception/fumble/penalty/kicks and administrative/unknown fallback. Actual nested PAT/two-point metadata is preserved separately from the primary play type. Explicit sneak wording was not observed; only a synthetic example covers that label, and ordinary short QB rushes are not relabeled by guess. Original source bodies stay ignored/private; no league-member data is in the fixture.

## Replay, scope and review corrections

One independent whole-branch review found four Important issues, all fixed through observed failing regressions and a full 409-test runtime check: cached summary/page restamping could undo newer corrections; requested season type was unchecked; a play's own reference could contradict assigned event scope; and malformed collection references could bypass safe failure handling. [Handoff](../project/handoffs/2026-10-31-supplemental-live.md) records the full findings/rulings and test names. No second review was dispatched.

Each play now retains its own page's observation time in live reads and offline multi-page replay. A newer summary/other page cannot promote cached older content. Matching facts can confirm their own observation time without producing a new play effect; older per-play evidence cannot undo a later no-play correction. Missing plays are not inferred tombstones. Scope requires the requested year/type/week and matching public NFL event/competition/play references where provided; embedded references are never fetched. Malformed references record a safe failed acquisition, clear its reservation and allow other selected games to continue.

Coordinates retain separate source team frames; source `down = -1` remains unknown with raw evidence. No continuous turnover trajectory, actual route tracking, stadium orientation or fantasy-point delta is fabricated. Replay is pure and does not install persistent M6 effective-play serving, outbox or SSE behavior.

Final offline verification covered **25 immutable observations and 66 unique manifest/body/normalized objects**, including 1,236 play rows across repeat observations, with zero provider requests. This differs from 842 game-specific rows because repeat captures are retained. All 17 captured ESPN raw inputs passed the corrected scope parser. Replaying two actual versions of the 197-play game yielded no changes; revised/late/mixed-page cases remain explicitly synthetic regression evidence.

## Gridiron and readiness boundary

Fresh HTML reads verified both sites, 2026 uniform week navigation and a 2026 field index with multiple variants. Both constructed uniform and field graphics require permission. No owner's earlier direct pattern or grant has been supplied; the manifest has zero assets, zero images downloaded and zero messages sent. [Exact prerequisites](gridiron-prerequisites-2026-10-31.md). `eligible_metadata` never means local image bytes are valid or ready to display.

FFA records are unchanged: one snapshot, 132 roster rows, 19,008 canonical entities and 35,505 aliases. There are zero active supplemental refresh reservations after the commands. Schema 0005 is applied locally without altering prior migrations. The full check passed 409 tests, Ruff/format, strict mypy 71, AJV and foundation checks. No automatic supplemental/live scheduler, member UI, model, deployment or recommendations is enabled.

**Next is M2:** authenticated application foundation, team binding and Front Office facts, with the OIDC provider/invite policy selected before auth implementation. M3 still validates semantic supplemental joins/features/model quality; M6 still proves active/corrected/live states, scoring attribution, persistent events/SSE, graphics and permitted exact assets. M1 source prerequisites are implemented with those limits visible; the complete product is not finished.
