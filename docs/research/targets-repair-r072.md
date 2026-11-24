# FFA targets repair: one code per franchise (R-072), 2026-11-24

TASK-20261123-007, ENG-058, under the owner's instruction that fundamental defects are repairs (OWN-075). Receipt: [targets-repair-r072.json](targets-repair-r072.json) (status `EXPLAINED`, 0 unexplained differences).

## The defect

nflverse's tables disagree about team codes:

| Table | Raiders | Chargers | Rams | 2012–2015 Cardinals, Ravens, Browns, Texans |
| --- | --- | --- | --- | --- |
| Schedule, snap counts | OAK to 2019 | SD to 2016 | STL to 2015 | ARI, BAL, CLE, HOU |
| Play-by-play, player and team statistics | LV | LAC | LA | ARI, BAL, CLE, HOU |
| Weekly rosters 2012–2015 | OAK | SD | SL | ARZ, BLT, CLV, HST |

The targets compared these codes directly, which broke three joins:
- **Player lines:** the opponent came from the schedule by comparing codes. For the relocated team's home games the comparison failed, so the team was named as its own opponent.
- **D/ST lines:** the scorer skips a game whose team row it can't find, so every game involving a relocated team had no D/ST line for either side.
- **Participation:** in 2012–2015, roster rows for nine franchises didn't match the schedule, so those players' roster-based labels (inactive, not on the active roster, active without a snap) were missing.

The DvP audit found it for 2016–2019. The repair's survey of every table for 2012–2026 found the 2012–2015 part: STL and the roster codes.

## The repair

- **`arbit_model.teams`:** maps every team field to the statistics tables' franchise code: OAK→LV, SD→LAC, STL→LA, and the roster codes ARZ→ARI, BLT→BAL, CLV→CLE, HST→HOU, SL→LA. Only codes seen in the stored files are mapped.
- **Where it applies:**
  - `targets` maps every table before any join;
  - `gamebook` maps the schedule and statistics (3b features);
  - `team_features` maps the schedule's context rows.
- **Fail closed:** the build refuses (`TeamCodeError`) any statistics, team, snap or play-by-play row whose team isn't one of its game's two teams, and any roster row whose team isn't on the season's schedule. The next unmapped code stops the build instead of joining wrongly.
- **Format:** the targets are now `arbit-ffa-targets-v2`: same schema as v1, with every `team` and `opponent` a franchise code.
- **Tests:** a relocated franchise scores exactly like a consistently coded one; roster codes keep their labels; stray teams are refused; a relocated team keeps its gamebook games. Removing the mapping fails them.

## How it was rebuilt and checked

1. **Same inputs:** `build_targets.py --inputs-of 4afbd836…` pins every nflverse manifest the old index's seasons read. The rules hashes are unchanged: athlete `10e938eb…`, D/ST `16885a80…`. The only change between the builds is the code.
2. **Deterministic:** built twice, from clean commits. Both builds produced identical season manifests and tables. The second build, index **`6ffb62fb…`** (code `9504631`), is the current pointer.
3. **Every row classified:** `targets_diff.py` matches rows by game and player, or by game and franchise for D/ST, and classifies each difference. It may touch only games of the franchises expected for that season: 2012–2015 the seven remapped franchises, 2016 LV and LAC, 2017–2019 LV. **Result: 0 unexplained.**

| Season | Player lines given their real opponent | Player lines with a code change only | D/ST lines added | Their FFA points | Participation labels added | Labels given their roster status | Labels with a code change only |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2012 | 803 | 1,489 | 92 | 695 | 1,691 | 2,866 | 1,694 |
| 2013 | 797 | 2,711 | 96 | 625 | 658 | 3,579 | 1,802 |
| 2014 | 787 | 2,480 | 88 | 629 | 683 | 3,716 | 1,695 |
| 2015 | 782 | 2,594 | 92 | 611 | 678 | 3,719 | 1,697 |
| 2016 | 526 | 1,748 | 62 | 340 | — | — | 2,242 |
| 2017 | 261 | 916 | 32 | 169 | — | — | 1,384 |
| 2018 | 273 | 886 | 32 | 165 | — | — | 1,557 |
| 2019 | 267 | 905 | 32 | 130 | — | — | 1,508 |
| 2020–2026 | byte-identical | | | | | | |

- **No player line's points changed.** The defect moved points to the wrong opponent; it never mis-scored a line.
- **Every season now has a D/ST line for every team-game:** 534 per season 2012–2019, regular season and playoffs.
- **Existing labels kept their label.** In 2012–2015 they gained the roster status and position the unmatched roster row held.
- **The 2016–2019 regular-season part** is the 1,327 lines and 156 D/ST team-games the DvP audit counted; the rest is playoffs and 2012–2015.

## What was rerun

| Study | Before | After |
| --- | --- | --- |
| [Signal study](ffa-signal-study-2026-11-23-r072.json): team rates, its own pinned inputs, its file unchanged | 317 team-seasons | 320 team-seasons; player measures identical |
| Team shrinkage constants (`feature_specs`) | takeaways 54.0, sack rate 23.0, defensive EPA 20.8, points allowed 22.4, plays 13.6, dropback rate 6.5 | 62.6, 21.4, 19.7, 22.0, 13.3, 6.4; offensive EPA 5.7 and points scored 7.5 unchanged |
| [DvP phase 1 audit](dvp/DATA_QUALITY.md) | D/ST 5,122 of 5,278 valid; 1,327 opponent mismatches | 5,278 valid; 0 mismatches; every check passes |
| [v0 on validated observations](dvp/V0_REPRODUCTION.md) (D/ST) | 315 offense-seasons, k 9.2 | 320, k 8.9 (95% by season 7–10); position measures unchanged |
| v0 itself | reproduces on `4afbd836…` | still reproduces exactly on `4afbd836…`, through a pointer of its own |

The defense-against-position constants in `feature_specs` are still v0's. The DvP research replaces them only through its Phase B decision (OWN-074).

## Reproducing

```bash
ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \
  python scripts/model/build_targets.py --output <main>/data/model \
    --inputs-of 4afbd8364fa7fd343ae3db2f4628c568f94f2e505b1eec1037aba33dd267ad18 --set-current \
    --reason "R-072 repair"
uv run python scripts/model/targets_diff.py --store <main>/data/model \
  --old 4afbd8364fa7fd343ae3db2f4628c568f94f2e505b1eec1037aba33dd267ad18 --new <index> \
  --expect 2012-2015=LV,LAC,LA,ARI,BAL,CLE,HOU 2016=LV,LAC 2017-2019=LV --out <receipt>
ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \
  python scripts/model/ffa_signal_study_r072.py docs/research/ffa-signal-study-2026-11-23-r072.json
```

The old index `4afbd836…` stays in the content-addressed store. Nothing deletes it.
