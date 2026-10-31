# ESPN endpoint wiring coverage

The original audit proved source availability; the first Arbit reader implemented only core acquisition. This slice closes that distinction: **all 68 recognized successful request variants across 19 registered families are callable through Arbit's guarded transport and provider client**. Every one of the 81 original audit cases is accounted for.

The [live coverage evidence](espn-endpoint-coverage-live-2026-10-30.json) records a fresh request through the production adapter for each recognized variant. A check succeeds only when its observed sections and identity/scope match the registered contract; HTTP 200 alone is insufficient. Current totals and timestamps are in that evidence.

| Family | Callable interface / observed scope |
| --- | --- |
| FFA league and views | `Endpoint.LEAGUE`: base metadata; settings, teams/members, rosters, matchup scores, matchups, boxscores, live scoring, scoreboard, standings diagnostics, schedule diagnostics, draft, transactions, status, positional ratings, player pool/cards and navigation metadata |
| Fantasy game metadata | `Endpoint.GAME` |
| Fantasy season metadata | `Endpoint.SEASON` with explicit season |
| NFL pro schedules/byes | `Endpoint.PRO_SCHEDULES`, season-level `settings.proTeams` |
| Active player directory | `Endpoint.PLAYER_DIRECTORY`, `players_wl`, JSON root array |
| Fantasy player news | `Endpoint.PLAYER_NEWS`, corrected site domain, with/without season |
| NFL core league | `Endpoint.NFL_CORE_LEAGUE`, NFL identity 28 |
| NFL core athlete collection | `Endpoint.NFL_CORE_ATHLETES`, bounded page request; not an automatic full-directory download |
| NFL core season athlete | `Endpoint.NFL_CORE_ATHLETE` with explicit season/player |
| NFL core season teams | `Endpoint.NFL_CORE_TEAMS` with explicit season/page/limit |
| Site NFL scoreboard | `Endpoint.NFL_SCOREBOARD` |
| Web NFL scoreboard | `Endpoint.NFL_WEB_SCOREBOARD` |
| Site game summary | `Endpoint.NFL_SUMMARY`, event identity and previous drives checked |
| Web game summary | `Endpoint.NFL_WEB_SUMMARY`, event and audited US/English query |
| NFL news | `Endpoint.NFL_NEWS` |
| NFL standings | `Endpoint.NFL_STANDINGS`, corrected `/apis/v2` scope |
| Now news | `Endpoint.NOW_NEWS`, optional football filter |
| NFL headshot | `Endpoint.HEADSHOT`, positive player ID; PNG MIME/signature |
| NFL team logo | `Endpoint.TEAM_LOGO`, bounded team abbreviation and fixed combiner image path |

Individual and combined views, scoring/matchup periods, availability statuses, IDs, positional/rank filters and pagination offsets from the original audit are reconstructed and tested. Boxscore validation selects the requested matchup rather than requiring populated player rosters on every schedule item. Cards require player stats; ranking-filter reads require ratings. Collection pagination must agree with explicit page options. Optional metadata may be omitted where observed, but a contradictory supplied identity is rejected.

Three responses are explicitly **limited**: `mSchedule` lacks schedule, `mStandings` lacks team records, and league-scoped `proTeamSchedules_wl` lacks schedules. Their useful alternatives are wired: matchup views, `mTeam`, and season-level pro schedules. Two views are **metadata-only**: `modular` and `mNav`.

Thirteen cases are excluded: nine non-200 cases (including the out-of-scope message board), three legacy HTML/redirect routes and the deliberate unknown-view control. They are preserved as evidence and are not working data APIs. No mutation endpoint, self-hosted reference-service route or unrelated sports integration was added.

## Reproduce

From the repository root:

```sh
uv run arbit-worker espn-endpoints
uv run arbit-worker espn-endpoints --live
```

The first command reconstructs the audit through the production allowlist without network access and makes no live-success claim. The second issues the 68 recognized reads serially under the existing budget and prints only safe results, counts and source receipts. Failed capabilities return nonzero; access/throttle/outage errors stop further calls and preserve the partial report. Audit method, credentials, outcomes, response formats and query consumption are validated before any request.

Library use remains inside the data layer:

```python
from arbit_data.espn.client import EspnClient
from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.transport import EspnTransport

client = EspnClient(EspnTransport())
transactions = client.fetch(
    Endpoint.LEAGUE,
    EndpointOptions(season=2026, views=("mTransactions2",), scoring_period=1),
)
```

This is complete wiring of the **verified retrieval surface**. Canonical rule/identity normalization, persisted sync, member auth, UI, news presentation, model validity, active-game cadence and historical completeness are separate gates. System DNS and per-instance/manual rate limitations are unchanged. Recommendations remain disabled pending scoring verification and the later model/auth requirements.
