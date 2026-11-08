# Handoff — 2026-11-07 — The stadium around the live field

## Current state

The owner asked for the field's black surround to look like a normal NFL game in a stadium (OWN-049). The stadium is implemented, verified and **published** to all 15 Week 9 games on the running app, on the owner's approval: "Push it live" (ENG-045, [plan](../../superpowers/plans/2026-11-07-live-stadium.md)).

## Completed work

- **`scripts/sprites/stadium.py`** traces each pixel of the fixed full-field camera against a bowl built around the field in yards. From the field out:
  - sideline turf in the field art's own border color, with the far team benches
  - a padded wall
  - a lower bowl of seats, aisles and tunnels
  - a lit club level
  - an upper deck and its rim

  The near stands aren't drawn because the camera sits in them.
- **The crowd and building** use the home team's nflverse colors. At a neutral site in nflverse's schedule, such as CIN at ATL in Madrid, the crowd is even and the building is gray. The stands are dimmed so the field stays brightest.
- **No real venue:** there are no logos, wordmarks or likeness of a real stadium. The game's ID seeds the stadium, so rebuilds match.
- **`live_art.py`** writes the stadium and the warped field into the same `field.png`. The running client paints it unchanged.
  - `Camera.warp` in `preview.py` gives the stadium the field's exact warp for its mask.
  - `neutral_sites()` was added to the Live context.
  - Pillow joined the dev dependency group (`pillow>=13,<14`) so the tests build real images.
- **External state:** the 15 Week 9 art pointers changed (see [Publishing](#publishing)). Nothing else in the running app changed.
  - The dev account session was renewed with `make dev-account` (read-only, until 01:02 Arizona time on November 8).
  - Review images are private in `data/sprites/review/stadium-2026-11-07/`:
    - `in-app-jax-at-bal.png`
    - `in-app-phone.png`
    - `jax-at-bal-full-size.png`
    - `week-9-all-games.png`

## Verification

- **Stadium tests.** `uv run pytest -q tests/contracts/test_stadium.py`: 6 passed.
  - Restoring the old black surround failed the empty-space, seam and determinism tests.
  - Ignoring the neutral site failed both neutral tests.
  - Skipping the field paste failed the field test.
- **Repository gates.**
  - `uv run pytest -q -p no:cacheprovider`: 1,214 passed in 48.7 s.
  - `uv run ruff check .`: passed.
  - `uv run ruff format --check .`: 183 files formatted.
  - `uv run mypy`: no issues in 99 files.
  - `python3 scripts/validate_foundation.py`: passed.
- **Staged slate.** I rebuilt all 15 Week 9 bundles into a scratch root, from the November 6 receipt with the November 7 Denver–Carolina entry (`live_art.py ... --output-root`). Each live pointer matched its receipt beforehand. Against the live bundles:
  - The sprites, officials, ball and `meta.json` were byte-identical in every game.
  - Every interior field pixel was unchanged, and no old fill color remained.
  - The field images grew from 4,247 kB to 7,949 kB in all, 319–579 kB each.
- **Signed-in app.** A Playwright script on the running app (port 8000, dev account) served the staged JAX at BAL art in place of the live art requests. It captured the board, players, posts and caption over the stadium at 1280 and 390 px with no page errors. The running app itself was not changed.
- **Not run.** The web checks and browser suite: no client code changed. The review renderer's GIFs keep the dark surround.

## Publishing

The owner approved publishing ("Push it live").
- **Before publishing (13:20 Arizona time, Saturday).** No game was active; the first kickoff is Madrid at 07:30 on Sunday. The API reads each pointer on every request, so no restart was needed.
- **Prior pointers.** All 15 were recorded first in `data/gridiron/2026/stadium-2026-11-07/before-pointers.json`.
- **Publishing.** Each verified staged bundle was copied in as its own revision folder. Its content hash was recomputed against its name, then `current.txt` was replaced atomically. The new pointers are in `after-pointers.json` beside it.
- **Verified on the running app (port 8000).**
  - Signed in as the dev account, 180 responses covered every file of every game, with and without `?revision=`. All matched the published files byte for byte.
  - Each game's animation response named the new art revision.
  - Anonymous art requests returned 401.
  - Screenshots of JAX at BAL and the Madrid game, without any override, showed the stadium.
- **Rollback.** Write each revision from `before-pointers.json` back to `data/live-art/<event>/current.txt`. The old revision folders are untouched.

## Decisions, issues and limitations

- **OWN-049 and ENG-045.** The generic home-colored bowl is my interpretation of "a normal NFL game/stadium"; the owner hasn't seen it yet.
- **R-043 (art built by hand).** It still applies, and any rebuild now includes the stadium.
- **Download size.** About 250 kB more per game's art. A separate stadium image plus a transparent field would save about 40%, but only after a web release that draws both.

## Resume here

1. **Owner feedback.** Watch for comments on Sunday's games. Changes to the look go in `stadium.py` (colors, crowd mix, how dark the stands are); rerun the tests and rebuild the slate.
2. **Later weeks.** Building a game's art with `live_art.py` includes the stadium automatically. R-043 (automating art per game) is unchanged.

[Status](../status.md) · [Roadmap](../roadmap.md)
