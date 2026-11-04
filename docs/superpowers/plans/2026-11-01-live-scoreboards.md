# Live scoreboards — 2026-11-01

Owner direction (OWN-019): "Begin on the scoreboards now." Requirements: LV-001, with LV-002's roster filters kept. Fantasy attribution waits for M3.

## Interfaces

- **Scoreboard read:** `normalize_game` keeps ESPN's `situation`, team colors, records, score by quarter, venue, weather, broadcast and leaders in `nfl_game.payload`. A shape change in any of these loses only that extra, never the score.
- **Summary read:** `normalize_summary_detail` keeps drives, win probability and team stats. They are stored with the raw boxscore in the `boxscore` column, and a change emits `game.summary`.
- **API:** `GET /api/v1/live/games` gains live state on each row. `GET /api/v1/live/games/{id}` adds leaders, drives, win probability and team stats.
- **Client:** `apps/web/src/GameBoard.tsx`, with tiles and the game page in `Live.tsx`.

## Decisions

- **No migration (ENG-024).** A migration planned for game night could stop live scoring if the worker restarted before it ran, because the worker reads every column. A later migration can give the summary its own column.
- **Field scale, measured.** ESPN's `yardLine` runs from the home team's goal line: 845 of 845 live samples agree. The server derives the line to gain from it, so the client does no football arithmetic.
- **Real-data corrections.** ESPN sends down and yard-line sentinels, keeps a finished drive listed as current, lists empty drives with no plays, and leaves its red-zone flag set during timeouts. None of these reach the screen.

## Evidence

- All captured scoreboards and summaries parsed with no failures (459 and 362 at the last full run).
- 587 backend tests, 20 client tests and 10 browser scenarios, including accessibility on the game page, no overflow at 320 px and a server change reaching an open page without a reload.
- Viewed with real captured games on an isolated port in dark, light and phone layouts, then checked during PHI at WSH on a copy of the real database ([receipt](../../research/live-slate-receipt-2026-11-01.md)).

## Not done

Running since 2026-11-01 21:25 (UTC−7). Signed-in pages on the running app were checked with the dev account on 2026-11-03 (ENG-031): the Live board and a game page load; R-039 covers the one flaw found. Player box scores, scoring-play and injury panels, and fantasy points are not built.
