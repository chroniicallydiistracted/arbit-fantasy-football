# NFL API data survey — slice A of the primary-source plan, 2026-11-05

Slice A of the [NFL API plan](../superpowers/plans/2026-11-05-nfl-api-primary.md) (OWN-041): everything the NFL API can return about a game, and what Arbit would use it for.

**Sources.**
- **Routes:** every route in the sportsdataverse endpoint catalog, plus those in the owner's route tests and NFL.com's own traffic.
- **Requests:** the owner's `direct_only.py` ran unchanged, in its own ignored folder, `data/nfl-api/2026-11-05-week8-survey/`. It made 21 requests for week 8 at its own pace, all HTTP 200, and saved no token.
- **The owner's earlier evidence:** [week 1 and CHI at SEA](nfl-api-routes-2026-11-05.md).

## Routes and what they give

| Route | Week 8 response | What it gives | Arbit's use |
| --- | --- | --- | --- |
| `/football/v2/weeks/date/{date}` | 458 B | The NFL week containing a date, its bye teams and its dates | Discovery: the current week |
| `/football/v2/games/season/{y}/seasonType/{t}/week/{w}` | 31 kB, 14 games | Each game's UUID, kickoff time, teams, venue, broadcast and category (TNF and so on). Its `status` stays SCHEDULED even after the game, so it isn't live state | Discovery: which games to watch, and when |
| `/football/v2/stats/live/game-summaries` | 11 kB, 14 games | Each game's phase, quarter, clock, down, distance, yard line, red zone, goal to go, score, start time, weather, attendance and gamebook PDF link | **The cheap live scoreboard.** Poll it for the week; fetch a game in full only when it changes |
| `/experience/v2/gamedetails/{id}` (with drive chart, replays, standings and tagged videos) | 439 kB | The game, its drives and every play (below), tagged videos and standings | **The play record**, with snap and whistle times and jersey numbers |
| `/experience/v1/gamedetails/{id}` | 641 kB | The same plays in another shape, adding possession and scoring teams, first downs, end yard line, penalty on play, short description, timeouts used and remaining, points by quarter, scoring summaries, red zone, and NFL's team colors for light and dark backgrounds. `latestPlay`, `isBigPlay`, `playReviewStatus` and `playClock` are empty or zero on a finished game, so they are likely live-only | **Game state and the extra play fields** |
| `/experience/v1/gamedetailsbyslug/{slug}` | 367 kB | v2's play record by slug | The same as v2 |
| `/football/v2/experience/weekly-game-details` | 6.2 MB | v2 game details for the whole week | Catching up a week; too large to poll |
| `/football/v2/stats/live/player-statistics/{id}` | 190 kB | Each player's box score for the game | Live player statistics, which could also serve the live fantasy estimates later |
| `/football/v2/stats/live/team-statistics/{id}` | 5 kB | Each team's box score | The game page's team statistics |
| `/football/v2/rosters?teamId=` | 44 kB, 89 people | Each player's NFL person ID, GSIS and Elias IDs, jersey number, position, roster status (ACT, DEV for practice squad, and so on), height, weight, experience and headshot address | Players' identities and numbers, which the play record overrides for a game |
| `/football/v2/standings` | 30 kB | Every team's standing for a week | Team context |
| `/football/v2/teams/{id}`, `/teams/history`, `/experience/v1/teams` | 1–36 kB | Team identity, branding, coaches and links | Team identity |
| `/football/v2/injuries` | 14 kB | Injury reports. The `week` filter is ignored: weeks 8 and 9 both returned week 1's first page | Open: needs paging or another filter |
| `/content/v1/videos/clips?gameId=` and `/replays` | 73 kB, 13 kB | Video metadata. 18 of CHI at SEA's 25 clips name the plays they show (`playIds`), such as the 3679 interception | A play can link out to its official highlight. Arbit never plays or stores NFL video |

The owner's tests also covered combine profiles, draft picks, site menus and pages, promotions, livestreams and RedZone previews. None of them is game data.

## The play record, field by field

**From v2 (and by slug):**
- `playId`, `playSequenceNumber`, `quarter` and `clockTime`, the game clock at the snap.
- `playStartTime` and `playEndTime`: the snap and the whistle (below).
- `playType`, `specialTeamsPlayType`, `scoringPlayType` and `scoringTeamId`.
- `down`, `yardLine`, `yardsRemaining`, `yardsGained`, `playIsGoalToGo`, `nextPlayType` and `nextPlayIsGoalToGo`.
- `prePlayByPlay`, such as "SEA 1-15 SEA 45".
- `playDescription` and `playDescriptionWithJerseyNumbers`.
- The drive fields.
- `playDeleted`, which marks a removed play.
- `stats`: one per player action, with GSIS player ID, the name as the text writes it, jersey number, NFL person ID, team ID, stat type and yards.

**Added by v1:**
- `possessionTeam` and `scoringTeam`, with NFL's team colors.
- `firstDown`, `endYardLine`, `goalToGo` and `penaltyOnPlay`.
- `shortDescription`, `timeOfDay` (the snap) and `endClockTime` (the whistle, the same instants as v2's).
- The live-only `latestPlay`, `isBigPlay`, `playReviewStatus` and `playClock`.
- `playStats` with a stat ID and team.

## Findings

**Snap and whistle.** `playStartTime` and `playEndTime` mark the snap and the whistle. Over week 1's 2,307 timed plays:
- **Durations:** the median is 5.1 seconds for a pass, 4.3 for a run, 8.9 for a punt, and under 1 for a kneel.
- **After an incompletion,** which stops the clock, the next snap is within 1.5 seconds of "snap clock minus duration" on 291 of 312.

**The clock at the whistle** is the snap clock minus the duration on plays from scrimmage. No field gives it: v1's `endClockTime` is the whistle's wall-clock time.
- **Confirmed against ESPN:** ESPN's own clock on all 7 CHI at SEA scoring plays, which ESPN times after the play, matches it to the second.
- **Kickoffs:** the clock starts at the touch.
- **Timeouts, tries and pre-snap flags** have no end time and no clock runs.

**Joining to ESPN.**
- **Plays:** every NFL football play in CHI at SEA has its ESPN play at **ESPN event ID followed by the NFL play ID** (152 of 152). Only timeouts and two-minute warnings carry ESPN IDs of their own.
- **Games:** they join through the Elias ID, which is nflverse's `old_game_id` and maps to ESPN's event ID.

**Jersey numbers.**
- **From the play's stats:** every one of week 1's 209 fouls naming a player has the player with his number (stat 93).
- **From the text:** declined fouls carry no stat, but `playDescriptionWithJerseyNumbers` has the number.
- **Why rosters aren't enough:** the game's own record is the authority. Quenton Nelson wore 53 against CHI. nflverse's week-8 roster said 56, and NFL's season roster lists no number for him.

**The real pace.** Arbit's runs animate in about 0.53 of the real snap-to-whistle time, and passes in 0.63.

**Sign-in.** The anonymous device grant returns a token that lasts about 60 minutes, with a refresh token. The token carries an approximate location (city, ZIP and market) from the request, so it must never be logged.

**Sizes for polling.**
- **The cheap read:** game summaries cover the week in 11 kB.
- **Per game:** v2 is 440 kB and v1 640 kB.
- **The week:** weekly details are 6.2 MB, so the worker polls the summaries and fetches only games that changed.

## Still to measure (slice A)

- **On the next live slate:** how soon a play appears against its whistle time, how often and how much a live game's response changes, whether the live-only fields fill in, and what `playClock` holds.
- **Rate limits:** none seen at the script's pace of one request per 0.6 seconds. A live budget needs a deliberate test.
- **Injuries:** how to page or filter them by week.
