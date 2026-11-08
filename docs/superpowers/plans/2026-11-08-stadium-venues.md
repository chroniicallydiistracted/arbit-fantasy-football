# Task: Each home stadium's own design

Status: implemented, 2026-11-08 (OWN-050, OWN-059, ENG-047). The owner reviews the designs before they are published to a week's bundles.

- **Requirement IDs.**
  - LV-003: canonical play graphics.
- **Specifications and decisions.**
  - **OWN-050:** each team's actual stadium, with international games kept generic.
  - **OWN-059:** recreate each stadium as Arbit's own art from the owner's references, not the references themselves.
  - **OWN-049 and ENG-045:** the generic surround this extends.
  - **OWN-022:** the pixel character.
- **Baseline.** `stadium.py` draws a generic traced bowl in the home team's colors behind the field. `live_art.py` bakes it into each game's private `field.png`.
- **Scope.**
  - **In:**
    - a measured design per domestic venue: band stacks for the far stands and both ends, plus an indoor flag
    - venue shading in the traced bowl
    - venue choice by nflverse stadium ID and home team
    - review sheets
  - **Out:**
    - roofs and canopies above the camera's view
    - video boards
    - international venues
    - any use of the references' pixels
- **Files.**
  - `scripts/sprites/venues.py`, which is new and writes private `data/stadiums/venues.json`
  - `scripts/sprites/stadium.py`
  - `scripts/sprites/live_art.py`: the venue lookup only
  - `libs/arbit-data/src/arbit_data/live/context.py`: `venues()`
  - `scripts/live/positions.py`
  - `tests/contracts/test_stadium.py`
- **Acceptance.**
  - Synthetic-spec tests:
    - shared buildings choose the home configuration
    - venue seats show and the field is exact
    - a roof indoors
    - end slab cleanup
  - All 32 configurations rendered against their references for the owner's judgment.
- **Migration, rollback and data impact.**
  - No migration or API change. Publishing rebuilds a week's art bundles and switches their pointers; rollback restores the prior pointers.

## Evidence and outcome

See the [handoff](../../project/handoffs/2026-11-08-stadium-venues.md).
