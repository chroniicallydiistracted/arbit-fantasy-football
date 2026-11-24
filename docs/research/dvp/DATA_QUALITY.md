# M3-3 DvP data quality

Specification §3.3, tests T01–T07, T30, T34. Receipts:
- [audit-receipt.json](audit-receipt.json) (checks, reconciliation, anomalies, examples) and [SCORE_FINALITY_AUDIT.json](SCORE_FINALITY_AUDIT.json);
- run `phase1-audit-20261124T021910Z`, code `bc414a0`, on targets index `6ffb62fb…` (R-072 repaired; [targets-repair-r072.md](../targets-repair-r072.md)). The first run, `phase1-audit-20261123T222517Z` on index `4afbd836…`, found the defect;
- the observation table is `artifacts/dvp/<run>/observations.parquet`, ignored by git, with its hash in the run manifest.

## Checks (all PASSED)

| Check | Result |
| --- | --- |
| T06: completed regular-season team-games | **5,278** = 5 × 512 + 4 × 544 + 542 |
| T06: two mirrored team-games per completed game, no duplicate game IDs | 0 violations |
| T06: teams and games per season | 32 teams every season; 16 games each in 2016–2020, 17 in 2021–2025; BUF and CIN 16 in 2022 |
| T34: the canceled 2022 BUF–CIN game | Absent from nflverse's schedule; 271 completed 2022 games; no team-game and no zero for it |
| T05: every target line belongs to a completed team-game; no player has two lines in a game | 0 and 0 |
| T30: the targets were scored with the league's current FFA rules | athlete `10e938eb…`, D/ST `16885a80…` equal the rules in the current league document |
| T30: each line's points equal the sum of its rule contributions | 257,914 lines checked, 0 mismatched |
| T37: targets index rules equal the configured rules | yes |
| T31: no provider projection in the scoring path or the DvP code | 0 findings ([provenance](SOURCE_PROVENANCE.md)) |

Positions come from the league's lineup slots: QB, RB, WR, TE, FLEX, DST, K, BENCH, IR. FLEX draws on RB, WR and TE, so the modeled groups are QB, RB, WR, TE, K and DST. FB and HB count as RB, PK as K. K and D/ST are lineup slots, so both are in scope.

## Cell status (26,390 position cells and 5,278 D/ST cells)

| Group | Valid | Not usable |
| --- | --- | --- |
| QB | 5,278 | — |
| RB | 5,265 | 13 refused line |
| WR | 5,261 | 17 refused line |
| TE | 5,264 | 14 refused line |
| K | 5,264 | 14 refused line |
| D/ST conceded by the offense | 5,278 | — |

**Refused lines (58 cells, 2016–2025).** A line is refused when the scorer can't verify a statistic it needs. Three statistics were refused:
- a defensive two-point return the play-by-play doesn't attribute to a player;
- a punt-return touchdown;
- a fumble-recovery touchdown.

Refusals cluster by team-game: one unattributed event leaves every player who might have been involved unscored. Those cells carry no points. v0 summed them as zero.

**Missing D/ST lines: none since the R-072 repair.** On the original index, 156 team-games had no D/ST line (60 in 2016, 32 in each of 2017–2019): the Raiders 2016–2019, the Chargers 2016 and every D/ST that played them ([V0_REPRODUCTION.md](V0_REPRODUCTION.md) #2). The repaired index scores all of them.

**True zeros (valid cells with 0.0 points):**

| Group | True zeros |
| --- | --- |
| QB | 9 |
| WR | 1 |
| TE | 109 |
| K | 162 |
| D/ST | 266 |
| RB | 0 |

A cell is zero only when the team-game has target rows. A team-game without rows would be `missing_coverage`; there are none.

**Negative cells** are preserved:

| Group | Negative cells | Lowest |
| --- | --- | --- |
| D/ST | 820 | −12.0 |
| K | 50 | −3.0 |
| QB | 27 | −6.66 |
| TE | 4 | — |
| WR | 1 | — |

## Anomalies

- **Opponent misattribution (R-072), repaired:** 0 rows whose recorded opponent disagrees with the schedule.
  - **Before the repair:** on index `4afbd836…`, 40 home games (Raiders 2016–2019, Chargers 2016) had 1,327 player lines and 3,994 FFA points naming the team itself as the opponent. The observations always took the opponent from the schedule, so the position cells were right then too.
  - **The repair:** every team code in every table becomes a franchise code (`arbit_model.teams`), and the build refuses a row whose team didn't play in its game. The targets were rebuilt on the same inputs. Every difference was classified and none was unexplained ([targets-repair-r072.md](../targets-repair-r072.md)).
- **Team codes:**
  - **Schedule:** OAK through 2019 and SD in 2016 (the raw codes are kept in the receipt).
  - **Targets:** LV, LAC and LA everywhere since the repair. Before it, player statistics used LV and LAC, but zero lines built from snap counts used OAK and SD.
  - **In the DvP view:** `FRANCHISE` (now `arbit_model.teams`) maps OAK to LV, SD to LAC and STL to LA, plus the 2012–2015 roster codes.
- **Traded players:** 645 player-seasons have lines for two franchises. Every line belongs to a completed team-game of the team named on it, so each game's points go to that game's team.
- **Points on positions outside FFA's groups:** 1,030 lines, 4,312.52 points. These are defensive and line players' return and recovery touchdowns, and the occasional trick-play pass. They are not a rosterable FFA position's production and aren't summed.

## Examples checked by hand (§3.3)

- **Zero-production TE:** 2025 week 1, TB at ATL. Tampa Bay's three tight ends with statistics lines scored 0.0 between them, so the cell is a valid 0.0, defense ATL. Seven 2025 TE cells are true zeros.
- **Multi-WR offense:** 2025 week 1, ARI at NO. New Orleans' five WR lines sum to the cell, defense ARI:

  | | Five WR lines | Cell |
  | --- | --- | --- |
  | FFA points | 5.6 + 12.4 + 9.3 + 0.0 + 2.3 | 29.6 |
- **Traded player:** player `00-0026158` has lines for CLE in weeks 1–4 (12.2, 8.76, 3.68, 1.26) and for CIN in weeks 6–18. Each line sits in its own team's cell.
- **D/ST with turnovers:** 2025 week 1, CAR at JAX. Jacksonville's D/ST scored 12 = 2 interceptions × 2 + 1 fumble recovery × 2 + 1 sack × 1 + 3 for 10 points allowed + 2 for 255 yards allowed. The observation row has offense CAR, defense JAX, unit CAR and points 12.0: what Carolina's offense conceded to an opposing D/ST.
- **Canceled game:** 2022 week 17, BUF at CIN. Not in the schedule, no team-game, no zero cell. Both teams have 16 games.

## Finality and vintage (SCORE_FINALITY_AUDIT.json, A12 and B12 to follow)

- **Source of these seasons:** the targets were built on 2026-11-10 from nflverse files Arbit first read between 2026-10-31 and 2026-11-10.
- **Only final revisions:** every value is the final revision, and when a stat correction first appeared can't be replayed.
- **Conservative rule:** a game's FFA actuals count from 12:00 UTC the day after its game day (`timing.STATISTICS`), labeled retrospective. This is a backtest limitation, not vintage certainty.
