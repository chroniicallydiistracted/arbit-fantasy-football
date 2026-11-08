# Task: Plays built to their real time

Status: in progress, 2026-11-07 (OWN-051, OWN-052). Slices 1 and 2 are implemented (ENG-046): the fitter, the real time passed to the choreographer, the board's real-time clock, the 31-game baseline, and runs and scrambles built to time ([handoff](../../project/handoffs/2026-11-07-play-timing.md)). Runs await the owner's look at the review captures. Slice 3, passes, is next.

- **Requirement IDs.**
  - LV-003: canonical play graphics.
  - LV-005: late, revised and cancelled plays. Re-timing follows a play's stored revision.
- **Specifications and decisions.**
  - OWN-051: natural, while accurate to the real time of the play, now that the board's clock counts down with it.
  - OWN-052:
    - Build each play to its real snap-to-whistle time phase by phase, at natural speeds.
    - Fit plays we would overrun by shortening what we invent.
    - Natural overrun is only a last resort, which narrows OWN-048.
  - OWN-041: change movement and timing before the look of the animation, and never slow motion.
  - OWN-033 and OWN-037: one natural pace per player, receivers never slowed, ball and receiver arrive together, no frozen poses.
  - OWN-035 and OWN-036: alignment rules.
  - ENG-042: the uniform stretch (`pacing.py`) that this replaces.
- **Baseline.** [Play timing research](../../research/live-play-timing-2026-11-07.md): on Thursday's game the uniform stretch stops at about 1.3×.
  - 25 of 58 runs leave players standing more than a second beyond a natural whistle delay while the clock runs.
  - Ten kicks, punts, passes and a field goal keep moving after the clock stops.

## The timing contract (all slices)

- **The budget.** `choreograph(..., real_seconds=None)` receives the NFL's snap-to-whistle time. Without it, a play keeps today's natural timing.
- **Phases.** Each template plans its play as natural phases, each with a least, natural and most duration. `live/timing.py` fits them to the budget:
  - Phases with room grow toward their most, in proportion to their give.
  - Over budget, they shrink toward their least.
  - What can't be fitted is reported, never hidden.
- **Speeds stay natural.** Time comes from more football (a longer path, a later throw, contact, the dead ball), never from a slower stride.
- **The whistle is the real whistle.** `PlayScript.whistle` is the snap plus the real time, so the board clock runs one second per second and stops on the recorded end clock.
  - Players are done shortly before it: down, out of bounds, the ball dead.
  - The gap is a natural dead ball of 0.4–1.5 seconds: players untangling, getting up, an official coming in.
  - If even the least plan overruns, motion finishes after the clock stops, and the overrun is counted.

## Slices

1. **Contract and evidence.**
   - `timing.py` with the phase fitter and its tests.
   - The budget passed from `animation.build` to `choreograph` and the try choreographer.
   - The whistle at the real time.
   - The board's clock (`led.ts` `runningClock`, and `board.py` for the review clips) runs one second per second from the snap and stops on the play's end clock, whatever the clip's length.
   - `scripts/live/check_play_timing.py`, built from the [coverage audit](../../research/live-play-coverage-2026-11-05.md)'s 31-game harness. Per template it reports:
     - whistle error
     - dead time after the action
     - overruns with their least-plan cause
2. **Runs.** Phases, each with its least, natural and most:

   | Phase | Range | What fills it |
   | --- | --- | --- |
   | Mesh | 0.45–1.3 s | A delayed handoff or a fake takes longer. |
   | Path to the hole | 0.5–2.2 s | Shaped by the text's side and gap: an inside press, an outside stretch, a counter step. |
   | Gain | Fixed | The yards, at the carrier's own pace. |
   | Contact and drive | 0–1.6 s | The carrier in `drive` with tacklers in `wrap`, the pile moving 1.5–3 yards a second over the yards held back for it. |
   | The fall | 0.45 s | Unchanged. |
   | Dead ball | 0.4–1.5 s | Getting up, as above. |

   Sneaks and scrambles get the same budget. A scramble's flex is pocket time before he runs.
3. **Passes, sacks and interceptions.**
   - **Pocket time** sets the time to throw, 1.6–4.5 s, through the drop, set, hitch and slide steps.
   - **Routes** are shaped to the throw. The stem depth, break, come-back or crossing path change length at the receiver's natural speed, so he and the ball still arrive together.
   - **After the throw:**
     - air time by distance, as now
     - after a catch, the run with contact and drive as in runs
     - after an incompletion, a dead ball of 0.3–1.0 s
   - **Sacks:** pocket time and the escape take the flex.
   - **Interceptions:** the return takes it.
4. **Kicks and incidents.**
   - **Kickoffs and punts:** hang time fitted to the budget within natural ranges (kickoffs 3.6–4.8 s, punts 3.6–5.2 s) after the return's run, with the return path's shape as the second flex.
   - **Field goals and tries:** snap, hold and kick in 1.25–1.45 s, then the flight by distance, the result, and the dead ball.
   - **Fumbles, penalties, kneels and spikes:** phase budgets of their own.
5. **Retire the uniform stretch.** Remove `pace()` once every template is built to time. Run the full rule check on all 31 games, render review clips for the owner by type, then release outside game windows with the owner's approval.

## Acceptance

- **The clock.** On the 31 archived games, every timed play's whistle is the real snap-to-whistle time, within 0.05 s.
- **Dead time.** After the action, dead time is at most 1.5 s on 95% of timed plays. An overrun happens only when the least plan exceeds the real time, and each one is listed with its phase.
- **Natural motion.**
  - `check_play_scripts.py` finds no new rule breaks: no run below 5.5 yards a second, one pace per player, no frozen pose.
  - Defenders still start at or beyond the line.
- **The owner's review.** The owner reviews rendered clips per slice. Motion quality is the owner's call (OWN-022).

## Migration, rollback and data impact

- No migration. Scripts are rebuilt from stored revisions, and the cache key includes the revision.
- Rollback restores the uniform stretch.
- The release needs the owner's approval, outside game windows.
