# Handoff — 2026-11-08 — Each home stadium's own design

## Current state

The owner supplied midfield references for every NFL stadium in `data/nfl_stadium_mockups/`. They want the generic surround replaced by each home stadium's design (OWN-050), recreated as Arbit's own art rather than the references themselves (OWN-059). This is implemented (ENG-047) and awaits the owner's review.
- **Not published.** It is game day, and publishing changes the running app's art, which needs the owner's approval outside game windows.
- **Codex** is refactoring the choreographer and renderer at the same time; its plan includes `live_art.py` atlas tooling. This work changes `live_art.py` by one venue lookup, and otherwise only `stadium.py` and the new `venues.py`.

## Completed work

- **`scripts/sprites/venues.py`** measures each domestic reference frame.
  - The far stands and both end-zone corners become stacks of bands from the field's edge up: seats, concrete, suites, LED ribbon, open.
  - Each band has its apparent height in yards at the field's edge and a color taken from its lit pixels.
  - Thick slabs beside an end zone take the far design. Indoor venues are flagged.
  - The spec is written to private `data/stadiums/venues.json`.
  - It maps nflverse stadium IDs to venues, with MetLife and SoFi by home team. Houston's ID covers NRG, which nflverse still names Reliant.
- **`scripts/sprites/stadium.py`:** `layer(..., venue=)` and `surround(..., venue=)`.
  - Each spot in the stands takes its venue band at the same apparent height on its side.
  - The stack above the wall is compressed into what the fixed camera sees.
  - Seats carry a thinner crowd. Suites are dark glass with some lit panes, ribbons stay lit, and indoor open space becomes roof with light rigs.
  - Without a venue, the generic bowl is unchanged.
- **The Live context:** `venues()` gives each game's stadium ID, home team and neutral flag from nflverse's schedule. `scripts/live/positions.py` re-exports it.
- **`scripts/sprites/live_art.py`** looks up the venue for the event, with neutral sites kept generic, and passes it to `surround`.
- **Review** in private `data/stadiums/review/`:
  - `sheet-1.png` … `sheet-8.png` show each of the 32 configurations, reference above ours, on a plain field. `sheet.py` rebuilds them.
  - `in-app-mt-bank.png` is Jacksonville–Baltimore in M&T Bank's design.

## Verification

- **Stadium tests.** `uv run pytest -q tests/contracts/test_stadium.py`: 10 passed. The 4 new tests use a synthetic venue spec:
  - shared buildings choose the home team's configuration
  - the venue's seats show while the field stays exact
  - a roof covers open space indoors
  - thick end slabs take the far design

  Removing venue shading failed two tests; removing the roof failed one.
- **Repository gates.**
  - `uv run pytest -q -p no:cacheprovider`: 1,230 passed.
  - `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy` passed.
- **Commands.**
  - `uv run --offline python scripts/sprites/venues.py` measured 34 entries: 30 venues, the Jets and Chargers configurations, and the two shared buildings' plain names.
  - `uv run --offline python data/stadiums/review/sheet.py` rendered all 32 configurations.
- **Signed-in app.** The staged Jacksonville–Baltimore build, `live_art.py 401873037 ... --output-root <scratch>`, rendered in the signed-in app through Playwright with the art requests served from the stage. There were no page errors, and the running app was not changed.

## Decisions, issues and limitations

- **A recreation, not a copy.** The fixed camera sees about 22 apparent yards of the far stands, so the design above the wall is compressed to fit. Colors come from the references' lit pixels, then are dimmed for a night game. It is a stylized recreation, not a likeness at every row.
- **Rough spots in the review.** A few end-zone corners take open sky and city lights where the reference shows a structure.
- **Not yet covered:**
  - roof and canopy shapes above the camera's view
  - scoreboards and video boards
  - the international references, which stay generic per OWN-050
- **R-043** (art built by hand) still applies. A week's bundles must be rebuilt to pick up the designs.

## Rework after the owner's review: real 3D models, M&T Bank first

The owner found the recolored bowls generic and rectangular, and asked to focus on one stadium until it reliably looks like the real one. M&T Bank Stadium is now a 3D model (ENG-048):
- **Plan.** It comes from its seating map, with every section scaled to the field wall measured in the reference.
- **Heights.** The calibrated reference camera gives each tier's height and rake.
- **Parts.** It has the suites, light banks, press box and end boards.
- **Rendering.** `venue3d.py` renders it.

The private study is in `data/stadiums/mt-bank/`:
- `refcam.py`: the camera fit
- `study.py`: structure placement
- `model.py`: the model
- `render_ref.py`: the reference comparison
- `render_live.py`: the live camera, day and night

Review images are in `data/stadiums/review/mt-bank/`. The model isn't in the art build yet.
- **Framing.** The live camera's frame starts at row 183. M&T's upper deck reaches row −56 and its light banks row −161, so the whole stadium needs a frame about 340 rows taller, with the field unchanged. That's the owner's call.
- **Not yet matched:** sunlight and shadow, the full white portal bunkers, the corner light towers, and the end boards' real form.

### Second M&T Bank review

The owner noted:
- a wrong shape along the field wall
- seating where none exists, beside the end zones
- an upper deck that was uneven and not straight
- unevenly placed suite frames

Changes:
- **Plan mapping.** The plan is now mapped piecewise per side, as the map's own offsets from the field differ by side. The reference walls, re-traced clear of the goalposts, are 12.7 yards behind the far sideline, 7.5 behind the left end line and 14 behind the right. The stands keep the far side's 0.84 depth scale.
- **The wall.** It is now the lower bowl's own front faces, following its true curve around the ends. The rounded-rectangle ring is gone, and the turf lies under everything in tiles.
- **Club and upper deck.** Every section shares the tier's front and back heights, so the edges run straight and level.
- **Suites.** Each suite has evenly spaced mullions across its own width and is lit or dark as one room.
- **End light banks.** Light banks were added on the end upper decks.

The near-side corner sections beside the end zones are in the seating map. The owner is asked whether those are the ones that don't exist.

## Resume here

The owner reaffirmed M&T Bank first, then expansion. Continue from the [M&T Bank refinement handoff](2026-11-08-mt-bank-refinement.md), which records the latest model, repeatable review images, actual validation and remaining likeness/framing gates. The earlier recolored venue sheets are historical evidence, not the current acceptance target.

[Status](../status.md) · [Roadmap](../roadmap.md)
