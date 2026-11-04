# Task: Generate play scripts for passes, runs, sacks and interceptions (automation slice 2)

Status: **verified**, 2026-11-04: the owner accepted the reworked plays (OWN-034)

- **Requirement IDs.** LV-003 (play graphics). LV-005 (a revised play gets a new script, because its facts and revision change).
- **Specifications and decisions.**
  - [Automation plan](2026-11-03-live-play-automation.md), items 2, 5 and 6.
  - [Slice 1](2026-11-03-play-facts.md).
  - OWN-021 and OWN-032 (only the players ESPN names), OWN-030 (the full-field view is the standard).
  - ENG-023 (re-creation label), ENG-030 (ball spin), ENG-032 (catch spot), ENG-033 (spots).
- **Baseline.**
  - `PlayFacts` v1 for every stored play.
  - The seven CHI at SEA plays choreographed by hand in `scripts/sprites/real_plays.py`, whose pieces (`throw`, `catch`, `tackled`, `tackler`) the owner accepted.
  - The Python renderer `scripts/sprites/preview.py`.
- **Scope.**
  1. **Script contract.** `PlayScript` v1, exported as JSON Schema to `packages/contracts/schemas/play-script.schema.json` with an example, and checked by `pnpm check:contracts`.
     - It holds actors, each with an ESPN ID, role, side, label from the text, facing, and timed segments of pose and movement in field yards; the ball as timed segments (resting, held by an actor, or in flight from one place or actor to another with a spin); the lines; the caption; and the re-creation label.
     - The frame is x for yards from the offense's own goal line, with the offense attacking toward 100; z for yards from the near sideline; y for height.
  2. **Choreographer.** `libs/arbit-data/src/arbit_data/live/choreography.py`, with `choreograph(facts, seed) -> PlayScript | None`, for the pass (complete, incomplete), interception, sack, run, scramble, sneak and kneel templates.
     - **Seeding.** Choices are seeded by play ID and revision: the spot between the hashes, routes, time to throw, alignments and where tacklers come from.
     - **Timing.** It solves timing so the carrier ends on ESPN's spot, the ball reaches the receiver's hands at the catch, tacklers meet the carrier there, and no one exceeds a plausible speed.
     - **Unsupported plays.** It returns nothing for a play whose facts say it has no template or is missing a fact.
  3. **Renderer adapter.** `scripts/sprites/render_script.py` draws a script with the existing renderer in the full-field view and the game's listed uniforms and field. It resolves where the ball sits in a hand from each frame's anchors.
- **Exclusions.** Kicks, fumbles and penalties (slice 3); the browser renderer (slice 7); players ESPN doesn't name (OWN-032).
- **Acceptance.** Tests on the slice 1 fixture plays check rules:
  - the carrier ends on ESPN's spot
  - only named players appear
  - the ball and the receiver meet at the catch
  - no one moves in a standing pose faster than a step, and no one faster than a sprinter
  - the ball is always somewhere, resting, held or in flight
  - the same play gives the same script
  - the schema and its example are current

  Evidence: CHI at SEA rendered from generated scripts, with the hand-made plays beside them, for the owner's review.
- **Rollback and data.** No migration and no change to the running app. Scripts are computed on request and stored nowhere.
- **Decisions to record.** The script frame and the hand-resolved ball, a new engineering decision.

## Evidence and outcome

**Implemented.**
- **Choreographer.** `libs/arbit-data/src/arbit_data/live/choreography.py`, with `PlayScript` v1 and `choreograph`.
  - Pass templates: complete, incomplete, thrown away and screen.
  - Also interception, sack, run (by gap), scramble, sneak and kneel.
  - Spikes and two-point tries return nothing for now.
- **Schema and example.** `packages/contracts/schemas/play-script.schema.json` and `tests/fixtures/live/play-script.example.json`, both from `scripts/live/export_play_script_schema.py`. `pnpm check:contracts` validates the example.
- **Renderer adapter.** `scripts/sprites/render_script.py`. Segment facing is honored, and a held or caught ball is placed from each frame's anchors.
- **Tests.** `libs/arbit-data/tests/test_choreography.py`, 69 tests.

**Rules over every captured play.** All 1,706 plays with these templates in the 14 captured games got a script: 827 passes, 724 runs, 71 sacks, 42 scrambles, 24 interceptions and 18 kneels. None had any of these problems:
- a speed over its pose class
- a gap in a timeline or in the ball
- a carrier off ESPN's spot
- a touchdown short of the goal line
- an unnamed player
- a player drawn twice

**Found by looking at the renders, and fixed:**
- **Interception tackler.** He started ahead of the return, in the end zone; tacklers on a return now chase from behind.
- **Name tags.** The text's tackler names were lost, because the sentence split broke names at their initials.
- **Captions.** They ran into the extra point; they now end at the play's sentence.
- **Players drawn twice.** A tackler already on the field could have been drawn again; he now chases from where he is.

**Commands.**

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 729 passed |
| `uv run ruff check .`, `ruff format --check .`, `mypy` | Passed |
| Ruff check and format, line length 120, on the new scripts by file | Passed |
| `pnpm check:contracts`, `pnpm check:client`, `make check` | Passed |
| `uv run --with pillow --with numpy python scripts/sprites/render_script.py --compare` | The five plays `real_plays.py` makes by hand, generated: td-pass, pass-tackle, run, sack, interception |

**Owner review and rework (OWN-033).** The first renders solved timing by stretching strides:
- **Receivers** ran their routes at 2 to 4 yards a second to meet the throw, then sped up after the catch.
- **The quarterback** froze in his set for over a second, then threw quickly.

The choreographer was reworked so timing follows from natural movement:
- **One pace per player,** drawn once.
- **Routes set the release.** A short receiver gets to his spot, settles facing the passer with a side step and comes back to the ball. A deep one catches in stride, on a bending route if the throw needs more time.
- **The quarterback** takes a quick, three-step or five-step drop matched to the throw, works his feet in the pocket, sets for 0.15 seconds and throws. The ball travels about 26 yards a second, 22 on deep throws.
- **Defenders** set with a side step, then break at full speed. Rushers take a longer edge path rather than a slow straight one.
- **A carrier** weaves instead of slowing.
- **Anyone standing** at the end keeps a small side step.

Three new rules hold on all 1,705 scripts: no run below 5.5 yards a second, one pace per player, and no standing pose held more than 0.6 seconds after the snap.

**Names and plays not to draw (OWN-033).** An audit of CHI at SEA's 125 scripts found 5 wrong labels from three causes:
- an eligibility report naming the wrong passer
- a direct-snap trick play
- two tacklers listed in a different order from ESPN's roles

Names now come from the 2026 roster by ESPN ID, and from the text only when a role names exactly one player. Passes after a direct snap to someone else are trick plays and show their text (1 in the captured games). Plays with accepted penalties enforced after the play, injuries or a two-point try after a touchdown are still drawn, because the play itself happened.

**Limits.**
- **No players added.** Only the players ESPN names are drawn, so the other team's coverage on an incompletion appears only when a pass defender is named.
- **Handoffs.** The quarterback isn't drawn on runs, so the ball travels from the line to the runner.
- **Not here yet.** Spikes, two-point tries, kicks, fumbles and penalties are slice 3.
- **Pose library.** Falls use the existing tackle poses; there are no blocking or stance poses, and none are needed while only named players appear.
