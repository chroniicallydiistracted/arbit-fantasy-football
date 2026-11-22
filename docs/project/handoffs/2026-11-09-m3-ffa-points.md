# Handoff — 2026-11-09 — M3 begins: FFA points from nflverse statistics

## Current state

After the 2026-11-09 audit, the owner started the next phase of development (OWN-060). The Model is the critical path: every advice feature (Lineup, Waivers, Trades, Front Office decision cards) consumes its player evaluations. The [M3 plan](../../superpowers/plans/2026-11-09-m3-model.md) orders seven slices. The weekly horizon comes first, then rest-of-season value for trades (deadline 2026-12-02 10:00 UTC−7). The draft horizon comes last.

**Slice 1 is implemented and verified, not released.** The work is on branch `claude/m3-model`, worktree `/home/andre/arbit-m3-model`, uncommitted, because the owner commits on request. Nothing on the running app changed: no service was restarted, no migration was added, and the running database was only read. No projection exists yet.

## Completed work

- **Stat line boundary** (`libs/arbit-data/src/arbit_data/nflverse/stat_lines.py`, `nflverse-ffa-stat-lines-v1`):
  - `athlete_line(row, events, metrics)` and `defense_line(team, own, opponent, opponent_score, events, metrics)` return a `StatLine` for `arbit_core.scoring.score`, with per-metric provenance.
  - Unknown metrics carry a coded reason: `COLUMN_ABSENT`, `VALUE_NULL`, `VALUE_INVALID`, `UNATTRIBUTED_TEAM_EVENT` or `UNVERIFIED_SCORING_EVENT`.
  - `game_events(plays)` reads the play-by-play columns in `PLAY_COLUMNS`. `classify(play)` gives ESPN's touchdown category, D/ST credit and points-allowed treatment.
  - `offense_recoveries(play)` pairs each fumble with its recovery.
- **Definitions** were settled against ESPN's raw statistics and are tabulated with their evidence in the [research note](../../research/nflverse-ffa-scoring-2026-11-09.md). Single-play definitions are labeled as such.
- **Verification tool** (`scripts/model/verify_nflverse_scoring.py`): reads ESPN's per-week player pool for QB, RB, WR, TE, K and D/ST across 2025 and 2026 (seven cookie-free GETs), or replays a saved read. It joins players by stored GSIS alias and games by ESPN event ID, and compares every category and the FFA total under the stored rules. It also checks the reverse direction.
- **Tests** (`libs/arbit-data/tests/test_nflverse_stat_lines.py`, 14): column mapping and exact totals; field goal bands with blocked misses; missing and null values refused; kick-type return TDs; kicking-team TDs on kicks; the offense recovering the defense's fumble; a teammate's fumble recovered for a TD; fumble recoveries paired per slot; points and yards allowed; D/ST categories and the zero offensive line; unattributed two-point returns.
- **Records:** OWN-060, ENG-051, R-060 to R-062, SRC-25, MD-001 to `in_progress`, DATA-007 evidence, status, changelog, roadmap note, AGENTS.md.

## Verification

All commands ran in `/home/andre/arbit-m3-model` on 2026-11-09.

| Command | Result |
| --- | --- |
| `uv run pytest -q libs/arbit-data/tests/test_nflverse_stat_lines.py` | 14 passed |
| Three deliberate definition breaks (blocked misses, defensive-TD exclusion, kick-play rule), one at a time | Each failed at least one test (1, 1 and 3 failures); file restored, 14 passed |
| `ARBIT_NFLVERSE_PATH=/home/andre/arbit-fantasy-football/data/nflverse uv run --env-file /home/andre/arbit-fantasy-football/.env.local python scripts/model/verify_nflverse_scoring.py --capture /home/andre/arbit-fantasy-football/data/model/espn-verification-2026-11-09 ...` | Seven ESPN GETs, 1,061 players; saved privately (14.8 MB) |
| Same with `--replay ... --output docs/research/nflverse-ffa-scoring-2026-11-09.json` | 2025: 7,202 compared, 7,171 exact, 8 differ, 23 refused. 2026: 3,569 compared, 3,549 exact, 3 differ (decided weeks), 3 differ (week 9), 14 refused. Reverse check: 0. Report hash `f503d6ff…` |
| `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | All passed; 108 source files clean |
| `uv run mypy --strict scripts/model/verify_nflverse_scoring.py` | Clean |
| `uv run pytest -q` (full suite, real PostgreSQL test schemas) | 1,290 passed, exit 0 |
| `python3 scripts/validate_foundation.py` | PASS: 45 JSON artifacts, 143 Markdown documents, 60 traceable requirements |
| `node scripts/validate-contracts.mjs` (with the main checkout's `node_modules` linked in after pytest, then removed) | PASS, exit 0 |

The client checks (`make web-check`) and the browser suite weren't run, because no client, API or contract file changed.

Exploration scripts lived in the session scratchpad and are not kept. Everything they established is either encoded in the adapter and its tests or reproduced by the verification tool.

## Decisions, issues and limitations

- **R-060:** 11 decided source-side differences that the adapter keeps. The largest effect is 2 FFA points in one line. ESPN stays the authority for official points.
- **R-061:** 37 lines (2025 and 2026) are unknown because play-by-play doesn't name who scored a defensive two-point return. Slice 2 can rule players out with snap counts.
- **R-062:** Chris Manhertz and Greg Desrosiers Jr. have no GSIS alias.
- The comparison covers ESPN's current player pool. Players who have left it since 2025 weren't compared, and seasons before 2025 rely on column-definition consistency (no nulls 2001–2026 in the columns read), not on ESPN comparison.
- Week 9 of 2026 was still settling, and the Sunday-night game was missing from nflverse at its 03:56 UTC import. Neither is a defect.
- Correction to the audit summary: nflverse is not import-only. The worker's statistics lane imports changed files daily, and 2026 data was current through week 9 at 03:56 UTC.

## Resume here

1. **Slice 2** in the [M3 plan](../../superpowers/plans/2026-11-09-m3-model.md), starting with "Slice 2 inputs carried forward":
   - Write the retrospective availability ADR (Q-005) before any backtest.
   - Define point-in-time features with cutoffs and a coverage inventory.
   - Build historical FFA targets from 2012 onward with this adapter. Snap counts start in 2012; confirm the range in the coverage inventory.
   - Separate "played, no statistic" from "did not play".
2. Keep using the worktree. The running worker loads `main`, so merge only on the owner's request, the way ENG-050 was released.
3. Owner decision pending, not blocking: after slice 5, should M4 Lineup come before the full Scout? (Plan, "Why this order".)
