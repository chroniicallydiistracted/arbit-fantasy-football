# Handoff — 2026-11-04 — Kicks, tries, fumbles and penalties (automation slice 3)

## Current state

Branch `claude/platform-reset`, local only and not pushed.

- **Slice 2** is committed (`d21d565`) and accepted by the owner (OWN-034).
- **Slice 3 is done in code and not committed.** The owner asked for the open items and the records, not a commit.
- **Evidence** is in the [task record](../../superpowers/plans/2026-11-04-kicks-fumbles-penalties.md).
- **Owner review.** The owner's first review found the fumble's J.Jackson out of place and asked that defenders start at or behind the line of scrimmage. They kept the 2026 kickoff alignment (OWN-035). Both are fixed for every play, slice 2 included (ENG-036), and CHI at SEA was re-rendered in full for a second look.
- **The running app is unchanged.** Nothing in this slice reaches it until slice 7 serves scripts.
- **The dev database stopped again** on 2026-11-04 while WSL kept running. It was started by hand at 13:23 (UTC−7) and the worker resumed by itself (R-029).

## Completed work

- **Kicks.** `libs/arbit-data/src/arbit_data/live/kicking.py` (ENG-035).
  - **Field goals:** the snap goes to a holder 8 yards back, and the kicker approaches at his own pace. Each result is drawn through the real posts:
    - good: between the uprights into the net
    - wide left or wide right: outside that upright
    - off an upright or the crossbar: back off it
    - short: falls in front
    - blocked: off the blocker
  - **Punts:** a 15-yard snap and a spiral.
  - **Kickoffs:** off a tee, with the coverage held at the receiving 40 until the catch.
  - **Kick results:**
    - returned to ESPN's spot and tackled by the kicking team
    - fair catch, touchback, out of bounds, downed, muffed
    - short of the landing zone, onside
- **Tries.** `choreograph_try(facts, seed, names)` gives the extra point or two-point try after a touchdown as its own script: from the 15 or the 2, named from the try's own sentence.
- **Fumbles and penalties.** `libs/arbit-data/src/arbit_data/live/incidents.py`.
  - **Fumbles:** the play up to the hit, then the ball bouncing to ESPN's recovery spot. The recoverer falls on it, or scoops it and returns it.
  - **Fouls before the snap:** the penalized player at the line and a flag.
  - **Plays wiped out:** the play, a flag and "No Play".
  - **Penalties on plays that count:** a flag where that kind of foul happens.
  - **Flags:** each is tossed by the nearest official, who isn't drawn.
- **Contracts.**
  - `PlayScript` gains `props`, and an actor's `espn_id` may be empty for a player named only in the text.
  - `PlayFacts` gains `before`, the play described before a fumble or a flag that wiped it out.
  - Re-exported with `scripts/live/export_play_script_schema.py`, with a second example: a punt with a flag and a long snapper named from the text.
- **Spikes and names.** Spikes are drawn. Kickers, punters, returners and blockers are named from the text when the roster has no name.
- **Rule check.** `scripts/live/check_play_scripts.py` replaces the scratch checker. It prints what got a script, what didn't and why, and every broken rule.
- **Renderer adapter.** `scripts/sprites/render_script.py` draws flags, players named only in the text, the ball on the tee and in the hold, and tumbling kicks. It renders tries as their own clips (`<id>+try`), and `--slice3` renders a game's kicks, tries, fumbles and penalties.
- **Start positions (ENG-036).** The offense starts on or behind the line and the defense on or beyond it, no deeper than a safety. Nobody runs before the snap, and a new tackler starts within the sprint he has time for after it. Punt coverage releases at the snap. Kickoff coverage is 25 yards past any tee.
- **Records.** OWN-035, ENG-035, ENG-036, R-041, R-029 (2026-11-04), the task record with the owner review, slice 3 in the plan, the changelog, status and the `AGENTS.md` link.

## Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 856 passed, with the dev database started |
| `uv run ruff check .`, `ruff format --check .`, `mypy` | Passed |
| `pnpm check:contracts`, `pnpm check:client`, `make check` | Passed. Both play-script examples validate |
| `uv run python scripts/live/check_play_scripts.py` | 2,182 of 2,196 football plays and 72 of 74 tries scripted, 0 broken rules, including where every player starts and nobody running before the snap |
| `render_script.py`, in batches of 30 | All of CHI at SEA in `data/sprites/review/generated/`, re-rendered after the owner review |

**Checked by eye.**
- **Field goal:** the hold and the kick through the posts.
- **Fumble:** Lawrence strips it, scoops it and is tackled by Jackson.
- **Pass interference:** a play wiped out, which led to the flag placement fix.

## Decisions, issues and limitations

- **ENG-035** records the slice's rules.
- **R-041:** ESPN lists a fumble's tacklers together.
- **Stay as text:**
  - 10 aborted or loose snaps
  - 2 laterals and 1 trick play
  - 3 plays ESPN gives only as a scoring summary: 1 fumble and 2 tries
- **Labels without a roster:** two tacklers on one play stay unlabeled, since ESPN's order isn't the text's. The roster names them in the renders and in the app.
- **Flags** mark where a foul happened, not where it was enforced. Officials aren't drawn (OWN-032).
- **Muffed punts and kickoffs** show the muff and the loose ball, not who recovered it.
- **Returner hesitation.** On six kick and return plays the returner hesitates 0.7 to 1.2 seconds before the tackle. Either he was swarmed for no gain, or his kickoff coverage could only leave at the catch.
- **Positions are unknown.** The library doesn't know a player's position, so a guard who chases or a pass rusher who tackles may start where a receiver or safety would.

## Resume here

1. **Second owner look at CHI at SEA** after the OWN-035 fixes. Commit when asked.
2. **Next slice.** Slice 5, the jumbotron, or slice 6, Gridiron delivery, of the [plan](../../superpowers/plans/2026-11-03-live-play-automation.md). Slice 4, supporting players, is on hold (OWN-032).
3. See [status](../status.md) and the [roadmap](../roadmap.md).
