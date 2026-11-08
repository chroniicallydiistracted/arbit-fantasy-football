# Task: The stadium around the live field

Status: verified and published to all 15 Week 9 games on 2026-11-07 at 13:20 Arizona time, on the owner's approval ("Push it live"; OWN-049, ENG-045).

- **Requirement IDs.**
  - LV-003: canonical play graphics.
- **Specifications and decisions.**
  - OWN-049: "Instead of just showing a field in a black void, I'd like the background to look as it would in a normal NFL game/stadium."
  - OWN-030: the fixed full-field view is the standard.
  - OWN-028 and OWN-048: fields and kits come from the owner's Gridiron art, never inferred stand-ins.
  - OWN-032: only players in the play. The stadium adds no figures on the sidelines.
  - The [design system](../../design/design-system.md) and ADR-005: the play is the signal. Nothing around it should compete with it.
- **Baseline.**
  - `scripts/sprites/live_art.py` warps the field art for the fixed camera into `field.png`, filling everything outside the field with near-black `(14, 18, 16)`.
  - The browser paints `field.png` as the opaque base of every frame, then the board, the play and the caption bar (`apps/web/src/live/LiveField.tsx`).
  - The drawn band shows the far sideline and the corners behind both end zones. No sky can show in it.
- **Scope.**
  - A stadium layer built once per game behind the field, in the same file, so the running client needs no change.
  - The building and crowd use the home team's nflverse colors. At a neutral site the crowd is even and the building is gray.
  - Out of scope:
    - real venue likeness, logos or wordmarks
    - roofs and sky, which the band never shows
    - crowd animation
    - the review renderer's GIFs, which keep the dark surround
- **Files and interfaces.**
  - `scripts/sprites/stadium.py`, new:
    - `layer(camera, band, colors, seed)`
    - `surround(camera, field, band, colors, seed)`
    - `field_mask`, `turf_color` and `Colors`
  - `scripts/sprites/preview.py`: `Camera.warp(image, fill)`, shared by `ground()` and the stadium's field mask.
  - `scripts/sprites/live_art.py`: `frame_band(camera)` and `team_rgb`. `build` writes the stadium into `field.png`.
  - `libs/arbit-data/src/arbit_data/live/context.py`: `neutral_sites()` from nflverse's schedule `location`. Re-exported by `scripts/live/positions.py`.
  - `tests/contracts/test_stadium.py`.
  - `pyproject.toml` and `uv.lock`: Pillow in the dev group, so the tests can build real images.
- **Acceptance.**
  - Nothing around the field is left as the old fill or empty sky.
  - The field art's pixels are unchanged, and the sideline turf meets the field without a seam.
  - A game always gets the same stadium.
  - Home fans dominate. A neutral site splits the crowd and carries no team colors on its walls.
  - A rebuild of every Week 9 bundle changes nothing but the surround.
- **Migration, rollback and data impact.**
  - No migration or API change.
  - Publishing replaces each game's private art pointer (`data/live-art/<event>/current.txt`). Rollback writes the previous revision back. Every prior revision stays on disk.
  - Field images grow by about 250 kB each.

## Evidence and outcome

See the [handoff](../../project/handoffs/2026-11-07-live-stadium.md).
