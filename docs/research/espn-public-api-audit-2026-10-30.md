# ESPN Public API Audit — FFA 2026

Tested **2026-10-30**, America/Phoenix. League **1729878439**, season **2026**, football code **ffl**.

## Result

**FFA's core league data is accessible without ESPN cookies while the league is publicly viewable.** The first cookie-free settings request returned 200, the correct IDs, and `settings.isPublic=true`. Earlier private-league 401 observations remain historical evidence; they no longer describe current public access. The communication endpoint still rejects anonymous access.

Reviewed all **68 tracked files**, including **34 Python files**, totaling **7,104 lines**, at [reference commit 097c42f](https://github.com/pseudo-r/Public-ESPN-Fantasy-API/tree/097c42f0da0b692ceb3168a2c6af1e7479be5906). This includes the complete client, models, serializers, routes, ingestion code, tests, configuration, CI/build files and documentation. [Source review manifest](espn-reference-source-review-2026-10-30.json) records every file checksum.

Executed **81 cookie-free GET probes** covering all **21 view names** in the detailed catalog, all **nine upstream client method request families**, documented football-compatible read URL families, filters, historical weeks, pagination, related NFL APIs and legacy variants. HTTP totals: **72 × 200, 1 × 401, 7 × 404, 1 × 400**. HTTP 200 alone is not treated as data coverage: three legacy requests returned HTML, two asset requests correctly returned PNG, and several views omitted the fields promised in the reference docs.

[Machine-readable evidence](espn-public-2026-10-30.json) contains each exact URL, safe headers, timestamp, status, expected-field checks, summary, body size and SHA-256. Complete response bodies and the one-off paced probe utilities remain only in ignored local `data/research/espn-public/2026-10-30/`; member names, owner GUIDs, contact details, communication contents and article text are not copied into the tracked evidence. No Cookie or Authorization header was sent, no credential store or Arbit secret setting was read, and no cookie jar was used.

## Observed FFA data

| Area | Observed result |
| --- | --- |
| Teams/members | Eight team records and eight member records |
| Roster | 132 distinct owned players; ONTEAM pool exactly matches all roster IDs |
| Available pool | **923** distinct entries: **884 FREEAGENT + 39 WAIVERS** |
| Pagination | Limit 300; offsets 0/300/600/900 returned 300/300/300/23; no duplicate IDs or overlap with owned roster |
| Draft | 128 picks; `OFFLINE`, keeper count 0 |
| Matchups | 56 regular-season entries, four in each matchup period 1–14 |
| Transactions | **389 unique records** across periods 1–8; period 8 returned 60 |
| Scoring | H2H_POINTS; rank type PPR; 46 scoring-item entries fetched, not yet normalized/reconciled through Arbit's scorer |
| Active lineup slots | QB 1, RB 2, WR 2, TE 1, FLEX 1, D/ST 1, K 1; bench 7, IR 1 |
| Locks / waivers | INDIVIDUAL_GAME / WAIVERS_TRADITIONAL |
| Season context | Current scoring/matchup period 8; 14 regular-season matchups; six playoff teams; previousSeasons empty |
| NFL player directory | 2,687 active-directory records; this broader directory is not the same universe as FFA's eligible pool |

These are observations over the test interval, not an atomic source snapshot or a promise that availability stays unchanged.

## Every documented view

The [complete view table](https://github.com/pseudo-r/Public-ESPN-Fantasy-API/blob/097c42f0da0b692ceb3168a2c6af1e7479be5906/docs/leagues.md#complete-view-reference) is the inventory authority. Tests substitute FFL/2026/1729878439 and obtain dependent player IDs from the actual roster. Some supplied examples/labels were verified against other sports and differ from this FFA response.

| View | HTTP | Actual FFA result |
| --- | --- | --- |
| `mSettings` | 200 | Full settings, 46 scoring items, public flag and eight-team configuration returned. |
| `mTeam` | 200 | Eight teams and eight member records; team records/standings fields present. |
| `mRoster` | 200 | 132 roster entries across eight teams; historical period 1 also returned 129 entries. |
| `mMatchupScore` | 200 | 56 schedule entries; player rosters populate for the requested matchup context. |
| `mMatchup` | 200 | Schedule plus roster/team context returned. |
| `mBoxscore` | 200 | Current-period player roster entries returned for the relevant matchup; period 1 also checked. |
| `mLiveScoring` | 200 | Scoring snapshot returned; active-game update cadence not measured. |
| `mScoreboard` | 200 | Schedule/team scoreboard data returned; this view omits some usual top-level IDs. |
| `mSchedule` | 200 | HTTP 200 JSON shell without schedule. Use mMatchupScore/mMatchup for the observed schedule. |
| `mStandings` | 200 | Simulation/playoff fields and schedule returned; team record objects absent. Use mTeam for records. |
| `mStatus` | 200 | Current scoring/matchup period 8; previousSeasons is empty. |
| `mDraftDetail` | 200 | 128 draft picks returned. Actual configured draft type is OFFLINE. |
| `mTransactions2` | 200 | Periods 1–8 checked: 389 unique transaction records; current period returned 60. |
| `mPositionalRatings` | 200 | positionAgainstOpponent.positionalRatings returned. |
| `kona_player_info` | 200 | Player pool, stats, ownership, availability and rating fields returned; filters/pagination checked. |
| `kona_playercard` | 200 | All three requested player IDs returned, seven stat records each. |
| `kona_league_messageboard` | 401 | 401 AUTH_COMMUNICATION_NOT_VISIBLE despite public league. No authenticated retry attempted. |
| `players_wl` | 200 | 2,687 active-directory records returned from the season /players subpath. |
| `proTeamSchedules_wl` | 200 | Works on /seasons/2026: settings.proTeams has 33 rows, including NFL team schedules. League-level example has no proTeamSchedules. |
| `modular` | 200 | HTTP 200 metadata only; no stable analytical payload established. |
| `mNav` | 200 | HTTP 200 navigation/default metadata. Combined mSettings/mTeam/modular/mNav returns explicit settings/team data. |

## Other endpoint families and domains

| Family | Representative HTTP | Observation |
| --- | --- | --- |
| Game metadata | 200 | FFL game metadata returned. |
| Season metadata | 200 | 2026 current scoring-period metadata returned. |
| Season pro schedules | 200 | settings.proTeams includes schedules/bye weeks; 32 NFL teams plus an unassigned row. |
| Documented player-news route | 404 | lm-api-reads /news/players returns 404. |
| Corrective player-news domain | 200 | site.api /apis/fantasy/v3/games/ffl/news/players returns news.feed. Both playerId-only and playerId+seasonId variants returned 200. |
| Current season via leagueHistory | 404 | 404 for season 2026; previousSeasons is empty. Not evidence of a historical authentication requirement. |
| Segments 1, 2 and 3 | 404 | All three return 404 for this league. Use segment 0 for the tested 2026 context. |
| fantasy.espn.com v1/v2/v3 | 200 | All three return HTML after redirects, despite final HTTP 200. |
| NFL core league/athletes/teams | 200 | League metadata, athlete collection sample, a roster-derived 2026 athlete and all 32 NFL team refs returned. |
| Site and Web NFL scoreboards | 200 | Both domains returned 14 events. |
| Site and Web game summaries | 200 | Both returned 25 drives, 196 play events and eight scoring plays for event 401873023. |
| NFL news | 200 | Six articles returned; article text not copied into tracked evidence. |
| NFL standings /apis/site/v2 | 404 | 404 for this URL family. |
| NFL standings /apis/v2 | 200 | Standings children returned at this variant. |
| now.core news | 200 | News and football-filtered news returned headlines. |
| now.core NFL /live | 404 | 404; headline feeds do not prove a usable NFL live-play stream. |
| Headshot/logo CDN | 200 | Both returned 200 image/png with valid PNG signatures; not JSON failures. |

## Filters, scoping and response-schema corrections

1. **Availability works with FREEAGENT, WAIVERS and ONTEAM.** The documented `INJURED_RESERVE` availability filter returns **400**, not an empty valid result. Five actual roster entries occupied slot 21 during the audit. IR belongs to roster placement/injury context; do not infer it from that unsupported availability enum.
2. **Without an explicit player limit, only 50 records returned.** This contradicts the player guide's suggestion of a complete unfiltered pool. Explicit limit/offset pagination is necessary. A QB slot/rank filter returned 25 QB-position entries; combined free-agent/waiver filtering respected both statuses.
3. **Matchup context is not a schedule-array filter.** `matchupPeriodId=1` and `=8` each returned all 56 schedule entries, while deeper player-roster context populated for the requested matchup. Select the intended schedule item locally and validate period IDs. Historical roster period 1 differs from the current roster.
4. **Correct pro-schedule scope is season-level.** The tested useful shape is `settings.proTeams[].proGamesByScoringPeriod`, not a league-level `proTeamSchedules` key. The included client's season method uses the successful route.
5. **Stats/ownership are nested differently from several examples.** Observed fields include `player.stats`, `player.ownership`, `statSourceId` and `statSplitTypeId`. Do not assume `playerPoolEntry.stats`, `statTypeId`, or pool-level ownership percentages from the guide/ingestor. The sampled cards returned source IDs 0/1 and split IDs 0/1; definitions still need explicit mapping before advice.
6. **Transaction enums are broader.** Observed `ROSTER`, `FREEAGENT`, `WAIVER`, `DRAFT`, `TRADE_PROPOSAL`, and `TRADE_DECLINE`. Do not hardcode the guide's underscored FREE_AGENT or treat every trade-related entry as an executed trade. `processDate` is not present on every observed record. Period filtering was verified for all eight requested weeks.
7. **Public indicators differ.** `settings.isPublic=true` coexists with `status.isViewable=false` in the successful response. Actual reachability and the authoritative settings response are more useful than assuming those two flags are interchangeable.
8. **Unknown/default views may succeed with metadata.** A deliberately unknown view also returned 200 JSON. Missing requested fields must be a distinct capability result; no silent empty-list/zero substitution.
9. **Source ingestion code is a reference, not Arbit's normalization.** It uses defaults/coercions and model assumptions that do not satisfy Arbit's unknown-data, Decimal, snapshot and identity requirements. No reference Django/Celery code was incorporated or run.
10. **Live proof is bounded.** One completed-game sample returned pass, rush, sack, interception, fumble, field-goal and other events. It does not establish active-game freshness, every required play type, uniform/field assets, exact trajectories or player tracking.

The corrective player-news route was additionally compared with the [existing ESPN wrapper request source](https://raw.githubusercontent.com/cwendt94/espn-api/master/espn_api/requests/espn_requests.py). Both tested site-domain variants returned news data; the reference repository's lm-api-reads news path returned 404.

## Scope boundaries

- ESPN mutation examples on `lm-api-writes` were inventoried and not called; this assignment is a data-retrieval test.
- `/api/v1/fantasy/*`, `/api/v1/ingest/*`, `/api/v1/live/*`, admin and schema/docs routes belong to the included **self-hosted Django service**, not an API hosted by GitHub or ESPN at those paths. All source was read; their nine upstream GET request families were tested directly. No reference service, local ingestion or Celery task was deployed or executed.
- Generic other-sport examples were adapted to football. No unrelated league IDs were queried. Previous FFA seasons do not exist in the returned `previousSeasons`; the alternate history URL was tested with the supplied 2026 context and returned 404.
- The message-board 401 was respected; filtered/authenticated variants were not repeatedly attempted after that denial.
- No league setting or membership changed, no transactions were submitted, and no choice of Arbit's final access policy was made. Arbit member sign-in remains a separate requirement from ESPN source visibility.

## Development conclusion

A cookie-free read adapter can use the verified public league endpoints while this visibility setting remains enabled. Persist the actual complete settings and unknown rule IDs, build schema contracts from observed FFA payloads, paginate availability, distinguish missing/denied data, and reconcile scoring before surfacing advice. If the owner later returns FFA to private visibility, private credential handling must be separately configured and tested. This audit proves access and records capabilities; it does not implement production synchronization or close all M1b/M1c gates.

## Complete probe index

Exact requests, response metadata and checks for every row are in the linked JSON evidence. `missing_expected_data` preserves HTTP 200 responses whose requested fields are absent; `asset_returned` means a verified PNG response.

| Probe case | HTTP | Recorded outcome |
| --- | --- | --- |
| `public-settings-preflight` | 200 | `data_returned` |
| `league-base` | 200 | `data_returned` |
| `view-mSettings` | 200 | `data_returned` |
| `view-mTeam` | 200 | `data_returned` |
| `view-mRoster` | 200 | `data_returned` |
| `view-mMatchupScore` | 200 | `data_returned` |
| `view-mMatchup` | 200 | `data_returned` |
| `view-mScoreboard` | 200 | `data_returned` |
| `view-mStandings` | 200 | `missing_expected_data` |
| `view-mSchedule` | 200 | `missing_expected_data` |
| `view-mBoxscore` | 200 | `data_returned` |
| `view-mLiveScoring` | 200 | `data_returned` |
| `view-mDraftDetail` | 200 | `data_returned` |
| `view-mTransactions2` | 200 | `data_returned` |
| `view-mStatus` | 200 | `data_returned` |
| `view-mPositionalRatings` | 200 | `data_returned` |
| `view-modular` | 200 | `json_metadata_only` |
| `game-metadata` | 200 | `data_returned` |
| `season-metadata` | 200 | `data_returned` |
| `season-pro-schedules` | 200 | `data_returned` |
| `league-pro-schedules` | 200 | `missing_expected_data` |
| `league-combined` | 200 | `data_returned` |
| `live-combined` | 200 | `data_returned` |
| `player-pool-default` | 200 | `data_returned` |
| `pro-player-directory` | 200 | `data_returned` |
| `message-board` | 401 | `http_error` |
| `history-route-current-season` | 404 | `http_error` |
| `view-mNav` | 200 | `json_metadata_only` |
| `modular-nav-combined` | 200 | `data_returned` |
| `player-card` | 200 | `data_returned` |
| `pool-status-FREEAGENT` | 200 | `data_returned` |
| `pool-status-WAIVERS` | 200 | `data_returned` |
| `pool-status-ONTEAM` | 200 | `data_returned` |
| `pool-status-INJURED_RESERVE` | 400 | `http_error` |
| `pool-free-waivers` | 200 | `data_returned` |
| `pool-qb-rankings` | 200 | `data_returned` |
| `pool-without-filter` | 200 | `data_returned` |
| `roster-week-1` | 200 | `data_returned` |
| `matchup-period-1` | 200 | `data_returned` |
| `boxscore-period-1` | 200 | `data_returned` |
| `matchup-period-8` | 200 | `data_returned` |
| `boxscore-period-8` | 200 | `data_returned` |
| `live-rosters-combined` | 200 | `data_returned` |
| `transactions-period-1` | 200 | `data_returned` |
| `transactions-period-2` | 200 | `data_returned` |
| `transactions-period-3` | 200 | `data_returned` |
| `transactions-period-4` | 200 | `data_returned` |
| `transactions-period-5` | 200 | `data_returned` |
| `transactions-period-6` | 200 | `data_returned` |
| `transactions-period-7` | 200 | `data_returned` |
| `player-news-documented` | 404 | `http_error` |
| `legacy-domain-v1` | 200 | `non_json` |
| `legacy-domain-v2` | 200 | `non_json` |
| `legacy-domain-v3` | 200 | `non_json` |
| `segment-1` | 404 | `http_error` |
| `segment-2` | 404 | `http_error` |
| `segment-3` | 404 | `http_error` |
| `nfl-core-league` | 200 | `data_returned` |
| `nfl-core-athletes` | 200 | `data_returned` |
| `nfl-core-season-athlete` | 200 | `data_returned` |
| `nfl-core-season-teams` | 200 | `data_returned` |
| `nfl-site-scoreboard` | 200 | `data_returned` |
| `nfl-site-web-scoreboard` | 200 | `data_returned` |
| `nfl-site-news` | 200 | `data_returned` |
| `nfl-site-standings` | 404 | `http_error` |
| `nfl-site-v2-standings` | 200 | `data_returned` |
| `now-news` | 200 | `data_returned` |
| `now-football-news` | 200 | `data_returned` |
| `now-nfl-live` | 404 | `http_error` |
| `cdn-headshot` | 200 | `asset_returned` |
| `cdn-logo-combiner` | 200 | `asset_returned` |
| `unknown-view-control` | 200 | `json_metadata_only` |
| `player-news-site-fantasy` | 200 | `data_returned` |
| `nfl-site-summary` | 200 | `data_returned` |
| `nfl-web-summary` | 200 | `data_returned` |
| `all-rostered-pool` | 200 | `data_returned` |
| `available-page-00` | 200 | `data_returned` |
| `available-page-01` | 200 | `data_returned` |
| `available-page-02` | 200 | `data_returned` |
| `available-page-03` | 200 | `data_returned` |
| `player-news-site-player-only` | 200 | `data_returned` |
