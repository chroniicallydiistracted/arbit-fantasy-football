# Team environment and defense against the position, 2026-11-23

M3 slice 3b (TASK-20261123-004, ENG-056, OWN-068). The Model's first features: each team's offense and defense, the opponent's defense against each position, the D/ST points the opponent's offense gives up, and pre-game context. Everything is computed as of a decision time through the point-in-time reader. Receipts:
- [defense-position-study-2026-11-23.json](defense-position-study-2026-11-23.json)
- [team-features-audit-2026-11-23.json](team-features-audit-2026-11-23.json)

## How fast a defense's record against a position means something

The owner wants every sit/start call to explain why, including the opponent's defense against the position (OWN-068). Before using that, the study measured how much of it is signal. It uses the same method as the [signal study](ffa-projection-methods-2026-11-09.md): each defense's odd weeks against its even weeks, regular seasons 2016–2025, 315–320 team-seasons per measure, scored by the shared engine.

"Games for half signal" is the number of games after which the defense's own record and the league average deserve equal weight. After n games the feature weighs the defense's record by n / (n + k).

| FFA points allowed per game | Games for half signal: raw | Adjusted for offenses faced | Weight after 8 games, adjusted | League mean per team-game in the 2025 and 2026 audit runs |
| --- | --- | --- | --- | --- |
| to RBs | 18.7 | 20.0 | 29% | 22.0 |
| to QBs | 30.6 | 22.2 | 26% | 16.5–17.0 |
| to TEs | 37.6 | 40.1 | 17% | 13.5 |
| to WRs | 44.1 | 42.0 | 16% | 31.7–31.8 |
| to Ks | 49.4 | 55.3 | 13% | 8.1–8.5 |
| D/ST points an offense gives up | 9.2 | 9.1 | 47% | 5.5–5.7 |

What this means for sit/start:
- **RB and QB matchups carry real but modest signal.** Adjusting for the offenses a defense faced helps most at QB: k falls from 30.6 to 22.2, because a defense's raw QB numbers mostly reflect its schedule.
- **WR, TE and K matchups are mostly noise within a season.** After eight games a defense's record against WRs earns 16% weight, so "this defense is bad against WRs" should rarely decide a lineup.
- **D/ST is the opponent.** The points D/STs score against an offense settle within about nine games, much faster than a D/ST's own points (24.0 games, signal study). It is the strongest matchup signal measured here. The offense's giveaway tendency is real, matching the design's "D/ST is mostly the opponent".
- These are measured constants, not a verdict on the projections. Slice 4's backtest decides how much each contributes.

**Corrections, 2026-11-24 (TASK-20261123-007):**
- **Team codes (R-072).** This study ran on FFA targets where the Raiders' 2016–2019 and the Chargers' 2016 home games named the team as its own opponent, and their games had no D/ST line. The constants above are v0's, kept unchanged as the DvP research's baseline (OWN-074). The DvP research's validated measures were already free of the misattribution, so its position measures are unchanged by the repair. Its D/ST measure is now k 8.9 on all 320 offense-seasons ([v0 reproduction](dvp/V0_REPRODUCTION.md)). The team-rate constants now come from the signal study rerun on the repaired codes ([repair](targets-repair-r072.md)).
- **Playoffs (R-074).** Gamebooks now read regular-season games only, so last season's rates no longer include playoff games.
- **The last column** holds the averages of the two real-data runs below, not the 2016–2025 study means. For example, WR is 31.7–31.8 here and 33.6 across the study.

## Features

One row per team per game, as of the decision time (default: the game's kickoff). The 65 feature columns are defined in `arbit_model.feature_specs`, each with definition, unit, window, cutoff, sources and shrinkage:
- **Team rates,** season to date, using the signal study's definitions so its constants apply. Offense: plays per game, dropback rate, EPA per play, points per game. Defense: EPA per play allowed, points allowed per game, sack rate, takeaways per game. Each comes three ways: raw, shrunk toward the league mean, and last season's value.
- **The opponent's defense,** shrunk.
- **Defense against the position,** for QB, RB, WR, TE and K. Each position has:
  - FFA points allowed per game, raw and shrunk;
  - adjusted for the offenses faced (minus each offense's average at the position in its other games), shrunk toward zero;
  - opportunities allowed per game.
- **D/ST points the opponent's offense gives up,** raw and adjusted for the D/STs faced, both shrunk.
- **Pre-game context:** home, rest days for both teams, roof, surface, division game.

**How a game's points are found.** FFA points per player-game and D/ST come from the shared scorer, run on the rows the reader returns for each game. A game counts once its score, play-by-play, player and team statistics are all known before the decision. Its scored lines are cached per combination of file versions, so a stat correction published later is used only by later decisions.

## Real data (read only)

| Run | Result |
| --- | --- |
| 2025 week 10, every game at its kickoff (7 decision times) | 28 rows in 5.5 s; every feature fully covered |
| 2026 week 12, at the run on 2026-11-23 | 32 rows in 4.5 s; 158 completed 2026 games known; every feature fully covered |

League values the 2026 run used look right: 23.1 points per game, 62.2 plays, a 56.8% dropback rate and a 6.8% sack rate. Examples from 2026 week 12, adjusted and shrunk:
- **RBs:** Philadelphia's backs face Dallas, which allows +2.96 FFA points per game more than its opponents' backs usually score. Carolina's face Tampa Bay at −2.01.
- **D/STs:** New York Giants' D/ST faces Indianapolis, whose offense gives up 8.15 D/ST points per game against a league 5.5. Buffalo's faces Kansas City at 2.74.

## Tests

- **Six tests** in `test_team_features.py`:
  - every column is a specified feature;
  - the constants equal both receipts;
  - team rates follow the signal study's definitions;
  - defense against the position is raw and adjusted (checked against the scorer's own position totals);
  - a mutation test: week 2 results, and stat corrections published after the decision, change nothing;
  - a correction published before the decision does change the features.
- **Three gamebook tests** in `test_gamebook.py`: a game counts once every table is known; scores are cached per version and rescored after a correction; FB scores as RB.
- **Two deliberate breaks** each fail a test: reading three days past the decision, and dropping the opponent adjustment.
- **The reader** now names each row's source version (`_manifest`), which the per-game cache uses.

## Limits

- **Positions** are nflverse's current labels mapped to FFA's (FB counts as RB), not a dated role, as in the slice 2 targets.
- **Pass rate over expected, success rate, drives and red-zone finishing** need play-by-play features and their own measured constants. They are left to a later 3b follow-up rather than shrunk with guessed constants.
- **Expected quarterbacks** are observed-only (ADR-007) and come with availability (3c).
