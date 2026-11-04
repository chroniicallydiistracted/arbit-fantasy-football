# Handoff — 2026-11-03 — Play facts (automation slice 1)

## Current state

Branch `claude/platform-reset`, local only and not pushed. Slice 1 is **uncommitted** in the working tree on top of `5d2edf2`. Live (M6) is in progress.

- **Slice 1 is done in code.** The [task record](../../superpowers/plans/2026-11-03-play-facts.md) holds its evidence.
- **The running app hasn't changed.** `arbit-api` and `arbit-worker` were not touched, and the database was only read. The normalizer change reaches the worker with the next approved upgrade (R-040), alongside R-039.
- **The plan.** The [automation plan](../../superpowers/plans/2026-11-03-live-play-automation.md) continues with slice 2.

## Completed work

- **Normalizer and contract** (ENG-033).
  - `FieldPoint.yard_line`: ESPN's `yardLine`, from the home goal line.
  - `LivePlay.yards_after_catch`, `penalty` and `review`.
  - Each is left out of the payload when absent, so such plays keep their content hash.
- **Interpreter.** `libs/arbit-data/src/arbit_data/live/play_facts.py` has:
  - `GameTeams.build(home, away, home_code, away_code, seen)`, where `seen` comes from `text_codes(texts)`. It maps gamebook codes such as BLT, ARZ, LA and WAS to the teams.
  - `interpret(play, teams) -> PlayFacts` (version 1). Spots are in the offense's frame, 0 to 100, and kick landings go up to 110.
  - Templates for pass, spike, interception, sack, run, scramble, kneel, punt, kickoff, field goal, extra point and two-point try. `missing` lists the facts a template lacks, and `reason` says why a play has none.
- **Evidence.** `scripts/live/play_facts_coverage.py` re-normalizes and interprets every captured game. `scripts/live/export_play_fixtures.py` writes `tests/fixtures/live/play-facts.examples.json`, 28 real plays.
- **Tests.** `libs/arbit-data/tests/test_play_facts.py`, 45 tests that check rules: start plus yards equals end, air plus yards after catch equals the gain, field goal distance is yards to goal plus 17–19, and punt start plus distance equals the landing.
- **Records.** The task record, ENG-033, R-040, the plan's slice 1 and its 8-yard hold, the changelog, status, and the `AGENTS.md` handoff link.

## Verification

| Command | Result |
| --- | --- |
| `uv run python scripts/live/play_facts_coverage.py` | 14 games, 2,604 plays, none failed to normalize. 2,032 of 2,196 football plays ready. End spot vs text 1,627 of 1,627; start plus yards 1,627 of 1,627 |
| `uv run pytest -q` | 658 passed, 45 new |
| `uv run ruff check .`, `ruff format --check .`, `mypy` | Passed |
| Ruff check and format, line length 120, on `scripts/live/*.py` by file | Passed |
| `pnpm check:client`, `pnpm check:contracts`, `make check` | Passed |

Rerunning `export_play_fixtures.py` reproduces the fixture byte for byte.

## Decisions, issues and limitations

- **ENG-033 and R-040.** ESPN's `yardsToEndzone` isn't flipped for the home team on some plays (54 of 114 punts). Spots come from `yardLine`. Plays stored by the running worker keep the wrong value until the upgrade. After it, each game's plays get one new revision on their next read. The client refetches and shows no "corrected" mark.
- **Field goal hold.** Measured at 8 yards: distance is the yards to goal plus 18 on 50 of 57. Slice 2 and 3 choreography must use it; the hand-made review renders used 7.
- **ESPN quirks.** The penalty object exists only for accepted penalties. An out-of-bounds kickoff's kicker is listed only as the penalized player.
- **Not covered yet.** Fumbles (29) and no-play penalties (133) have facts but no template until slice 3. The 2 laterals show their text.
- **Decisions for the owner.** Approval of the next upgrade, which carries R-039 and R-040, before Thursday's game would give live plays `yardLine` and yards after catch. Q-012 is open.

## Resume here

1. Slice 2 of the [plan](../../superpowers/plans/2026-11-03-live-play-automation.md): `libs/arbit-data/src/arbit_data/live/choreography.py`, which turns `PlayFacts` into a play script for pass, run, sack and interception. The script schema goes in `packages/contracts`. Evidence: the whole CHI at SEA game rendered from generated scripts by the Python renderer.
2. See [status](../status.md) and the [roadmap](../roadmap.md).
