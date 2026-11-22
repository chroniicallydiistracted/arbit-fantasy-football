# FFA points from nflverse statistics, verified against ESPN

Observed **2026-11-09**. M3 slice 1 ([plan](../superpowers/plans/2026-11-09-m3-model.md)). Arbit can now turn nflverse weekly statistics and play-by-play into FFA stat lines and score them with the shared engine under FFA's stored rules. That gives the Model an FFA-scored history to learn from and backtest against, where before only ESPN's points for rostered players existed. [Machine-readable receipt](nflverse-ffa-scoring-2026-11-09.json).

## Result

Every player-week ESPN serves for the 2025 regular season and 2026 through week 9 was compared category by category, and as an FFA total, with the line built from nflverse.

| Season | ESPN played weeks | Compared | Exact in every category | Differ | Refused (unknown) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025, weeks 1–18 | 8,137 | 7,202 | **7,171** | 8 | 23 |
| 2026, weeks 1–8 (decided) and 9 | 4,144 | 3,569 | **3,549** | 3 decided, 3 in week 9 | 14 |

| Position | 2025 compared / exact | 2026 compared / exact |
| --- | --- | --- |
| QB | 664 / 661 | 309 / 306 |
| RB | 1,659 / 1,653 | 795 / 792 |
| WR | 2,516 / 2,508 | 1,255 / 1,249 |
| TE | 1,276 / 1,270 | 672 / 668 |
| K | 543 / 541 | 270 / 269 |
| D/ST | 544 / 538 | 268 / 265 |

Not compared, by reason:

- **No nflverse row, ESPN all zero:** 918 (2025) and 546 (2026). ESPN marks a player as having played; nflverse lists only players with a recorded statistic. All of these ESPN lines are zero in every category.
- **No nflverse row, ESPN nonzero:** 18, all in 2026 week 9 and all from Chicago–Tampa Bay, the Sunday-night game that kicked off after the last nflverse import (03:56 UTC). This is timing, not a mapping gap.
- **Unresolved identity:** 26 player-weeks from two players whose ESPN IDs have no GSIS alias: Chris Manhertz and Greg Desrosiers Jr. (R-062).
- **No team row:** Chicago and Tampa Bay D/ST, 2026 week 9, for the same reason as above.

The reverse check found no nflverse row for a player in ESPN's pool without a matching ESPN game.

## Definitions settled against ESPN

The adapter is `arbit_data.nflverse.stat_lines`, version `nflverse-ffa-stat-lines-v1`. Where a definition below rests on a single observed play, the count says so.

| FFA metric | From nflverse | Evidence |
| --- | --- | --- |
| Passing, rushing, receiving yards, TDs, 2-pt conversions, receptions, interceptions | Same-named weekly player columns | 10,771 compared lines |
| Fumbles lost | `fumbles_lost_total` (sack, rush, reception and return fumbles) | Every compared line |
| FG 0–39 / 40–49 / 50–59 / 60+ | `fg_made_0_19 + 20_29 + 30_39`, `fg_made_40_49`, `fg_made_50_59`, `fg_made_60_` | 813 kicker-weeks |
| Missed field goals | `fg_missed + fg_blocked`. ESPN counts blocked attempts as misses | 813 kicker-weeks; 6 differed in the first 2026 comparison before this rule |
| Kick and punt return TDs | Play-by-play, by `td_player_id` and kick type | Every compared line |
| Fumble return TD vs fumble recovery TD | An opponent's fumble recovered for a TD is a fumble return TD, even when the offense recovers the defense's fumble after an interception. A teammate's fumble is a fumble recovery TD | 1 play (2025 week 5) |
| D/ST points allowed | Opponent's final score, minus 6 for each interception or fumble TD the opponent's *defense* scored and 2 for each safety against the offense. Return TDs, blocked-kick TDs, a teammate's fumble recovered in the end zone, defensive two-point returns and safeties on kicks all still count | 812 D/ST-weeks. All 6 differences in the first 2026 comparison were defensive TDs or a safety against the offense |
| D/ST yards allowed | Opponent `passing_yards + rushing_yards + sack_yards_lost` (net passing). `sack_yards_lost` is stored ≤ 0 in every season checked (2001, 2012, 2025, 2026) | 812 D/ST-weeks |
| D/ST sacks | Opponent `sacks_suffered` | 808 of 812; the 4 others are uncredited sacks (below) |
| D/ST interceptions, blocked kicks | `def_interceptions`; `def_fg_blocks + def_punt_blocks + def_pat_blocks` | Every D/ST-week |
| D/ST fumbles recovered | `fumble_recovery_opp`, minus opponent fumbles the team's *offense* recovered after a turnover, pairing each fumble with its recovery. Blocked field goals and extra points are special teams | 4 D/ST-weeks differed before this rule |
| D/ST return TDs | Play-by-play by scoring team. A muffed punt the punting team recovers for a TD is a punt return TD (1 play, 2026 week 3). A kickoff the kicking team recovers in the end zone is a fumble return TD, with no individual credit (1 play, 2025 week 2). A TD the offense scores on the defense's fumble is not the D/ST's | As listed |
| D/ST safeties, one-point safeties, two-point returns | Play-by-play score changes and `defensive_two_point_conv` / `defensive_extra_point_conv` | 1 two-point return; no one-point safety observed |
| Offensive statistics on a D/ST line | Zero. ESPN's were zero in every D/ST-week | 812 D/ST-weeks |

## Remaining differences

Each is a difference in how the two sources recorded a play. None is a mapping error the adapter could fix without guessing.

| Cause | Cases | Effect on FFA points |
| --- | --- | --- |
| **Sack with no credited defender.** 13 decided D/ST-weeks had one. ESPN counted it in 9 and left it out in 4; nflverse's opponent total always counts it, so it matches the 9 | 4 (2025: 2, 2026: 2) | 1 |
| **Two-point catch missing on ESPN.** ESPN credits the passer's conversion but no receiver; play-by-play names the receiver (2026 week 3 Chris Blair, 2025 week 1 Julian Hill) | 2 | 2 |
| **Aborted shotgun snap.** ESPN charges the yards lost back to the line of scrimmage as the quarterback's rushing yards and the defense's yards allowed; nflverse records no gain (2025 week 6 Chicago–Washington, week 15 Indianapolis–Seattle) | 3 lines | 0.5 QB; none for either D/ST |
| **Safety on a fake punt.** ESPN keeps it in points allowed (2025 week 4 Philadelphia); play-by-play has no special-teams flag on the play, only "Punt formation" in its description | 1 | none (same band) |
| **Unexplained points allowed.** ESPN shows 34 for Arizona, 2025 week 15; the final score was 40 and no Houston defensive score was recorded. A teammate's fumble recovered in the end zone counted in two 2026 cases, so it is not the rule | 1 | 2 |
| **Week 9 still settling.** ESPN's week-9 statistics moved by a yard after the nflverse import (Daniels, Okonkwo, Rams D/ST) | 3 | under 0.2 |

## Refused, not guessed

Play-by-play does not name who scored a defensive two-point return. When one happens, that team's players get no value for that category, and the scorer refuses their lines instead of assuming zero: 23 lines in 2025 and 14 in 2026 (R-061). A two-way player could have scored it. Slice 2 can rule players out with snap counts. Other refusals follow the same rule but were not triggered: a punting-team player's credit for a muffed-punt TD, and a one-point safety against a D/ST.

## Limits

- ESPN's pool holds current players, so 2025 players no longer in the pool were not compared.
- Two team abbreviations differ (`WSH`→`WAS`, `LAR`→`LA`). Every D/ST comparison checks the mapped team against the game joined by ESPN event ID; none mismatched.
- Definitions resting on one play are labeled above. A later contradicting play is a reason to revisit them, not to tune the gate.
- Older seasons use the same columns. No nulls were found from 2001 to 2026 in any column the adapter reads, but categories were only compared with ESPN for 2025 and 2026.

## Reproduce

```sh
# Replays the saved ESPN read (private, under data/model/); --capture DIR makes a new read.
ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \
  python scripts/model/verify_nflverse_scoring.py \
  --replay data/model/espn-verification-2026-11-09 \
  --output docs/research/nflverse-ffa-scoring-2026-11-09.json
```

The ESPN read was seven cookie-free GETs of ESPN's player pool, one per position slot and page, for per-week actual statistics across 2025 and 2026. Their receipt hashes, the stored rule hashes and each nflverse manifest are in the receipt.
