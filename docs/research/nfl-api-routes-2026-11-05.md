# The NFL API as a live play source — the owner's route tests, 2026-11-05

## Live-only follow-up

The pregame investigation traced a 30-second play-by-play refetch interval in NFL.com's browser code and saw ordinary JSON when requesting `text/event-stream` from the v2 game record. It observed Varnish caching with different settings for completed details, pregame details and weekly summaries. The investigation had no in-game sample. [Week 9 capture plan](../superpowers/plans/2026-11-05-live-feed-observation.md).

The owner tested routes on `api.nfl.com`, the raw source nflverse itself captures, and put the package in the ignored `data/NFL_API_Expanded_Route_Tests/`. The owner decided to use this source once their script is final (OWN-040). This note records what the package shows for Arbit's Live animation and board. None of its data is committed, and it holds no credentials. The 46 strings in it that look like signed tokens are the API's pagination cursors (`"pagination": {"token": …}`, encoding a limit, offset and query), not login tokens.

## What the owner's package contains

- **Requests:** 25 direct GET requests across 21 route families on 2026-11-05. 22 returned data, 2 returned empty collections, and 1 returned an application error behind HTTP 200.
- **Integrity:** the package's own verifier (`work/expanded/verify_expanded.py`, standard library, no network) reproduces exactly. Run on a copy, it regenerates `verification_report.json`, `observed_field_catalog.json` and `route_results.csv` byte for byte.
- **The play data:** `/football/v2/experience/weekly-game-details` for 2026 regular-season week 1, with 16 final games and 3,023 play records under `driveChart.plays`.
- **Not measured:**
  - **Live delay:** the package didn't measure it.
  - **Live games:** none were captured. Week 9's game summaries came back empty.

## What a play record gives

Each play has:
- **Timing:** `quarter`, `clockTime` (the game clock at the snap), and `playStartTime` and `playEndTime` (UTC wall-clock times).
- **Situation:** `down`, `yardLine` and `yardsRemaining`, plus `prePlayByPlay` (such as "SEA 1-15 SEA 45").
- **Result:** `yardsGained`, `playType`, `specialTeamsPlayType`, `scoringPlayType` and `scoringTeamId`.
- **Drive:** the drive fields.
- **Text:** `playDescription`, and `playDescriptionWithJerseyNumbers`.
- **Stats:** a `stats` list. Each entry has the player's GSIS ID (nflverse's own player ID), his name as the text writes it, his **jersey number**, NFL's person and team IDs, a stat type and yards.

Each game carries NFL's identifiers: Elias (`2026090900`, which is nflverse's `old_game_id`), GSIS and a slug. It has no ESPN ID; nflverse's schedule maps `old_game_id` to ESPN's.

## Findings for the board and the animation

**The start and end times are the snap and the whistle.**

| Play type | Median duration (all 2,307 plays with both times) |
| --- | --- |
| Pass | 5.1 s |
| Run | 4.3 s |
| Sack | 5.0 s |
| Kickoff | 8.4 s |
| Punt | 8.9 s |
| Field goal | 3.6 s |
| Kneel | under 1 s |

The strongest test is the next snap. An incompletion stops the clock, so the next snap should show exactly the snap clock minus the play's duration. It does within 1.5 seconds on 291 of 312 incompletions, with a median difference of 0.2 seconds.

**The game clock at the whistle is the snap clock minus the duration on plays from scrimmage.** Over 2,242 pairs of consecutive plays in the same quarter, only 165 next snaps showed more time than that. 159 are kickoffs: on a free kick the clock starts only when the receiving team touches the ball, so the kick's flight isn't game time. The other 6 are long returns, where the clock stops on a change of possession.

So the board's `clock_end` (ENG-040) can come from this feed:
- **Plays from scrimmage:** the snap clock minus the duration.
- **Kickoffs:** only from the touch, which the feed doesn't time. Hold the clock, or run it from the return.
- **No end time:** 630 records have a start but no end. They are mostly timeouts (369), tries (89) and pre-snap flags (75), where no clock runs, plus 84 plays. The board holds there.

**Jersey numbers for fouls are in the feed.** All 209 fouls in week 1 that name a player have him in the play's stats with his number (stat type 93, penalty). The board's roster lookup (ENG-040) found 214 of 215 in the ESPN captures; the feed needs no lookup at all.

**Real play durations.** The choreographer times each play from its distances. With the snap-to-whistle duration it could fit the play to the real time.

## Joining it to the plays Arbit stores

- **Games:** Elias ID → nflverse `old_game_id` → ESPN event ID.
- **Plays:** ESPN and the NFL use the same gamebook text. The NFL's carries a "(13:09)" clock prefix and uses "(:28)" under a minute. Matching quarter, snap clock and text should join a play. Tested on CHI at SEA below: 157 of 159 football plays join.

## Open before it feeds the app

- **Live delay:** measured on a live slate, against ESPN's median of 36 seconds (2026-11-01 receipt).
- **Ingestion:** a supervised worker lane with a declared cadence and stale limit, as every source needs. The owner wants plays pushed the moment they're available rather than polled every 5 to 10 seconds (OWN-040). The API has no push to subscribe to, so a push design is something Arbit, or the owner's pipeline, would build.
- **Authorization:** the anonymous device grant the owner's script uses, kept server-side like every credential.

## CHI at SEA (week 8), fetched for comparison, 2026-11-05

At the owner's request, the owner's `direct_only.py` was run unchanged on one request: `/experience/v1/gamedetailsbyslug/bears-at-seahawks-2026-reg-8`.
- **Where it ran:** its own ignored folder, `data/nfl-api/2026-11-05-chi-at-sea/`, so the owner's earlier evidence wasn't overwritten.
- **Sign-in:** the script's anonymous device grant, with the public web-client defaults read by `ast` from sportsdataverse-py's `nfl_games.py` (fetched from its `main` branch, never executed). That file's SHA-256, `096b9b26…`, differs from the owner's recorded `704646ce…`, which may cover a different file or version.
- **Result:** HTTP 200, 367,114 bytes. The game is final, with Elias ID `2026110200` and 189 play records, 149 of them with snap and whistle times. No token was saved.

**Joining to Arbit's stored ESPN plays: 157 of 159 football plays.** 150 match on quarter, snap clock and text, and 7 scoring plays on text, since ESPN times those after the play. The NFL also lists the 7 tries as plays of their own, which ESPN attaches to the touchdown.

**ESPN's clock on a scoring play is the clock after it.** All 7 scoring plays show ESPN's clock equal to the NFL's snap clock minus the play's duration, to the second:

| Scoring play | NFL snap clock | Snap minus duration | ESPN's clock |
| --- | --- | --- | --- |
| Williams to Burden, touchdown | 5:30 | 5:25.2 | 5:25 |
| Myers, 27-yard field goal | 12:53 | 12:50.0 | 12:50 |
| Santos, 44-yard field goal | 6:11 | 6:07.0 | 6:07 |
| Santos, 38-yard field goal | 1:12 | 1:08.5 | 1:08 |
| Darnold to Smith-Njigba, touchdown | 0:37 | 0:30.3 | 0:30 |
| Darnold to Kupp, touchdown | 11:51 | 11:45.8 | 11:46 |
| Swift, touchdown | 8:33 | 8:28.1 | 8:28 |

Two independent sources agree, which confirms the end-of-play clock rule. It also means the board, fed by ESPN alone, shows a scoring play's after-play clock from the snap: 3 to 7 seconds early. The NFL feed gives both clocks.

**Our animations are faster than the real plays.** Median snap to whistle:

| Template | Plays | Ours | Real | Ours ÷ real |
| --- | --- | --- | --- | --- |
| Pass | 64 | 3.6 s | 5.0 s | 0.63 |
| Run | 47 | 2.2 s | 4.4 s | 0.53 |
| Kickoff | 11 | 8.8 s | 8.1 s | 1.12 |
| Flag (penalty) | 7 | 3.1 s | 5.3 s | 0.53 |
| Punt | 5 | 7.1 s | 10.1 s | 0.70 |
| Field goal | 4 | 4.1 s | 3.4 s | 1.16 |
| Sack | 3 | 3.1 s | 4.6 s | 0.68 |
| Scramble | 3 | 5.3 s | 6.3 s | 0.89 |

The real time includes play after the action we draw, such as the pile and the whistle. Still, with the feed each play could be paced to its real length; that is a question for the owner.

**The board's foul numbers: 14 of 15 right.**
- **Agree:** 9 match exactly, and 3 differ only in format (the NFL writes "01"). 2 declined fouls carry no stat, but `playDescriptionWithJerseyNumbers` gives "SEA-29-J.Jobe" and "CHI-6-K.Gordon", matching the board.
- **Differs:** Q.Nelson's false start. nflverse's week-8 roster says 56, and the NFL's record of the game says 53. The game's own record is the authority, so with the feed the board would take numbers from it.
