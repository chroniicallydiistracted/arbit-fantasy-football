# Handoff — 2026-11-03 — Real uniforms on the sprites

## Current state

Branch `claude/platform-reset`, local commits only: no push, merge or deployment. Live (M6) is in progress. The owner said not to infer uniform colors and added their full 2026 Gridiron uniform set to ignored `data/Gridiron_2026_Uniforms` (OWN-028). Sprite frames can now be painted in any real uniform measured from that set. Nothing here is in the app yet. The running `arbit-api` and `arbit-worker` were not touched.

## Completed work

- **Region maps** (`assets/sprites/regions/*.txt`, made by `scripts/sprites/pixellab/regions.py`). They say which uniform part each pixel of all 59 frames shows, from the skeleton each frame was drawn from.
- **Measuring and painting** (`scripts/sprites/uniforms.py`). It measures helmet, stripe, facemask, jersey, numbers, pants, pants stripe, socks by height and cleats at fixed places on the 400×500 template. Large sheets are scaled to it. Sheets that show two versions are refused unless one is named. The owner's sheet's own shading ratios are applied. The painting and shading code needs only the standard library, so the repo's tests can import it.
- **Renderer** (`scripts/sprites/preview.py`). An actor can carry a measured uniform. GIFs keep every sprite color exactly; the old 128-color encoder had turned Chicago's orange stripe into the first-down yellow. The public preview plays (`assets/sprites/preview`) were rebuilt on the plain field.
- **Real plays** (`scripts/sprites/real_plays.py`). They now use what Gridiron's week 8 page lists for CHI at SEA, rechecked 2026-11-03: Chicago `B2`, Seattle `E`, field `SEA_2023-2026^3`. The white stand-in palette is gone. Seven GIFs were re-rendered to ignored `data/sprites/review/real-plays/`.
- **Private receipt.** `data/gridiron/2026/week-08/manifest.json` now records the recheck for this game.
- **Records.** OWN-028, ENG-027, R-037, the changelog, [research](../../research/uniform-measurement-2026-11-03.md), the sprite and pipeline READMEs, and a note in the Gridiron research.

## Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | **609 passed**. New: `tests/contracts/test_sprite_uniforms.py` (shading reproduces all 64 of the owner's sets for 4 families; measuring a synthetic template sheet; sock stripes; painting) and 3 region-map tests in `test_sprite_frames.py` |
| `uv run ruff check .`, `uv run ruff format --check .` | Passed |
| `uv run --no-project --with ruff ruff check --line-length 120 scripts/sprites/uniforms.py scripts/sprites/pixellab/regions.py scripts/sprites/preview.py scripts/sprites/real_plays.py` | Passed (these scripts are outside the repo's ruff scope) |
| `uv run mypy` | Passed, 85 files |
| `make check`, `pnpm check:contracts` | Passed |
| `uv run --no-project --with pillow --with numpy python scripts/sprites/real_plays.py` | 7 GIFs, 0.5–10.2 MB. Chicago's measured orange and whites confirmed present in the encoded frames, and merged frames keep each play's length (sack 5.6 s, pass 6.8 s, touchdown 8.0 s) |
| `uv run --no-project --with pillow --with numpy python scripts/sprites/preview.py` | 5 public plays and the frame sheet rebuilt |

Checked by eye: all 59 region maps; all 202 single-version sheets beside their painted stand and run frames; stills and zooms from four of the seven plays. RED check: changing the white blend from 0.31 to 0.25 fails the shading test.

**Not verified:** the owner hasn't seen the re-rendered plays. The three two-version sheets weren't painted, because no version is named. Shading of black uniforms against the black outline follows the owner's own black jerseys, but nobody has judged it on the field.

## Decisions, issues and limitations

OWN-028 and ENG-027 are new; limits are in R-037. In short: one trim color per part (jersey trim is the number color), no helmet logos or thin piping, socks about six pixels tall, and placeholder skin tones. Which uniform a game used is a manual read of the week page until a sync lane records it (M6). Gridiron art and anything measured or painted from it stays in ignored `data/` (OWN-015). The sign-in fix R-036 still waits on an owner-approved upgrade.

## Resume here

1. The owner reviews `data/sprites/review/real-plays/*.gif`.
2. For M6, the Gridiron sync lane records each game's listed uniforms and field with status (listed, TBA, two versions), rechecks until settled, and feeds `uniforms.measure_file`. Then the in-app renderer reads `assets/sprites/regions` and `anchors.json`. See [status](../status.md) and the [roadmap](../roadmap.md).
3. After any frame change, rerun `regions.py` from `data/sprites/pixellab-test` and the sprite contract tests.
