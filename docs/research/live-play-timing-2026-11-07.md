# Play timing against the real clock — 2026-11-07

The owner asked for plays to look natural while matching the real time of the play, now that the board's game clock counts down with each play (OWN-051). This note measures how the current pacing (ENG-042, `libs/arbit-data/src/arbit_data/live/pacing.py`) lands on Thursday's Jacksonville–Baltimore game.

## Method

A read-only run of `animation.build` against the local database captured each clip before and after `pace()`. 123 of 145 clips have NFL snap and whistle times.
- **The action's end:** the last moment any player moves more than 0.3 yards in a segment, or the ball is in flight.
- **The board clock:** it runs from the snap to the clip's whistle (`apps/web/src/live/led.ts`).

The script and per-clip rows are private in `data/nfl-api/play-timing-2026-11-07/`, run with `uv run --env-file .env.local python data/nfl-api/play-timing-2026-11-07/measure.py 401873037`.

## Results

| Template | Clips | Real snap to whistle (median) | Our action, unpaced (median) | Idle with the clock running (median / p90) | Action past the real whistle |
| --- | ---: | ---: | ---: | ---: | ---: |
| run | 58 | 4.4 s | 1.9 s | 1.9 / 3.1 s | 0 |
| pass | 41 | 5.2 s | 3.2 s | 0.8 / 2.2 s | 3 |
| kickoff | 11 | 8.7 s | 8.5 s | 0.4 / 1.8 s | 4 |
| punt | 5 | 7.7 s | 6.6 s | 1.5 / 7.6 s | 2 |
| other | 8 | — | — | — | 1 |

- **Stretching stops at about 1.3×.** Pacing slows runs by a median 1.30× and passes by 1.31×. Beyond that the runner would fall below 5.5 yards a second and read as slow motion (OWN-033).
- **Runs end early.** Allowing a natural one second from the tackle to the whistle, 25 of 58 runs still leave players standing more than a further second while the clock runs (median 0.9 s, p90 2.1 s). Passes do this in 8 of 41.
- **Some plays overrun.** Ten clips keep moving after the clock has stopped at the real whistle, by a median 0.8 s: four kickoffs, two punts, three passes and a field goal (OWN-048 kept natural movement there).

## Why

Stretching a finished play can't add what a real play spends its time on. A real 4-yard run includes:
- the mesh
- the back's path to the hole
- contact and the drive through it
- the fall
- the dead ball before the whistle

Our run goes straight from the handoff to the spot. A real pass spends its time in the pocket and in a route's stem and break. A kick's time is mostly hang time, which we set rather than read.

## Baseline across 31 games

`scripts/live/check_play_timing.py --before` runs the production animation build without real times, then the uniform stretch, as the app did before. It covers the archived Week 1 and Week 8 weekly details and Thursday's stored game: 4,285 timed plays in 31 games. The action ends as `_finish` judges it: the last movement of the play, a player going down, or the ball landing.

A first version of this table counted a player lying on the turf twice. The finished script continues his last `ground` pose to the clip's end, and the helper took that continuation as a second fall, adding 0.3 s to every tackled play. The helper now counts going down once, and the table is corrected. Rows are private in `data/nfl-api/play-timing-2026-11-07/baseline-rows.json`.

| Template | Plays | Real (median) | Action (median) | Dead time p50 / p90 | Dead time over 1.5 s | Overruns |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pass | 1,792 | 5.0 s | 4.4 s | 0.4 / 2.2 s | 21% | 150 |
| run | 1,499 | 4.3 s | 2.9 s | 1.2 / 2.6 s | 36% | 7 |
| kickoff | 323 | 8.4 s | 8.9 s | 0.0 / 0.0 s | 2% | 198 |
| punt | 179 | 8.6 s | 6.6 s | 1.6 / 3.5 s | 54% | 15 |
| sack | 130 | 4.7 s | 3.5 s | 1.1 / 3.0 s | 40% | 7 |
| scramble | 115 | 6.7 s | 6.3 s | 0.0 / 2.0 s | 13% | 16 |
| field goal | 103 | 3.5 s | 4.4 s | 0.0 / 0.0 s | 1% | 92 |
| fumble | 47 | 7.2 s | 5.1 s | 2.1 / 4.3 s | 62% | 2 |
| interception | 41 | 7.5 s | 6.2 s | 0.9 / 4.0 s | 39% | 4 |
| all | 4,285 | 4.8 s | 4.0 s | 0.7 / 2.4 s | 27% | 492 |

An overrun is action more than 0.05 s past the real whistle. Kickoffs and field goals overrun because we set hang time and kick timing ourselves rather than read them.

## Runs built to time (slice 2)

The same 31 games, with runs and scrambles built to their real time:

| Template | Dead time over 1.5 s | Dead time p50 / p90 | Overruns | Clock stops on the real whistle |
| --- | ---: | ---: | ---: | ---: |
| run | 36% → 2% | 1.2 / 2.6 → 0.9 / 1.2 s | 7 → 7 | 100% |
| scramble | 13% → 3% | 0.0 / 2.0 → 0.7 / 1.1 s | 16 → 4 | 97% |
| all plays | 27% → 14% | | 492 → 480 | 89% |

The seven run overruns are plays whose natural motion is longer than the real one. In the remaining long-dead runs, the real play outlasted every phase's most: a 3-yard run, for example, took 7.8 s.
