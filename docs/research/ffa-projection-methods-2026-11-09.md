# FFA projections from nflverse alone: methods and measured signal

Observed **2026-11-09**. Research for the M3 Model under the owner's direction of the same day (OWN-061). It reviews how other analysts project NFL players from nflverse data, then measures on our own data which statistics drive FFA points and how quickly each one carries signal. The resulting architecture is proposed in [ADR-006](../architecture/decisions/006-model-architecture.md), and the work is sequenced in the [M3 plan](../superpowers/plans/2026-11-09-m3-model.md). [Machine-readable receipt](ffa-signal-study-2026-11-09.json).

## Owner direction and how it is applied

The owner's words: "Our model must EXCLUSIVELY use all fields of all currently active NFL players raw data stats using any and all relevant NFLVerse repositories. We will, and should never use any other providers FFA/Projection data. We must build our own projection model using what I just stated by weighing raw data against THE ESPN Family Fantasy Leagues scoring points. We have to take into account all of the potential data points, so we don't solely rely on an individual NFL players raw stats."

Applied as follows:

- **Inputs come only from nflverse repositories**, meaning everything nflverse publishes: play-by-play with its nflfastR model outputs, weekly player and team statistics, snap counts, Next Gen Stats, PFR advanced statistics, FTN charting, participation, injuries, rosters, depth charts, schedules, combine, draft picks, contracts, trades, officials, and QBR as nflverse republishes it. All 28 families are already imported ([audit](nflverse-data-audit-2026-10-31.md)).
- **Excluded everywhere** (inputs, training targets and benchmarks): any other provider's fantasy points, rankings, values or projections:
  - nflverse's own `fantasy_points` columns, which use generic scoring rather than FFA's;
  - ffverse expected fantasy points (`ff_opportunity`);
  - DynastyProcess values, rankings and projections;
  - ESPN draft probability files in nflverse `misc`;
  - ESPN's projections and player ratings, and draft position data from any source.
- **ESPN stays the league authority.** FFA's stored rules define the target, and ESPN's official points verified the nflverse-to-FFA conversion ([slice 1](nflverse-ffa-scoring-2026-11-09.md)). That is "weighing raw data against the FFA scoring points", not another provider's projection.
- **Every field is considered.** "All fields" becomes a catalog that gives every one of the 1,802 imported nflverse fields a recorded use, with a reason. A field enters the Model when it is available before the game and improves FFA-point accuracy out of sample. Nothing is dropped silently.
- **Every currently active NFL player at an FFA position gets a projection** (QB, RB, WR, TE, K, plus all 32 D/ST). The Model also *learns* from every historical player-game, retired players included. Training only on players active today would teach it from survivors, the players whose careers went well, and bias every projection upward.
- **Beyond a player's own statistics,** context enters through his team's volume and scoring environment, teammates' and opponents' availability, opponent defense, schedule, rest, venue and role.
- **Open for the owner (Q-014):** nflverse schedules carry betting lines (spread, total, moneylines), and play-by-play carries a line-based win probability. These are a betting market's forecast of the game, not fantasy data, but they are another party's projection. They stay unused until the owner decides.

## What other analysts do

| Work | Method | What Arbit takes |
| --- | --- | --- |
| nflfastR models (Carl and Baldwin; [Open Source Football, 2020](https://www.opensourcefootball.com/posts/2020-09-28-nflfastr-ep-wp-and-cp-models/); [fastrmodels](https://github.com/mrcaseb/fastrmodels)) | XGBoost expected points, win probability, completion probability, expected yards after catch and expected dropback. Validated leave-one-season-out, so no season predicts itself, with calibration checked in 0.05-wide probability bins (calibration error 0.005–0.008) | Season-grouped validation and binned calibration. Their per-play outputs (`ep`, `epa`, `cp`, `cpoe`, `xyac_*`, `xpass`, `pass_oe`) are nflverse fields and can be inputs. As documented in 2020 they were fitted on 2006–2019 (EP from 2000), so those seasons are in-sample for the play models. `fastrmodels` has been re-released since (2.1.0, February 2026), so the availability policy must record which model version produced each season's values |
| Expected fantasy points ([ffopportunity](https://github.com/ffverse/ffopportunity), Sydlowski and Ho) | XGBoost on nflverse play-by-play (2006–2020) giving each pass and rush an average player's expected yards, touchdowns and receptions: opportunity, not production | The idea, rebuilt ourselves and scored under FFA rules. Their outputs are another provider's fantasy data and are excluded |
| [Expected fantasy points for receivers](https://www.opensourcefootball.com/posts/2020-08-30-calculating-expected-fantasy-points-for-receivers/) (Open Source Football) | Completion probability × the yards-after-catch distribution per target, then Monte Carlo over a player's game. Notes it ignores individual skill and QB quality | Per-target simulation from nflverse's own models, with player and QB effects added and shrunk |
| [Rolling averages of EPA](https://www.opensourcefootball.com/posts/2020-12-29-exploring-rolling-averages-of-epa/) | Windows of 10–20 games spanning seasons beat a fixed 10; recency weighting helped most metrics; offensive EPA is far more predictive than defensive | Windows that cross seasons with recency weights. Defensive matchups lean on the opposing offense |
| [Opponent-adjusted EPA](https://www.opensourcefootball.com/posts/2020-08-20-adjusting-epa-for-strenght-of-opponent/); [team ability from EPA](https://www.opensourcefootball.com/posts/2021-06-27-estimating-team-ability-from-epa/) | Adjustment by lagged opponent averages raised game-outcome accuracy only from 63.5% to 64.0%. A hierarchical Student-t model with partial pooling pulls noisy team estimates toward the mean | Shrink team ratings. Treat opponent adjustment as a tested add-on, not a pillar |
| WOPR and RACR (Josh Hermsmeyer; [summary](https://www.cbssports.com/fantasy/football/news/2019-fantasy-football-draft-prep-how-should-i-use-air-yards-in-my-research-process/)) | 1.5 × target share + 0.7 × air yards share predicted fantasy points better than targets alone | Opportunity shares at the core. `wopr`, `racr`, `target_share` and `air_yards_share` are nflverse columns |
| Stabilization ([Footballguys](https://footballguys.com/article/tuccittotfp0wr), [4for4](https://www.4for4.com/node/173504)) | Receptions per route stabilize near 188 routes, yards per route 351, TDs per route 882. Year over year, targets per route (0.64) hold better than yards per route (0.56) | Shrink efficiency hard; measured on our own data below |
| Touchdown regression ([PlayerProfiler](https://www.playerprofiler.com/?p=54042), [Underdog](https://underdognetwork.com/football/2022-touchdown-regression-candidates-wrs-and-tes)) | Red-zone TDs correlate 0.11 year over year; red-zone target share is about three times as stable. Expected-TD models score each play by distance to the end zone, down and air yards | Touchdowns from expected TDs by field position and opportunity, not from a player's TD history |
| D/ST projection ([FantasyPros](https://www.fantasypros.com/2018/09/lets-stream-defenses-week-1-2018-fantasy-football), [Stokastic](https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-defense-strategy)) | Opponent's expected scoring first, then sacks and turnovers; a Poisson distribution turns points allowed into scoring bands | D/ST from the opponent's projected offense, simulated through FFA's exact bands |
| Teammate correlation ([4for4](https://www.4for4.com/fantasy-football/2018/preseason/definitive-guide-stacking-draftkings)) | QB with his top receiver is the strongest positive pairing; correlation changes the spread of outcomes, not the mean | Simulate teammates jointly from one team game; matchup and lineup ranges need it |
| Hierarchical Bayes ([Rome](https://srome.github.io/Bayesian-Hierarchical-Modeling-Applied-to-Fantasy-Football-Projections-for-Increased-Insight-and-Confidence); [Egidi and Gabry, JQAS 2018](https://arts.units.it/bitstream/11368/2929586/1/jqas-2017-0066.pdf)) | Partial pooling by position and team gives intervals that widen with little evidence | Priors by position, role and draft capital for rookies and new roles |
| [Fantasy Football Analytics](https://isaactpetersen.github.io/Fantasy-Football-Analytics-Textbook/) (Petersen, 2025) | Open textbook on nflverse data: mixed models, base rates, accuracy evaluation, bootstrapping, machine learning, with explicit overfitting warnings | Base rates for cold starts; evaluation practice |
| [Weekly projections from public data](https://theses-dissertations.princeton.edu/entities/publication/d6981488-f30c-47ce-8f06-b6c3e98f2578) (Williams, Princeton thesis, 2026) | Per-position XGBoost on 32,900 player-weeks (2022–2025): 2025 MAE 2.909 against ESPN's 3.074. Betting-market features carried 40–52% of model gain. Much of the edge came from predicting *whether a player plays* | Availability is a first-class model. Market features are powerful, which is why Q-014 matters. Under OWN-061 Arbit compares only against its own baselines |

None of these is adopted wholesale. Their recurring lessons:

1. Opportunity predicts better than production.
2. Efficiency and touchdowns regress heavily.
3. Validate across whole seasons.
4. Simulate rather than average.
5. Availability matters as much as talent.

## What our data shows

`scripts/model/ffa_signal_study.py` built FFA stat lines for every 2016–2025 regular-season player-game and D/ST team-game with the [slice 1 adapter](nflverse-ffa-scoring-2026-11-09.md), and scored them with the shared engine under FFA's stored rules. The population is the top 32 QBs, 64 RBs, 96 WRs, 48 TEs and 32 Ks per season by FFA points per game (8+ games), plus every D/ST team-game. 490 athlete lines were refused because a defensive two-point return had no named scorer (R-061) and are left out.

### Where FFA points come from

Variance share is each category's share of the spread in weekly FFA points, cov(category, total) / var(total). It says which statistics decide a good or bad week under FFA's rules (full PPR, 4-point passing TDs, banded field goals and D/ST bands).

| Position (player-weeks) | Mean, SD | Biggest drivers (variance share) |
| --- | --- | --- |
| QB (4,522) | 16.7, 8.2 | Passing TDs 45%, passing yards 27%, rushing TDs 11%, rushing yards 8%, interceptions 5% |
| RB (8,985) | 11.3, 8.4 | Rushing yards 33%, rushing TDs 30%, receiving yards 14%, receptions 14%, receiving TDs 9% |
| WR (13,562) | 11.0, 8.1 | Receiving yards 42%, receiving TDs 30%, receptions 26% |
| TE (6,536) | 8.1, 6.6 | Receiving yards 38%, receiving TDs 32%, receptions 28% |
| K (4,812) | 7.9, 4.6 | FG 0–39 32%, FG 40–49 30%, FG 50–59 28%, extra points 5%, misses 3% |
| D/ST (5,160) | 5.9, 6.6 | Yards-allowed band 23%, points-allowed band 20%, sacks 15%, interceptions 14%, interception TDs 9%, fumbles recovered 8%, fumble TDs 6% |

### How quickly each statistic carries signal

Split-half reliability compares each player-season's odd weeks with its even weeks. "Games for half signal" is the sample at which a player's own record and the population average deserve equal weight. It is exactly the shrinkage constant an empirical-Bayes projection needs: after *n* games, weight the player's own rate by *n* / (*n* + *k*).

| Statistic | Position | Games for half signal (volume) |
| --- | --- | --- |
| Offensive snap share | RB, WR, TE | 0.7–1.0 |
| Carry share | RB | 0.7 (18 team carries) |
| Target share | RB, WR, TE | 1.4–1.8 (47–60 team targets) |
| Targets per game | RB, WR, TE | 1.6–2.0 |
| Carries per game; rushing yards per game | QB | 1.2; 1.4 |
| Air yards share | WR, TE | 2.2–2.3 |
| Air yards per target (depth) | WR, TE | 3.3–5.5 |
| Pass attempts per game | QB | 3.9 |
| FFA points per game | RB / WR, TE / QB | 2.6 / 3.9–4.0 / 5.7 |
| Team offensive EPA per play; dropback rate | Team | 5.7; 6.5 |
| Points scored per game | Team | 7.5 |
| Passing yards per attempt; EPA per dropback | QB | 10.4 (342 attempts); 9.6 |
| Catch rate | WR / TE / RB | 13 (82 targets) / 21 / 138 |
| Passing TDs per attempt | QB | 13.6 (448 attempts) |
| Offensive plays per game | Team | 13.6 |
| Defensive EPA per play allowed; points allowed per game | Team | 20.8; 22.4 |
| Kicker FFA points per game | K | 22.5 |
| Sacks per opponent dropback | Team | 23.0 |
| D/ST FFA points per game | D/ST | 24.0 |
| Rushing yards per carry | RB | 34 (382 carries) |
| Field goal attempts per game | K | 38 |
| Yards per target | WR / TE / RB | 46 / 42 / 58 |
| Rushing TDs per carry | RB | 51 (571 carries) |
| Interceptions per attempt | QB | 53 (1,740 attempts) |
| Takeaways per game | Team | 54 |
| Receiving TDs per target | WR / TE | 56 / 85 |
| Field goal accuracy | K | 164 |

### What follows for the design

- **Opportunity first, efficiency shrunk.** Role and volume settle within one or two games. Per-touch efficiency, especially touchdowns, needs dozens of games. A projection is mostly expected opportunity times a heavily shrunk efficiency.
- **Touchdowns from the environment.** TDs are 30–45% of weekly FFA variance at every skill position, yet a player's TD rate is the least reliable statistic measured. TDs have to come from team scoring and each player's share of red-zone and goal-line opportunities.
- **Full PPR rewards volume.** Receptions are 26–28% of WR and TE variance, and target share is among the fastest statistics to stabilize. Rushing QBs are predictable, because QB carries settle in about one game.
- **Kickers belong to their offense.** Kicker points per game take 22.5 games to stabilize, and accuracy takes 164, so it is nearly noise. FG attempts by distance come from the team's drives, with league make rates by distance and venue.
- **D/ST is mostly the opponent.** D/ST points take 24 games to stabilize, and the yards and points bands drive 43% of the variance. Offensive EPA stabilizes almost four times faster than defensive EPA allowed (5.7 against 20.8 games). D/ST comes from simulating the opponent's offense, plus the team's own pass rush, through FFA's exact bands.
- **Team environment is an early, strong input.** Dropback rate and offensive efficiency settle within about six games, and they set the volume every player shares.

**Limits.** These are within-season reliabilities over relevant players. Restricting to starters narrows the range and understates reliability, and mid-season role changes blur it. They set starting shrinkage constants and priorities; the backtest decides final values.

## Data available before a game

Checked in the stored nflverse files on 2026-11-09:

- **Weather is not a pre-game input.** `temp` and `wind` are empty for every 2026 game, even completed weeks 8 and 9. In 2023–2025 they are filled after the fact for 499 of 549 outdoor games. Only `roof` and `surface` are known before kickoff.
- **Betting lines and expected starting QBs** (`home_qb_id`, `away_qb_id`) appear about one week ahead: present for week 10, absent for week 11. Lines are pending Q-014.
- **Weekly roster status `INA` reaches nflverse only after the game.** Inactives are announced about 90 minutes before kickoff, but nflverse publishes rosters once a day at 07:00 UTC. Arbit's imports saw week 9's inactive marks appear only after each game (0, then 10 after Thursday's game, 171 after Sunday's). So no projection can use them for that game ([ADR-007](../architecture/decisions/007-model-availability.md), corrected 2026-11-10).
- **Injury reports** (`report_status`, practice status) cover 2026 weeks 1–9 and are the main pre-game availability evidence.
- **Participation is published after the postseason:** routes, coverage, personnel and pressure. Within a season it can only feed priors from earlier seasons.
- **Depth charts** are timestamped observations from 2025 on, and FTN charting lags the games by days.
- **Historical vintages:** files observed since the first local import on 2026-10-31 are real point-in-time evidence. Earlier seasons need the retrospective policy (Q-005) before any backtest.

The imported catalog has 1,802 distinct family-and-field pairs. Use by family:

| Family (fields) | Use |
| --- | --- |
| Play-by-play (372) | History: per-play opportunity (targets, air yards, yard line, down, red zone, goal line), nflfastR outputs (EP, EPA, CP, CPOE, xYAC, xpass, pass rate over expected), drives, penalties. Same-game values are outcomes only |
| Weekly player (153) and team (140) statistics | History and the FFA training target. `fantasy_points*` excluded |
| Legacy `player_stats` (130) | Duplicates of the weekly statistics; reconciliation only |
| Snap counts (16) | History from 2012; participation labels |
| Next Gen Stats (51) | History from 2016: separation, cushion, time to throw, aggressiveness, expected completion, expected YAC, rushing yards over expected |
| PFR advanced (122) | History from 2018: pressures, blitzes, drops, bad throws, broken tackles, yards before and after contact, coverage allowed |
| FTN charting (29) | History from 2022, with publication lag: play action, RPO, screens, motion, catchable and contested balls, created receptions, interception-worthy throws, box count, blitzers |
| Participation (26) | Earlier seasons only: routes, coverage, personnel, pressure |
| Injuries (17), weekly rosters (36), depth charts (26), trades (11) | Pre-game availability and role for the player, his teammates and the opponent |
| Schedules (46) | Pre-game: home, rest, roof, surface, division, coaches, expected QBs. Scores are outcomes. Weather is not pre-game. Lines pending Q-014 |
| Players (39), rosters (36), combine (18), draft picks (36), contracts (27) | Static facts and priors: age, size, experience, draft capital, athletic testing, contract |
| Officials (9), QBR (30) | Candidates; must show out-of-sample benefit |
| Teams (16), players components (42) | Identity |
| `misc` (39) | ESPN draft probabilities excluded; reference tables only |
| ffopportunity (219), DynastyProcess (95), test (21) | Excluded (OWN-061; diagnostic). The DynastyProcess ID directory stays an identity source only |

## Recommendation

Adopt [ADR-006](../architecture/decisions/006-model-architecture.md) (accepted by the owner on 2026-11-09, OWN-062): a team-first model that simulates whole stat lines, built only from nflverse and scored by the shared engine under FFA's rules.

The first release is the interpretable Baseline A, shrunk with the constants measured above. Gradient-boosted component models and a direct-points challenger follow, promoted only if they pass the release gate. Q-005 (retrospective availability) and Q-014 (betting lines) come before any backtest.

## Reproduce

```sh
ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \
  python scripts/model/ffa_signal_study.py docs/research/ffa-signal-study-2026-11-09.json
```

Read-only against the object store and the stored rules. The receipt pins the rule hashes, the adapter version and the 42 nflverse manifests it read.
