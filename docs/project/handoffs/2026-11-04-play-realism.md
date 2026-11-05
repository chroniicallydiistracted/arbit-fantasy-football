# Handoff — 2026-11-04 — Play realism from the owner's video comparison (OWN-037, OWN-038)

## Current state

Branch `claude/platform-reset`, local only and not pushed.

- **Nothing new is committed.** Slice 3, the OWN-035 and OWN-036 work and this work are uncommitted. The owner commits when they ask.
- **The running app is unchanged.**
- **Waiting on the owner.** The owner compares the 19 clips in `data/sprites/review/play-types-2/` with CHI at SEA's video.
- **Records.** The [task record](../../superpowers/plans/2026-11-04-play-realism.md) holds the plan, the owner's answers and the evidence. The [play alignment handoff](2026-11-04-play-alignment.md) covers what came before.

## Completed work

Each of the owner's notes is built (ENG-038):
- **Passes:** the ball and receiver arrive together, with bullets for short passes only.
- **Coverage:** covering defenders backpedal and mirror the receiver with a cushion. Tacklers come from their own side.
- **Poses:** waiting and idle poses that aren't the quarterback's.
- **Interceptions:** the intended receiver is drawn, and passes tipped at the line are drawn as tips.
- **Sacks:** the quarterback escapes right.
- **Snaps:** the center and the long snapper snap the ball.
- **Runs:** the quarterback hands off, with jet motion on receiver sweeps.
- **Fouls:** pass interference, holding, illegal contact and offensive pass interference are drawn where they happen.
- **Officials** throw the flags.
- **Name tags:** style C, in team colors.

**Sprites.** PixelLab drew them; 7 generations were used and the trial is spent.
- **Player poses:** 11 in `assets/sprites/frames/situational.txt`.
- **The official:** 8 frames in `assets/sprites/officials/`, made by `scripts/sprites/pixellab/officials.py`.

**Data.**
- `scripts/live/positions.py` gains `units()`, `team_colors()` and `GameUnits`.
- `tests/fixtures/live/team-units.example.json` holds every team's center, long snapper, quarterback and colors.
- Five real plays were added to the fixtures.

## Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 1,085 passed |
| Ruff, format, mypy, `pnpm check:contracts`, `pnpm check:client`, `make check` | Passed |
| `uv run python scripts/live/check_play_scripts.py`, and with `--no-positions` | 0 broken rules over all 14 captured games, with the new realism rules |
| `uv run --with pillow --with numpy --with pyarrow python scripts/sprites/audit_render.py` | 2,254 scripts, 0 problems |
| `render_script.py --types`, then the full game in batches of 30 | 19 comparison clips, and every CHI at SEA clip |

## Decisions, issues and limitations

- **Decisions:** OWN-037, OWN-038 and ENG-038.
- **Changed earlier decisions:**
  - Passes replace OWN-033's short receiver who settles and comes back.
  - The snapper, the run quarterback and the intended receiver amend OWN-032.
- **The untipped interception** can't be compared with video. It's an Atlanta game with no measured uniforms, so tests check it.
- **Fouls on players ESPN doesn't identify:** a foul whose player ESPN doesn't identify shows only the flag.
- **Officials are generic:** one look, a referee's white cap for all.
- **Tags not yet seen at full size:** the owner chose style C from a small preview; the renders show it at full size.
- **PixelLab credits:** the trial plan is spent. The bonus refills by 5 a day.

## Resume here

1. **The owner's second look** at the 19 clips against the video: fix what they find, then commit when asked.
2. **Next slice:** slice 5, the jumbotron, or slice 6, Gridiron delivery, of the [plan](../../superpowers/plans/2026-11-03-live-play-automation.md).
