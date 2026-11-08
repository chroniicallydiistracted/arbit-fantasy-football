# Handoff — 2026-11-07 — Plays built to their real time

## Current state

The owner wants each play to look natural while matching its real time, now that the board's clock counts down with plays (OWN-051).
- **The owner's choices (OWN-052):**
  - Build each play phase by phase to its real snap-to-whistle time at natural speeds.
  - Fit plays we would overrun by shortening what we invent.
- **Progress.** [Plan](../../superpowers/plans/2026-11-07-play-timing.md) slices 1 and 2 are implemented (ENG-046): the timing contract, the real-time clock, and runs and scrambles built to time.
  - The owner reviews the run captures next.
  - Slice 3, passes, follows.
- **Not released.** Nothing in this work is on the running app; it needs the owner's approval, outside game windows.

The owner also set a later goal (OWN-050): recreate each team's actual stadium for its home games, keeping the generic stadium for international games. It hasn't been started.

## Completed work

- **`libs/arbit-data/src/arbit_data/live/timing.py`:** `Phase` and `fit`.
  - Phases grow by the same share of their room, or shrink toward their least.
  - Time they can't absorb is reported as `unfilled` or `over`.
- **The real time reaches the choreographer.**
  - `choreograph(..., real_seconds=)` and `kicking.choreograph_try(..., real_seconds=)` set `choreography.REAL_SECONDS` for the play states they make.
  - Every `_Play` has `budget`, `extra` (seconds per flexible phase), `timed` and `again()`. `again()` gives a fresh state that draws the same random choices.
  - `animation.build` passes each play's and try's NFL time.
- **`_to_time`** in `choreography.py`:
  - It builds the play naturally, then fits the template's flexible phases and the dead ball (`DEAD_BALL`, 0.4–1.5 s) with `timing.fit`.
  - It rebuilds the play from the same seed, up to four times.
  - Any error goes into, or comes out of, the drive, then the path, then the mesh.
  - It measures the play with any flag drawn in it.
  - It copies the final state into the caller's object, because incidents keep using the state they pass in.
  - `_finish` puts a timed play's whistle at `SNAP + budget`, and `_moments` is the shared whistle rule.
- **Runs** (`_run_phases`):
  - **The mesh:** up to 0.3 s. It is capped so the handoff stays by `HANDOFF_BY` (OWN-037).
  - **The path to the hole:** 1.5 s more for an end run, 1.2 s for tackle, 1.0 s otherwise. It bends up to three times its straight length through `_waypoint`, at the back's own pace.
  - **The pile:** `MOST_DRIVE` 2.5 s.
    - The carrier meets the tacklers sooner and churns `drive` with `stumble` (`_churn`, 0.2 s steps) while tacklers churn `drive` with `wrap` (`_wrap_toward(pile=...)`).
    - The pile moves `DRIVE_PACE` 1.6 yards a second over the ground he has. It always moves at least 0.5 yards a second, sideways when no ground is left.
  - **A scrambler's look** in the pocket: `SCRAMBLE_LOOK` 0.4 s natural, from 0 to 1.9 s.
  - **Sneaks** push longer.
- **Fumbles.** The run before a fumble and partial re-creations keep natural timing: `budget = None` in `incidents.py`, because their real time is the whole play's.
- **The clock.** `apps/web/src/live/led.ts` `runningClock`, and `scripts/sprites/board.py` for review clips, run the clock one second per second from the snap and stop on the play's end clock.
- **Evidence tools.**
  - `scripts/live/check_play_timing.py` reports whistle error, dead time and overruns by template. `--before` gives the old behavior: no real time, then the uniform stretch.
  - `scripts/live/check_play_scripts.py --paced` now builds to the real time as the API does.
- **Research and review.** [Play timing](../../research/live-play-timing-2026-11-07.md) has the corrected baseline and the slice 2 results. The review captures are private in `data/sprites/review/play-timing-2026-11-07/`, six before-and-after GIFs of Thursday's runs:
  1. a 1-yard pile
  2. a 2-yard run
  3. a no gain
  4. a 5-yard run
  5. a push out of bounds
  6. the 65-yard run
- **External state.**
  - The VS Code restart stopped `arbit-dev-postgres-1` (exit 255, R-029). It was restarted at about 13:47 Arizona time with `docker start arbit-dev-postgres-1`. `/health/ready` returned 200, and the worker rediscovered the 15 Week 9 games.
  - An isolated API ran on port 8021 against `arbit_local` for the captures, with a scratch web build (`vite build --outDir`). It was stopped by its PID afterwards.
  - The running app, its build and its services were not changed.

## Verification

- **Python.**
  - `uv run pytest -q -p no:cacheprovider`: 1,226 passed in 41 s. This includes `test_timing.py` (6) and `test_play_timing.py` (6).
  - `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy` (100 files) passed.
  - `python3 scripts/validate_foundation.py` passed.
- **Web**, in `apps/web`:
  - `npx --no-install vitest run`: 25 passed, including `led.test.ts`, which failed before `runningClock` existed.
  - `npx --no-install biome check src/live/` passed.
  - `npx --no-install tsc -b --noEmit` exited 0.
- **Timing.** `uv run --offline --env-file .env.local python scripts/live/check_play_timing.py` ran with:
  - `--weekly data/NFL_API_Expanded_Route_Tests/work/expanded/results/direct_weekly_details_full_raw.json`
  - `--weekly data/nfl-api/2026-11-05-week8-survey/expanded/direct_only_results/direct_weekly_details_week8_raw.json`
  - `--event 401873037`, with and without `--before`

  Runs with more than 1.5 s of dead time went from 36% to 2%, with a p90 of 2.6 s before and 1.2 s after. Scrambles went from 13% to 3%, and their overruns from 16 to 4. Run overruns stayed at 7. All 4,285 timed plays are still built.
- **Rules.** `uv run --offline python scripts/live/check_play_scripts.py --nfl=data/nfl-api/2026-11-05-week8-survey/expanded/direct_only_results/direct_weekly_details_week8_raw.json --paced`: 2,199 plays, 0 broken rules.
  - An early version broke the handoff deadline twice; it is now capped.
  - The Week 1 file yields no plays in this checker, which maps only Week 8 games.
- **Browser.** Playwright captured both servers at 20 fps on a paused page clock, stepping 1/20 s per frame. The running app was "before" and the isolated build "after".
  - The after clock read 4:17 at the snap and counted to 4:12 at the real whistle, one second per second.
  - In the 1-yard run, "before" has the carrier down by 2.6 s and lying there until 5.8 s. "After" holds the pile until about 4.2 s and has him down around 4.6 s.
- **Not run.** The browser suite (`pnpm --filter @arbit/web test:browser`): the board's markup didn't change, only its clock arithmetic. It is due before release.

## Decisions, issues and limitations

- **Decisions.** OWN-050, OWN-051, OWN-052 and ENG-046 are in the [decision register](../decision-register.md). OWN-052 narrows OWN-048: natural overrun is a last resort.
- **Remaining standing time.** Some runs still stand more than 1.5 s because the real play outlasted every phase's most. A 3-yard run, for example, took 7.8 s. Raising the most further would need new kinds of motion, such as a cutback or a second effort.
- **Overruns until slice 4.** Kickoffs, field goals and punts overrun because their timing is ours, not the NFL's.
- **Database restart policy.** R-029 recurs whenever WSL or the editor restarts. Changing the container's restart policy needs the owner's approval.

## NGS comparison

The owner supplied six NGS highlight captures of Jacksonville–Baltimore as a reference for how plays really happened (OWN-053).
- **The tool.** `scripts/sprites/ngs_compare.py` renders each play twice with the review renderer, BAL's field and both teams' kits:
  - from today's choreographer
  - from the tracking: only the players involved, at their tracked positions, with the ball's holders taken from the side in possession

  The two clips are stacked with matching timing.
- **Where it is.** The clips, `summary.json` and `FINDINGS.md` are private in `data/sprites/review/ngs-compare-2026-11-07/`. Neither the captures nor anything derived from them goes in Git.
- **What the comparison found:**
  - Quarterbacks throw early.
  - Play action isn't drawn.
  - The real handoff on the long run came after our handoff deadline.
  - Carriers and receivers are too slow, and their paths too short and straight.
  - Defensive backs and deep backs line up at the wrong depth.
  - Centers and quarterbacks stand still instead of blocking or following the play.
  - One receiver is drawn twice: the text says Zay, the roster Xavier.
  - A kickoff return with a challenge in its text isn't drawn.
  - Short passes fly too long.

## Resume here

1. **The owner reviews the run captures.** Apply any changes to the phases in `_run_phases` and the pile in `_carry`.
2. **Slice 3, passes, sacks and interceptions** (`_pass`, `_route`, `_sack`, `_interception` in `choreography.py`):
   - pocket time through the drop, set and hitch
   - routes shaped to the throw at the receiver's own pace (OWN-037)
   - the pile after a catch, reusing `_carry`'s drive
   - an incompletion's dead ball

   Measure with `check_play_timing.py` and `check_play_scripts.py --paced`. Recapture with `data/sprites/review/play-timing-2026-11-07/frames.mjs` and `gif.py` (private): pause the page clock after load, focus `button:has(canvas)`, press `r`, step 1/20 s per frame.

[Status](../status.md) · [Roadmap](../roadmap.md)
