# Task: Interpret every stored play into facts (automation slice 1)

Status: **verified in code**, 2026-11-03. The normalizer change reaches the running worker with the next approved upgrade

- **Requirement IDs.** LV-003 (play graphics need facts, and the unknown fallback needs a reason). LV-005 (a revised play is re-interpreted from its current revision).
- **Specifications and decisions.**
  - [Automation plan](2026-11-03-live-play-automation.md), items 1 and 11.
  - OWN-021 and OWN-032 (only named players).
  - ENG-023 (re-creation label), ENG-029 and ENG-030 (kicks and the ball).
  - ENG-032 (catch spot from ESPN's yards after catch), ENG-033 (spots from `yardLine`).
  - [Live play detail research](../../research/live-play-detail-2026-11-03.md).
- **Baseline.**
  - The worker stores ESPN core API plays as `LivePlay` revisions (`libs/arbit-data/src/arbit_data/live/normalize.py`, `contracts.py`, `store.py`).
  - `LivePlay` keeps the text, kind, participants and roles, `statYardage`, and each spot's `yardsToEndzone` with its team. Nothing turns a play into facts yet; the seven review plays were choreographed by hand.
- **Found while reviewing.** ESPN's `yardsToEndzone` is wrong on a share of plays while the home team has the ball. It repeats `yardLine` instead of `100 − yardLine`.
  - **How often:** 54 of 114 punt starts in the captured games, and about 25 scrimmage spots, almost all in LAR–LAC.
  - **The reliable field:** `yardLine`, counted from the home team's goal line, agrees with the text ("to LAC 14" is 86 from the Rams' goal). The normalizer drops it today.
- **Scope.**
  1. **Normalizer.** Keep `yardLine` on each spot, plus ESPN's `yardsAfterCatch`, the `penalty` object (type, yards, status) and the `review` object (type, upheld).
     - New optional fields are left out of the stored payload when ESPN doesn't send them, so a play without them keeps its content hash.
     - `yardLine` is on nearly every play, so each game's plays get one new revision the next time the worker reads them. The client refetches and shows no "corrected" mark, because that mark compares results and credited players, not hashes.
  2. **Interpreter.** `libs/arbit-data/src/arbit_data/live/play_facts.py` has a `GameTeams` context (home, away and the text codes for each) and `interpret(play, teams) -> PlayFacts`. All spots are in the offense's frame, yards from its own goal line. The result holds:
     - the shape, the template the choreographer will use, and any facts that template needs but the play doesn't state
     - offense, defense, start and end spots, down, distance and line to gain
     - the named players by role
     - formation, plus pass, run, kick, penalty, fumble and extra-point details
     - touchdown, safety, turnover, out of bounds and replay result
  3. **Coverage.** `scripts/live/play_facts_coverage.py` re-normalizes the newest captured plays pages for every captured game, interprets them, and prints the coverage table and the spot checks. It reads only `data/live-captures` and the database.
- **Exclusions.** Choreography and scripts (slice 2). Fumble and penalty templates (slice 3): their facts are extracted, but they get no template yet. Any new provider request.
- **Interfaces later work relies on.** `PlayFacts` (version 1), `GameTeams.build(home_id, away_id, home_abbr, away_abbr, texts)` and `interpret(play, teams)`. A spot is an integer from 0 to 100 in the offense's frame. Kick landings can go up to 110, the back of the end zone.
- **Acceptance.**
  - Tests take real captured ESPN plays as fixtures, trimmed to factual play fields as the existing fixture is, one per shape and text form. They include the home-team punt, a LAR–LAC spot, a replay reversal, a no-play penalty, every kick result and every pass result.
  - The coverage run reports, by shape, how many plays have a template with no missing facts.
  - It checks facts against ESPN's own spots and text: the end spot against the spot the text states, and start plus yards against the end on plays without penalties or turnovers.
- **Rollback and data.** No migration. The normalizer change adds revisions and never rewrites one; reverting the code stops adding the fields. The interpreter is pure.
- **Decisions.** ENG-033, spots from `yardLine` with `yardsToEndzone` as fallback, recorded with this slice.

## Evidence and outcome

**Implemented.**
- **Contract and normalizer.** `FieldPoint.yard_line`, and `LivePlay.yards_after_catch`, `penalty` (`PlayPenalty`) and `review` (`PlayReview`), each left out of the payload when absent (`contracts.py`, `normalize.py`).
- **Interpreter.** `libs/arbit-data/src/arbit_data/live/play_facts.py`, with `PlayFacts` v1, `GameTeams`, `text_codes` and `interpret`.
- **Scripts.** `scripts/live/play_facts_coverage.py`, and `scripts/live/export_play_fixtures.py`, which writes `tests/fixtures/live/play-facts.examples.json`: 28 real plays trimmed to factual fields.
- **Tests.** `libs/arbit-data/tests/test_play_facts.py`, 45 tests.

**Coverage.** All 14 captured games, 2,604 plays. Every play normalized; 2,196 are football plays.

| Shape | Plays | Ready: template, nothing missing | No template yet (reason) |
| --- | --- | --- | --- |
| pass | 828 | 827 | 1 lateral |
| run | 725 | 724 | 1 lateral |
| kickoff | 149 | 149 | |
| penalty | 133 | 0 | 133 no-play (slice 3) |
| punt | 114 | 114 | |
| sack | 71 | 71 | |
| field goal | 57 | 57 | |
| scramble | 42 | 42 | |
| fumble | 29 | 0 | 29 (slice 3) |
| interception | 24 | 24 | |
| kneel | 18 | 18 | |
| spike | 6 | 6 | |
| **Football plays** | **2,196** | **2,032 (92.5%)** | |

Also excluded: 391 timeouts and period ends, and 17 coin tosses and other non-plays.

**Facts checked against ESPN's own spots and text.**

| Check | Plays | Agree |
| --- | --- | --- |
| End spot vs the spot the text states, on plays without penalties or turnovers | 1,627 | 1,627 (100%) |
| Start plus yards equals end, same plays | 1,627 | 1,627 (100%) |
| Placed from `yardsToEndzone` instead, start or end would be wrong | 2,032 | 76 wrong: 54 of 114 punts, 11 passes, 8 runs, 2 interceptions, 1 field goal |

**What the facts give the choreographer:**
- **Passes:** a catch spot on 548 of 551 completions; the other 3 have no yards after catch from ESPN and fall back to depth. Interception spots on 24 of 24, and depth and side on 277 of 277 incompletions.
- **Runs:** a direction on 724 of 725.
- **Punts:** landing and result on all 114: 42 returned, 35 fair catches, 14 out of bounds, 13 downed, 8 touchbacks, 2 muffed.
- **Kickoffs:** landing and result on all 149: 108 returned, 32 touchbacks, 3 short of the landing zone, 3 muffed, 2 out of bounds, 1 recovered.
- **Field goals:** distance and result on all 57: 45 good, 11 missed, 1 blocked.
- **Points after:** 74 attached to touchdowns: 60 good and 3 missed extra points, 6 successful and 5 failed two-point tries.

**Found in the data:**
- **Field goal distance** is the yards to the goal line plus 18 on 50 of 57 kicks, with 17 or 19 on the rest. The hold is 8 yards back, and the hand-made review renders used 7.
- **Penalty object:** ESPN sends one only for accepted penalties (193 of 193; 0 of 28 declined). Declined penalties come from the text.
- **Kickers on kickoffs:** ESPN lists the kicker of an out-of-bounds kickoff only as the penalized player. The interpreter recognises him by name.

**Commands.**

| Command | Result |
| --- | --- |
| `uv run python scripts/live/play_facts_coverage.py` | The tables above |
| `uv run pytest -q` | 658 passed, 45 of them new |
| `uv run ruff check .`, `ruff format --check .`, `mypy` | Passed |
| `ruff check` and `ruff format --check --line-length 120` on the two scripts | Passed |
| `pnpm check:client`, `pnpm check:contracts`, `make check` | Passed |

**Limits and next.**
- **The running worker** still uses the old normalizer until the next approved upgrade. Until then, newly stored plays have no `yard_line` or yards after catch, so home-team punts get wrong spots from stored payloads; the captures still hold everything.
- **The first read after the upgrade** gives each play one new revision. The client refetches without showing a "corrected" mark.
- **Next:** slice 2, the choreographer.
