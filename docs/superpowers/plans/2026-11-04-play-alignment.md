# Task: Players line up by position and play their role (OWN-036)

Status: done in code 2026-11-04; one clip of each play type rendered for the owner to compare with the game's video

- **Requirement IDs.**
  - LV-003: canonical play graphics.
  - The owner's review rules: OWN-032 (only the players in the play), OWN-033 (natural motion), OWN-035 (start on your side of the line).
- **Owner direction (OWN-036).** "yes, build it. We should ensure contextual logic in the renderer can understand where the player would generally start, along with what their role would be based on the play type and play description. Once you add the logic, be sure to run a full audit on the renderer, then render one animation for each play type."
- **Baseline.**
  - ENG-036 put every drawn player on his side of the line, but anywhere there: D.Lawrence, a 3-4 edge rusher, started 18 yards deep.
  - No live source has the real formation ([research](../../research/play-alignment-sources-2026-11-04.md), Q-013).
  - The 2026 depth charts give every team's base slots by ESPN ID, for 1,003 of the 1,009 players ESPN names in the captured plays.
- **Scope.**
  1. **`libs/arbit-data/src/arbit_data/live/alignment.py`.**
     - **Positions:** read from depth charts and rosters. A 3-4's outside linebackers become WOLB and SOLB, edge rushers.
     - **Pre-snap spot for every position:**
       - offensive line left to right across the ball, with the tight end inline on the strong side
       - backs and the quarterback by shotgun or under center
       - the defensive front at the line, with the left side opposite the offense's right
       - linebackers off the ball, corners wide, safeties deep
     - **First move after the snap**, by position and play type:
       - **pass:** a lineman or edge rushes the passer, a linebacker or defensive back backpedals into coverage, a receiver releases, and a blocker sets
       - **run:** a lineman takes on and sheds a block, and a blocker drives
     - **Kick coverage:** gunners wide and everyone else inside.
  2. **Context from the play.**
     - The play's side puts a defensive back who makes the play on that side, and a corner over the receiver he covers.
     - A tight end the pass goes to on the left makes the left the strong side.
     - A receiver lines up by his position: a tight end inline, a back in the backfield, a wide receiver on the line.
     - A ball carrier lines up by his: a designed quarterback run from the quarterback's spot, a sweep by a receiver or tight end from the slot.
     - A two-way player lines up at his position for his side of the ball. A defensive player on a punt team has no base spot.
     - A kick specialist shows his job's slot, such as P for a punter who also holds.
  3. **The script contract.** Each actor carries `position`, so any renderer knows who lines up where.
  4. **Wiring.** Positions go to `choreograph`, `choreograph_try`, fumbles and penalties alongside names. `scripts/live/positions.py` loads them for the scripts and the renderer, from the depth charts as they stood before the game.
  5. **Audit.**
     - **`check_play_scripts.py`** gains:
       - every player starting in his position's box
       - nobody starting on top of anyone
       - a table of each position's first move
       - a `--no-positions` mode for the fallback
     - **`scripts/sprites/audit_render.py`** is new and checks what the review renderer needs:
       - a sprite frame for every pose
       - somewhere for a carried ball to sit in every frame
       - flights between real players or points
       - a name tag for everyone ESPN names
       - captions that fit
- **Exclusions.**
  - The real formation, personnel and coverage of a live play: no live source has them.
  - Which receiver is in the slot or on which side, beyond the play's own side.
  - The hash.
  - Players ESPN doesn't name (OWN-032).
- **Acceptance.**
  - Every drawn player with a known position starts in his position's box and clear of everyone else, over every captured play. All other rules hold with positions and without.
  - The renderer audit finds nothing.
  - One clip per play type, with position tags, for the owner.
- **Rollback and data.**
  - No migration and no change to the running app.
  - Without positions the choreographer behaves as before, plus the keep-clear step.
  - The live app will need positions from the stored depth charts when scripts are served (slice 7).

## Evidence and outcome

**Fixed on the way** (the audit found them).
- **Impossible air yards (slice 1).** Air yards used ESPN's stat yardage, which is the net after an accepted penalty, so 4 passes had impossible air yards.
  - They now use the text's own gain ("for 12 yards").
  - Yards after catch that don't fit the gain or a deep pass are dropped, falling back to the depth's range (ENG-032).
- **Overlapping starts.** The fallback placement could start two tacklers on top of each other: 39 plays without positions, 2 kick coverages.
- **Slow-motion encroachment.** An encroaching lineman crossed the line in slow motion.
- **Two-way players.** Travis Hunter, a corner first, lined up at corner when carrying the ball.
- **A nickel back across the field.** Reading the play-type clips, the nickel back on Smith-Njigba's incompletion started across the field from him. A defensive back named on a pass now lines up over its receiver.
- **A receiver as close as a tight end.** Smith-Njigba lined up 3 yards from the ball, where he read as a tight end. A wide receiver now lines up at least in the slot, 6 yards out.
- **Missing name tags.** Six named players had no tag; they are now named from the depth charts when the roster lacks their ESPN ID.

**Checks.** All pass.

| Check | Result |
| --- | --- |
| `uv run python scripts/live/check_play_scripts.py` | 2,182 of 2,196 football plays and 72 of 74 tries scripted. 5,243 of 5,244 drawn players have a position. 0 broken rules |
| `… check_play_scripts.py --no-positions` | 0 broken rules |
| `uv run --with pillow --with numpy --with pyarrow python scripts/sprites/audit_render.py` | 2,254 scripts, 0 problems |
| `uv run pytest -q` | 980 passed. `test_alignment.py` checks spots, depth chart reading, two-way players, every fixture play's starts and rules with real positions, the fumble's Jackson and Lawrence, the punter's slot, corners and nickel backs over the receiver, and wide receivers at least in the slot |
| Ruff, format, mypy, `pnpm check:contracts`, `pnpm check:client`, `make check` | Passed |

**First moves after the snap**, over every captured play. A player makes his position's move when there's time before he has to get to the ball:
- **Run plays:** a defensive lineman takes on a block on 75 of 307 tackles.
- **Pass plays:**
  - a linebacker backpedals on 93 of 192 plays
  - a defensive back on 279 of 386
  - linemen and edge rushers rush the passer

**Renders.**
- **One per play type:** `render_script.py --types` writes 16 clips with position tags to `data/sprites/review/play-types/`, one for each play type in CHI at SEA. That game has no spike.
- **The full game:** CHI at SEA was re-rendered in full as the renderer's draw-everything check.
