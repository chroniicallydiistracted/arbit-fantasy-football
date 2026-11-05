# Handoff — 2026-11-05 — The stadium board (automation slice 5)

## Current state

Branch `claude/platform-reset`, local only and not pushed.

- **Committed.** Slice 3 and the OWN-035 to OWN-038 work were committed on 2026-11-05 (`1b5fee7`, `c7ed1df`, `9f3e8ec`). Slice 5 was accepted by the owner ("The scoreboard looks phenomenal!", OWN-040) and committed at their request the same day. Nothing is pushed.
- **The running app is unchanged.** Boards reach it with the browser renderer in slice 7.
- **Owner review (OWN-039).** The owner reviewed the first board ("It looks really good!") and asked for four changes, now built (ENG-040):
  - scrolling results
  - green, red and yellow by kind
  - penalty cards with the team and the player's number
  - team logos in LED dots
- **Review clips.** The board is in `data/sprites/review/board/` (the 19 comparison plays) and in the whole CHI at SEA game in `data/sprites/review/generated/`.
- **The task record** is the [jumbotron task](../../superpowers/plans/2026-11-05-jumbotron.md). It holds the plan, the interpretations and the evidence.

## Completed work

**The board's facts:** `libs/arbit-data/src/arbit_data/live/board.py` (ENG-039).
- **API:** `GameBoard(teams, home_code, away_code, names).boards(play, facts)` gives each play's `PlayBoard`, then its try's. Feed it every stored play in ESPN's order.
- **States:** the game at the snap and after the play: quarter and clock, both teams' code, score and timeouts left, possession, down and distance (or kickoff or the try), goal to go, and the ball's spot.
- **Results:** in large type, from `RESULT_TEXT`.
- **Contract:** `packages/contracts/schemas/play-board.schema.json`, with `tests/fixtures/live/play-board.example.json`.

**The script:** `PlayScript.whistle`, the play's last movement or a player going down.

**Drawing:**
- `assets/sprites/board/glyphs.txt`: our own squared glyphs.
- `scripts/sprites/board.py`: the LED board, its layout and the result cards' wipe.
- `preview.render(..., backdrop=)`: draws the board behind the field and keeps it in the crop.
- `render_script.py`: builds boards with the scripts. Its `--board` mode renders the 19 comparison plays.

**Checks:**
- `scripts/live/check_boards.py` compares the boards with ESPN's own scoreboard reads.
- `audit_render.py` checks every board's glyphs and widths.
- `scripts/live/export_board_fixtures.py` writes `tests/fixtures/live/board-plays.example.json`: three whole real games.

**Design system:** the Live graphics section describes the board.

**After the owner's review (ENG-040):**
- **Tones and flags:** `BoardResult.tone`, and `penalty` results with `jersey` and `detail`.
- **Rosters:** `GameBoard` takes each team's week roster (`scripts/live/positions.py` `week_rosters`) and `boards(..., clock_end=)`.
- **Logos:** `scripts/sprites/fetch_logos.py` stores all 32 teams' logos in the ignored `data/logos/espn/`. `board.logo()` draws each as LED dots.
- **Drawing:** cards scroll in from their team's side, the clock runs when an end time is known, and the "#" glyph is new.

## Verification

| Command | Result |
| --- | --- |
| `uv run python scripts/live/check_boards.py` | 0 problems. Penalty cards: 214 numbered, 11 team fouls, 1 player not on his team's roster that week. Board equals ESPN's scoreboard: final score 14 of 14; score and timeouts after 691 plays; down and distance after 641; possession after 602. 23 reads where ESPN's play record disagrees with its own scoreboard are listed apart |
| `uv run pytest -q` | 1,155 passed, including 36 board tests and 34 whistle checks |
| `uv run --with pillow --with numpy --with pyarrow python scripts/sprites/audit_render.py` | 2,254 scripts, 2,676 boards, 0 problems |
| `uv run python scripts/live/check_play_scripts.py` | 0 broken rules |
| Ruff, format, mypy, `pnpm check:contracts` (5 examples), `pnpm check:client`, `make check` | Passed |
| `render_script.py --board`, then the whole game in six batches | The 19 board clips and the game's clips |

**Checked by eye:**
- **The field goal:** the snap, the "FIELD GOAL GOOD" wipe, then 10–3.
- **The first touchdown:** 2nd & goal at the SEA 1, "TOUCHDOWN" for CHI, then 6–0 with "EXTRA POINT".
- **Its try:** "EXTRA POINT GOOD", then 7–0.
- **The interception:** after it, CHI's ball, 1st & goal at the SEA 6.

## Decisions, issues and limitations

- **Decision:** ENG-039. It records three interpretations of the plan:
  - Missed and blocked kicks get a result card.
  - Team codes use the name tag colors rather than measured uniforms.
  - The clock holds at the snap.
- **Timeouts** depend on ESPN's numbering in its text. It numbered all 108 timeouts and 4 lost challenges captured. A challenger it can't name, or a name both teams share, leaves both teams' timeouts unknown until the half ends.
- **The board's after state** follows ESPN's record of the play. When ESPN re-spots the ball afterwards (17 reads), its scoreboard shows the new spot, and the next play's board shows it at the snap.
- **The live app (slice 7) will need:**
  - each team's location and full name from `nfl_team`, for challenges
  - the week's rosters from the stored nflverse data, for numbers
  - the logos behind a session-checked route, like the Gridiron art
- **The clock** runs only when a source gives the end of the play. The owner is building an NFL API route that will; until then it holds at the snap.
- **Safeties** are colored green, as scores.

## Resume here

1. **The owner's NFL feed (OWN-040).** When their NFL API script is ready, pass each play's end clock to `GameBoard.boards(..., clock_end=)` and the board runs the clock. They want the feed pushed to Arbit as data arrives instead of polled; plan that with them as real-time work.
2. **Next slice:** slice 6, the Gridiron listing lane and private delivery. It adds migration `0008` and changes the running app, so it needs the owner's approval outside game windows. See the [plan](../../superpowers/plans/2026-11-03-live-play-automation.md).
