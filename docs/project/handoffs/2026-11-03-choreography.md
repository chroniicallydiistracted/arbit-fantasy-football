# Handoff — 2026-11-03 — Play scripts (automation slice 2)

## Current state

Branch `claude/platform-reset`, local only and not pushed.

- **Earlier commits.** Slice 1 (`37bba10`) and the R-039 fix (`63e0a28`) are committed.
- **The 21:16 upgrade** was approved by the owner and recorded in `24d90e8`. The running app has the play normalizer (ENG-033) and the Live team context (R-039); it was offline 5 seconds. The worker now stores `yardLine`, yards after catch, penalties and reviews.
- **Slice 2 is done.** The owner accepted it on 2026-11-04 (OWN-034), and it is committed with this handoff. Its evidence is in the [task record](../../superpowers/plans/2026-11-03-choreography.md). The owner reviews CHI at SEA rendered from generated scripts before any slice 3 work.

## Completed work

- **Choreographer.** `libs/arbit-data/src/arbit_data/live/choreography.py` defines `PlayScript` v1 and `choreograph(facts, seed)`.
  - **Templates:** passes (complete, incomplete, thrown away, screen), interceptions, sacks, runs by gap, scrambles, sneaks and kneels. It returns nothing for other templates or missing facts.
  - **Frame:** field yards, with x from the offense's goal line and the offense attacking toward 100, z from the near sideline, and y up. A segment may face its own way.
  - **The ball:** resting, held, or in flight from a hand or point to catching hands or a point, resolved by the renderer.
  - **Seeding and speeds:** choices are seeded by play ID and revision, and speeds are bounded by pose class (ENG-034).
- **Contract.** `packages/contracts/schemas/play-script.schema.json` and the example `tests/fixtures/live/play-script.example.json` come from `scripts/live/export_play_script_schema.py`, and are checked by `pnpm check:contracts` and a schema test.
- **Renderer adapter.** `scripts/sprites/render_script.py`. Run it with `--compare` for the five plays that also exist hand-made, `--all` for every scripted play, or play ID suffixes for single plays. It uses the full-field view and CHI at SEA's listed uniforms and field, writing GIFs and scripts to ignored `data/sprites/review/generated/`.
- **Tests.** `libs/arbit-data/tests/test_choreography.py`, 69 rule tests.
- **Owner review (OWN-033).** Movement was reworked to natural pace, with routes setting the timing, pocket footwork and settling with a side step. Names come from the roster by ESPN ID. Passes after a direct snap to someone else (trick plays) show their text.
- **Records.** OWN-033, ENG-034, the task record, the plan's slice 2 status, the changelog, status and the `AGENTS.md` link.

## Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 729 passed |
| `uv run ruff check .`, `ruff format --check .`, `mypy` | Passed |
| `pnpm check:contracts`, `pnpm check:client`, `make check` | Passed |
| Rule check over all 14 captured games, scratch script | 1,705 scripts: 826 passes, 724 runs, 71 sacks, 42 scrambles, 24 interceptions and 18 kneels. No rule broken, including the natural-motion rules: no run below 5.5 yards a second, one pace per player, no standing pose still more than 0.6 seconds after the snap |
| `render_script.py`, in batches of 10, after the rework | CHI at SEA's scripted plays, now without the trick play |

**Checked by eye.** Contact sheets of the generated touchdown pass, pass and tackle, run, sack and interception.

**Owner review.** The first look found the timing problems that were then fixed (OWN-033). The reworked plays were accepted (OWN-034).

## Decisions, issues and limitations

- **ENG-034** is the script frame, hand-resolved ball, speed classes and the tackler who chases.
- **Runs:** the quarterback isn't drawn, so the ball travels from the line to the runner.
- **Incompletions:** coverage appears only when ESPN names a pass defender.
- **Not in this slice:** spikes, two-point tries, kicks, fumbles and penalties wait for slice 3. It must use the measured 8-yard hold for place kicks.
- **No browser renderer yet.** Scripts aren't served; that is slice 7.

## Resume here

1. Slice 3 of the [plan](../../superpowers/plans/2026-11-03-live-play-automation.md): kicks, fumbles and penalties.
2. See [status](../status.md) and the [roadmap](../roadmap.md).
