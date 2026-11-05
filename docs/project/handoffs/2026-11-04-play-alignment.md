# Handoff — 2026-11-04 — Players line up by position and play their role (OWN-036)

## Current state

Branch `claude/platform-reset`, local only and not pushed.

- **Nothing new is committed.** Slice 3 (kicks, tries, fumbles and penalties), the OWN-035 review fixes and this work are all uncommitted. The owner commits when they ask.
- **The running app is unchanged.**
- **Waiting on the owner.** The owner compares one clip of each play type with the game's video. The clips are in `data/sprites/review/play-types/`, with each player's position on his name tag.
- **Records.** The [task record](../../superpowers/plans/2026-11-04-play-alignment.md) has the evidence, and the [slice 3 handoff](2026-11-04-kicks-fumbles-penalties.md) covers what came before.

## Completed work

- **`libs/arbit-data/src/arbit_data/live/alignment.py`** (ENG-037).
  - **Positions:** read from depth chart and roster rows. A 3-4's outside linebackers become edge rushers, WOLB and SOLB.
  - **Pre-snap spots:** a general spot for every position.
  - **First moves:** each position's first move after the snap, by play type.
  - **Kick coverage:** gunners wide.
- **The choreographer.**
  - **Placement:** new tacklers, chasers, pass defenders, interceptors, recoverers, sackers, blockers and penalized players start at their position's spot.
  - **Context from the play:** it decides a defensive back's side, and puts a corner or nickel back over the receiver the pass went to.
  - **Receivers and carriers** line up by position.
  - **Two-way players** line up for their side of the ball.
  - **Every actor** carries `position`.
  - **Without positions**, placement is as before, now kept clear of others.
- **Slice 1 fix.** Air yards use the text's own gain, not ESPN's net stat yardage, and yards after catch that don't fit are dropped.
- **Scripts.**
  - `scripts/live/positions.py` loads positions from the depth charts before a game.
  - `check_play_scripts.py` checks starting boxes and overlaps and reports first moves. `--no-positions` checks the fallback.
  - `scripts/sprites/audit_render.py` is the renderer audit.
  - `render_script.py` gained `--types` and `--position-tags`, and names players from the depth charts when the roster lacks them.
  - `export_play_fixtures.py` also writes `tests/fixtures/live/play-positions.example.json`.
- **Tests.** `libs/arbit-data/tests/test_alignment.py` checks:
  - spots and depth chart reading
  - two-way players
  - every fixture play's starts and rules with real positions
  - the fumble's Jackson and Lawrence
  - the punter's slot
  - corners over their receiver
  - wide receivers at least in the slot

## Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 980 passed |
| Ruff, format, mypy, `pnpm check:contracts`, `pnpm check:client`, `make check` | Passed |
| `uv run python scripts/live/check_play_scripts.py` | 2,182 of 2,196 football plays and 72 of 74 tries scripted. 5,243 of 5,244 drawn players have a position. 0 broken rules |
| `… --no-positions` | 0 broken rules |
| `uv run --with pillow --with numpy --with pyarrow python scripts/sprites/audit_render.py` | 2,254 scripts, 0 problems |
| `render_script.py --types`, then the full game in batches of 30 | 16 play-type clips, and every CHI at SEA clip |

**Checked by eye.** Every play-type clip's starting spots and first moves were read from its script. That look found two problems, both fixed and tested. The nickel back on Smith-Njigba's incompletion lined up across the field from him, and Smith-Njigba lined up 3 yards from the ball, like a tight end.

## For the owner's comparison

The game is CHI at SEA, 2026-11-02. Each clip's caption gives the quarter and clock.

| Clip | Play |
| --- | --- |
| 01 pass, complete | Q2 9:34, C.Williams deep middle to L.Burden for 23 (J.Love) |
| 02 pass, incomplete | Q1 14:16, S.Darnold short middle to J.Smith-Njigba, broken up by K.Gordon |
| 03 interception | Q4 6:01, S.Darnold intended for A.Barner, intercepted by J.Lynch |
| 04 sack | Q3 13:27, S.Darnold sacked by M.Sweat for −8 |
| 05 run | Q1 8:08, R.Johnson right tackle for 9 (T.Okada; E.Jones) |
| 06 scramble | Q4 3:49, S.Darnold scrambles for 14 (D.Bush) |
| 07 kneel | Q4 0:37, C.Williams kneels |
| 08 punt | Q1 1:48, T.Taylor punts, T.Horton returns 3 (J.Walker) |
| 09 kickoff | Q1 15:00, C.Santos kicks, G.Holani returns 23 (J.Sanborn) |
| 10 field goal | Q2 6:07, C.Santos 44 yards, good |
| 11 extra point | Q2 0:30, J.Myers, no good, wide left |
| 12 two-point try | Q4 11:46, S.Darnold to T.Horton, good |
| 13 fumble | Q4 13:14, C.Loveland fumbles, D.Lawrence recovers |
| 14 penalty before the snap | Q2 0:18, false start, J.Jackson |
| 15 play wiped out by a flag | Q2 1:03, pass interference on J.Johnson |
| 16 flag on a play that counts | Q1 5:25, sack by J.Simmons with a face mask |

## Decisions, issues and limitations

- **Decisions:** OWN-036, ENG-037; Q-013 resolved.
- **Base alignment only.** The depth chart is a team's base alignment, not the play's real formation, which no live source has.
- **Receivers' sides:** which receiver is in the slot, or on which side, comes only from the play's side.
- **The hash** isn't known.
- **Only named players are drawn (OWN-032)**, so the line and the other receivers aren't on the field.
- **No spike in this game**, so it has no spike clip.
- **The live app** will need positions from the stored depth charts when scripts are served (slice 7).

## Resume here

1. **The owner's comparison is in (OWN-037).** The fixes are planned and their fixtures prepared in the [play realism task](../../superpowers/plans/2026-11-04-play-realism.md):
   - fixture cases
   - `team-units.example.json`
   - `name_tag_preview.py`

   Start there once the owner picks a name-tag style and a pose source. Commit when asked.
2. **Next slice:** slice 5, the jumbotron, or slice 6, Gridiron delivery, of the [plan](../../superpowers/plans/2026-11-03-live-play-automation.md).
