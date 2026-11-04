# Richer live play detail: nflverse's raw play-by-play and ESPN — 2026-11-03

The owner looked at [nflverse-pbp-internal](https://github.com/nflverse/nflverse-pbp-internal) and [nflverse-pbp](https://github.com/nflverse/nflverse-pbp) as a way to get nflverse's richer play-by-play before a game ends. The only obstacle they found is one `nflapi` call that doesn't show its route.

## What the repositories show

- **The scraper.** `R/save_raw_pbp.R` calls `nflapi::nflapi_pbp(game_nflapi_id)` and saves the raw result. nflverse's own comment there says "QUERY RAW PBP FROM API (WORKS LIVE)". The game list comes from `nflapi::nflapi_games()`, and its IDs are named `v1_api_id`.
- **Why the data comes after games.** `auto/release_raw.R` keeps only games whose status contains `FINAL`. The release workflow runs every 15 minutes, so a game's raw play-by-play appears within about 15 minutes of the final whistle. A weekly workflow refreshes the latest 16 games for stat corrections.
- **Where the route lives.** `nflapi` is a separate nflverse package (`Remotes: nflverse/nflapi`). It isn't public: the GitHub API returns 404, and the workflows install it with nflverse's own token (`secrets.NFLVERSE_GH_TOKEN`). Neither public repository contains the route or how it authenticates.
- **What it points to.** The `v1_api_id` naming points to NFL's own API, the one behind nfl.com's game center. Finding the route would mean working it out from nfl.com's site and its sign-in tokens. NFL's Terms of Service prohibit "systematic retrieval of data ... to create or compile ... a collection, compilation, database" without written consent ([NGS note](ngs-highlights-2026-11-03.md)). So this is the same decision as NGS, and it is the owner's (Q-012).

## What nflverse's play-by-play adds

The table counts how many of the 188 plays carry each field in nflverse's CAR at GB (2026-10-29), the one game present in both our stored nflverse file and ESPN's live store.

| Field | Plays | Live from ESPN today? |
| --- | --- | --- |
| Air yards | 82: every pass attempt | For completions, yes: ESPN's yards minus its yards after catch. Not for incompletions |
| Yards after catch | 53: every completion | **Yes**, see below |
| Pass length and side, run location and gap | 81 and 49 | Yes, in the text |
| Kick distance, return yards | 26 and returns | Yes, in the text |
| Solo and assisted tacklers | 85 and 30 | Yes, as named participants |
| QB hit, passes defended | flags and 13 | No |
| Forced fumble and recovery players | 3 and 4 | In the text |
| Penalty type, player and yards | 11 | Partly: ESPN has a `penalty` object on 193 of 2,590 captured plays |
| Shotgun, no huddle, scramble, out of bounds | all plays | In the text (ESPN says "Shotgun" on 1,042 of 1,714 scrimmage plays) |
| Drive summaries | all plays | Yes, ESPN drives |
| EPA, win probability, CPOE, expected YAC | all plays | Win probability yes (ESPN's model); the others are nflfastR models computed from these fields |

## ESPN already sends yards after catch, live

ESPN's game summary, which the worker already reads during games, has a `yardsAfterCatch` field on each play. In our captured summaries (2,590 distinct plays, 2026-11-01 to 11-03) it is on **506 of 508 receptions**. The worker's normalizer keeps `statYardage` but drops this field. The raw summaries are still stored, so nothing is lost.

I checked it against nflverse's official values. ESPN's live captures were matched to nflverse's 2026 file (updated 2026-11-03 17:03 UTC) by play number and player names:

| Matched receptions | Yards after catch equal | Within 1 yard | Within 2 yards | Off by more than 5 |
| --- | --- | --- | --- | --- |
| 504 | 394 (78.2%) | 477 (94.6%) | 487 (96.6%) | 9 |

For a completion, the catch spot is the yards gained minus the yards after catch from the line of scrimmage, which matches nflverse's air yards on 390 of 504. ESPN sometimes gives negative yards after catch where NFL records 0. For the animation, that is enough to place the catch and the run after it within about a yard on 19 receptions in 20.

## Field by field: the nflreadr play-by-play dictionary

The owner added nflreadr's dictionary for the play-by-play dataset (`data/nflverse/dictionary_pbp.csv`, 372 fields). Each field was sorted by where we can get it during a game:

| Fields | Source during a game |
| --- | --- |
| 164 | **ESPN's live play.** Its fields (type, start and end spots, down and distance, yards, yards after catch, clock, wall clock, scores, sequence, penalty with type, yards and status, review with type and result, turnover) and the players it names (passer, receiver, rusher, tackler, assisted tackler, sacker, pass defender, forcer, fumbler, recoverer, returner, kicker, punter, holder, snapper, penalized player, scorer). The rest is in its description text: formation, pass depth and side, run gap, kick distance, fair catch, touchback, out of bounds, laterals, blocks, QB hits in brackets, and the extra-point or two-point result |
| 110 | **Worked out from the plays in order, player IDs or rosters.** Series and conversions, timeouts left, drive summaries, running totals, seconds remaining, jersey numbers and GSIS IDs (already joined for rostered players) |
| 67 | **nflfastR's models.** Expected points, win probability, completion probability, expected yards after catch and their running totals. nflfastR computes them; they aren't in any feed |
| 29 | **Game context.** Stadium, roof, surface, weather, coaches, betting lines and final score; most are in ESPN's game summary |
| **2** | **NFL only.** `air_yards` on incomplete passes and interceptions, and `play_clock` at the snap |

For incompletions, ESPN's text says only short or deep. In nflverse's 2026 data, short incomplete or intercepted passes went −4 to 13 air yards (10th to 90th percentile, median 5, never over 15). Deep ones went 17 to 42 (median 24). The choreographer aims an incompletion within that range, seeded by play, and a finished game can use nflverse's exact value.

## Descriptions: the same text

nflverse's `desc` and ESPN's `text` are both the NFL's official play description. Week 8 has 2,270 plays in both, matched by play number and wording. Most of nflverse's extra length, about 14 characters on a typical play, is the game clock it starts with ("(13:07)") and the jersey number before each name ("9-B.Young"). We have both elsewhere.

| | Plays |
| --- | --- |
| Word for word the same, once clock, jersey numbers, ESPN's team codes (BLT, ARZ, HST, CLV) and spacing are evened out | 2,145 (94.5%) |
| ESPN's text is NFL's plus the extra point or two-point result, which nflverse gives its own row | 67 |
| Spacing or line-break quirks this check didn't even out, plus the NFL's later corrections (one added assisted tackler) | about 50 |
| ESPN dropped "(Kick formation)" | 2 |
| ESPN gave its scoring-summary line instead of the play ("Jalen Coker 26 Yd pass from Bryce Young …") | 2 of 120 scoring plays |

The interpreter reads ESPN's structured fields first, so the two scoring-summary plays still get their players, spots and type. nflverse's text can replace either after the game.

## Recommendation

- **Use what ESPN sends.** The play interpreter (slice 1 of the [automation plan](../superpowers/plans/2026-11-03-live-play-automation.md)) reads `yardsAfterCatch`, and places the catch at the yards gained minus the yards after catch (ENG-032). It needs no new source and has no terms question.
- **nflverse after the game.** nflverse's published play-by-play arrives about 15 minutes after the final, under CC-BY. It could refine a finished game's plays with official air yards, including incompletions, plus QB hits and passes defended.
- **The private `nflapi` route.** I recommend against working it out. It is NFL's API, NFL's terms prohibit this kind of collection, and the piece the owner asked for, catch to carry, is already in the live ESPN feed. Owner decision: Q-012.
- **Not available from ESPN during a game:** exact air yards on incomplete passes and interceptions, and the play clock at the snap. nflverse fills both about 15 minutes after the final.
- **Not available live anywhere public:** player movement and speed (OWN-032).

Sources: the two repositories' code at their 2026-11-03 state, the GitHub API for `nflverse/nflapi` (404), nflverse's `play_by_play_2026.parquet` (public release, CC-BY), and our stored ESPN summary captures in `data/live-captures`.
