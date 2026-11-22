# Handoff — 2026-11-10 — NFL availability for the Model, twice a day (OWN-063)

## Update 2: wake the PC for game windows (OWN-065)

The owner said: "My PC cannot stay on 24/7. Do not remove the sleep option. 3 is the only one that would work."
- **Built and installed:** `infra/windows/arbit-wake.ps1` ([how it works](../../engineering/windows-wake.md)).
  - **On Windows now:** `\Arbit\Plan wake windows` (daily at 9:00 and at logon) and 20 `\Arbit\Wake …` tasks through 18 November, with the installed copy in `%LOCALAPPDATA%\Arbit`.
  - **Windows:** game windows run 120 minutes before each kickoff to 30 minutes after; the injury-report windows sit around 12:00 and 19:15 Eastern. In Phoenix time, a weekday is 9:55–10:20 AM and 5:10–5:35 PM, and Sunday 15 November has 5:30–8:00 AM, 9:00–11:30 AM, 12:05–2:55 PM and 4:20–6:50 PM.
  - **After a window:** the PC sleeps again only if the task woke it and nobody used it. Sleep stays in the Start menu, and power settings are unchanged; wake timers were already allowed on AC.
- **Verification:**
  - `-Preview` matched ESPN's schedule.
  - The planner's tests passed: 3, through the real script.
  - A 5-second `-Hold` with a start three days back ran, logged `woken by this task: False`, and correctly stayed awake.
  - `-Install` registered 21 tasks, all with `WakeToRun`, run headless.
  - Full gates: ruff, format and mypy passed; `uv run pytest` 1,330 passed.
  - Not yet seen: a real timer wake. `powercfg /waketimers` needs administrator rights.
- **To remove:** `powershell -File infra\windows\arbit-wake.ps1 -Uninstall`.

## Update: the owner chose ESPN status (OWN-064)

The owner said: "Yes, use ESPN status and fix the read gaps."
- **Inactives:** ESPN's fantasy injury status is the Model's game-day availability input. `arbit_data.availability.espn_status.status_as_of(uow, season, at)` reads the latest stored league document published by `at`, and the latest ESPN read finished by `at`.
  - The result is current only within 15 minutes of a read; otherwise game-day availability is unknown.
  - Real data: current at the 8 November 1 PM kickoff (read 1 minute before, 63 players Out). Stale at the London kickoff (last read 09:20) and at 1 November's 1 PM games (last read 12:17).
- **Next Gen Stats:** the reader was removed (Q-015 resolved). The `availability` lane now reads only NFL's injury report, twice a day.
- **Read gaps (R-066):** Windows' own records show the PC put to sleep from the Start menu (`StartMenuExperienceHost.exe`) every night from 31 October to 9 November, while idle sleep is set to never. The worker and the public site pause while it sleeps. The fix is a choice about the owner's PC, so it waits for the owner. Nothing on the PC was changed.
- **Verification:**
  - `uv run pytest -q libs/arbit-data/tests/test_nfl_availability.py services/worker/tests/test_daemon.py`: 24 passed.
  - Breaking the current-read rule, the future-data guard, or the 15-minute window each failed tests. The window case was added after a first run missed it.
  - Gates: `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy` passed (214 files, 118 source files). `mypy --strict` passed on `scripts/model`. The full `uv run pytest` gave 1,327 passed. The foundation validator gave PASS.

## Current state

After slice 2 ([handoff](2026-11-09-m3-slice2-catalog-targets.md)), the owner asked whether any route surfaces inactives without projection data. The owner then directed: "We should use NFL for both Inactives/Did Not Play, and weekly game status. It should also be pinged twice a day every day to keep projections current." (OWN-063)

**Implemented, not released.** It is on branch `claude/m3-model`, worktree `/home/andre/arbit-m3-model`, uncommitted. The running worker loads `main`, so nothing is read on schedule until the owner asks for a release. Test captures went only to the scratchpad. The database was not written.

What the owner needs to know:
- **Weekly game status:** NFL's API serves it. This is the official injury report: Out, Doubtful or Questionable, and practice participation, with no projection data.
- **Inactives:** NFL's API has no inactive designation. The only NFL route found is Next Gen Stats, which the owner set apart over permissions on 5 November (OWN-040). So it is built but off until the owner decides (Q-015).
- **Did not play after a game:** snap counts, as in the slice 2 participation labels.

## Completed work

- **Research** (SRC-31). Read-only requests to NFL's API, NFL Next Gen Stats and ESPN on 2026-11-10:
  - **NFL injury report:** `/football/v2/injuries` ignores week and team filters and pages with `pageToken`. 2026 is 2,821 rows over weeks 1–9 in three pages (about 2 MB), the same row count as nflverse's injuries file.
  - **NFL roster route:** it ignores the week and shows only season statuses. The v1 and v2 game details have no inactive field, and four likely routes returned 404.
  - **Next Gen Stats:** the current roster marked 9 players `I01` "Inactive" or `I02` "Inactive/3rd QB", from Baltimore and Jacksonville. The weekly per-team roster lists the 48 game-day players: Atlanta's week 9 list matches nflverse's 48 active.
  - **nflverse's source:** its rosters build takes 2016+ weekly status from Next Gen Stats through a private scraper.
  - **ESPN's core game roster:** after the game, it flagged `didNotPlay` for all 41 nflverse inactives in four week 9 games, plus 13 dressed players with no snap. Not used, because the owner chose NFL.
- **Code** (`libs/arbit-data/src/arbit_data/availability/`):
  - `sources`:
    - `read_injury_report` follows `pageToken` and refuses repeated tokens or more than 20 pages.
    - `NgsClient` allows only the two roster paths. `read_current_roster` and `read_game_day_rosters` use it.
    - `GameStatus` and `RosterStatus` parse the responses; `inactive` marks the `I` codes.
  - `capture`:
    - It keeps original bytes, game-status and roster Parquet, and a manifest with `startedAt`, `observedAt` (when the reads finished), week, counts and per-source errors. A failed source doesn't discard the others.
    - Captures are content-addressed under `ARBIT_AVAILABILITY_PATH` (default `data/availability`), listed in `captures.jsonl`.
    - Next Gen Stats is read only when `ARBIT_AVAILABILITY_NGS=1`.
  - `schedule`: 12:00 and 19:15 America/New_York, so daylight saving is handled.
- **Worker:**
  - The `availability` lane is in the default lane list. It reads at each scheduled time, catches up one missed read, records freshness `nfl.availability` (member label "NFL injury reports") and retries a failure after 30 minutes.
  - `arbit-worker availability-capture` reads once and prints counts, never paths.
- **Records:**
  - Decisions and issues: OWN-063, Q-015, R-064 update.
  - Sources, policy and plan: SRC-31, ADR-007 update (still proposed), the M3 plan's slice 2b.
  - Status, changelog, `.env.example`, AGENTS.md link.

## Verification

All commands ran in `/home/andre/arbit-m3-model`.

| Command | Result |
| --- | --- |
| `ARBIT_NFL_API_CLIENT_SOURCE=<main checkout>/data/nfl-api/client/nfl_games.py ARBIT_AVAILABILITY_PATH=<scratch> uv run --env-file <main checkout>/.env.local arbit-worker availability-capture` (Next Gen Stats off) | Exit 0. Week 2026 REG 9; 3 requests; 2,821 game-status rows, 588 Out; no errors |
| The same command before the Next Gen Stats setting existed, to test NGS | Exit 0. 36 requests, 4.5 MB: 1,722 current roster rows, 9 inactive; 1,440 game-day rows (30 teams × 48; two teams on bye) |
| The same command without the full client path | Exit 1. NFL sources recorded `NFL_API_CLIENT_MISSING`, while the NGS read was still kept. This confirmed the failure handling; the worker runs from the main checkout, where the relative path resolves |
| `uv run pytest -q libs/arbit-data/tests/test_nfl_availability.py services/worker/tests/test_daemon.py` | 21 passed (15 new) |
| Breaking six behaviors one at a time: inactive codes, the `pageToken` name, the repeated-token guard, finish versus start time, the schedule, the 30-minute retry | Each made at least one test fail |
| `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | All passed; 213 files formatted; 117 source files clean |
| `python3 scripts/validate_foundation.py` | PASS |
| Full `uv run pytest` | 1,324 passed |

## Decisions, issues and limitations

- **Q-015 (owner):** whether to read Next Gen Stats for inactives. Without it, no inactive designation reaches the Model before kickoff.
- **The injury report doesn't resolve game-time decisions** (SRC-32, `scripts/model/injury_report_outcomes.py 2026 7 8 9`).
  - nflverse's file and NFL's feed are identical (2,821 of 2,821 rows), and nflverse's file is already a pre-game input with history back to 2009.
  - **2026 weeks 7–9:** no Out or Doubtful player played. 149 of 229 Questionable players played, while 53 were inactive and still listed Questionable.
  - Downgrades before game day do reach the report: week 9 had 6 Questionable-to-Out changes on Saturday.
  - The direct NFL read adds timing and a record of each version, not new content.
- **ESPN's fantasy status already settles game-time decisions** (SRC-33, `scripts/model/espn_status_timing.py 2026 8 9`). Arbit stores every version of the ESPN league document, and each holds every pool player's `injury_status`, with no projection fields.
  - **Week 9:** 39 of 41 inactives that weren't already Out switched to `OUT` 62–86 minutes before kickoff, and 15 of 16 Questionable players who played switched to `ACTIVE`.
  - **Week 8** had no reads in those windows (R-066).
  - This would make Next Gen Stats unnecessary; the owner decides.
- **Unproven:** whether Next Gen Stats marks inactives before kickoff. It can be checked at Thursday's game, Washington at the Giants, kickoff 01:15 UTC Friday 13 November; inactives are due about 23:45 UTC Thursday.
- **Coverage (R-064):** two fixed reads miss the Sunday late window's inactives (posted about 2:35 PM Eastern) and morning international games. The 19:15 read lands about an hour before 8:15 PM kickoffs.
- **Size:** about 2 MB per read without Next Gen Stats and 4.5 MB with it, twice a day; unchanged responses are stored once.
- **Release:** merging and restarting the worker needs the owner's request. Until then nothing is read on schedule.
- **Slice 3:** reads the captures by decision time and adds their fields to the field catalog.

## Resume here

1. Check the first timer wake (Windows event 1, `wake.log`) and that the league reads appear in the window. Owner: ADR-007 acceptance; Q-014; Lineup-before-Scout; whether to release the `availability` lane.
2. Watch Thursday's game with `scripts/model/espn_status_timing.py 2026 10` after it ends, if the PC stays awake.
3. Slice 3 features, as in the [slice 2 handoff](2026-11-09-m3-slice2-catalog-targets.md).
