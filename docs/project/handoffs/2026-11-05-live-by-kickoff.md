# Handoff — 2026-11-05 — Live by kickoff: NFL API primary and the browser's live field

## Current state

Branch `claude/platform-reset`, local only and not pushed.

- **Committed:** up to `52331d4` (slice 5).
- **Uncommitted:** everything below. The owner commits when they ask.
- **The running app is upgraded** (07:47 Arizona time, with the owner's approval, OWN-043):
  - **Database:** migration `0008_nfl_api`, after a backup at `data/backups/2026-11-05/before-nfl-api-upgrade-074654.dump`.
  - **Services:** the API, the worker (with the new `nfl` lane) and the web build.
  - **Worker restarts:** three more by 07:51, for the kickoff rule, the empty-record safeguard and wiped-out plays.
  - **Health:** the API reports ready and `nfl.api.plays` is healthy.
- **Tonight:** Jacksonville at Baltimore, Thursday Night Football, 18:15 Arizona time (01:15 UTC on 2026-11-06).
  - **IDs:** ESPN `401873037`, NFL `ab380826-4feb-11f1-abca-2c54536568a9`.
  - **Art:** built at `data/live-art/401873037/`, with Gridiron's listed uniforms (JAX `A2`, BAL `W`) and Baltimore's usual field, labeled (OWN-044).
  - **Before kickoff:** the game page shows the empty field. Plays draw as they arrive.

## Completed work

Owner direction OWN-041 to OWN-044. Records:
- [NFL API plan](../../superpowers/plans/2026-11-05-nfl-api-primary.md)
- [survey](../../research/nfl-api-data-survey-2026-11-05.md)
- [route tests](../../research/nfl-api-routes-2026-11-05.md)

**The NFL API lane (ENG-041):**
- `libs/arbit-data/src/arbit_data/live/nfl_api.py`: the converter.
- `nfl_feed.py`: the lane and client.
- The worker lane `nfl`.
- Migration `0008`.
- The ESPN feed's fallback switch.
- `LivePlay` gains `source`, `snap_at`, `whistle_at`, `clock_end`, `jerseys` and `nfl`.
- `context.py`: game context moved into the library; `scripts/live/positions.py` re-exports it.

**Real-time pacing (ENG-042):** `pacing.py`, applied in `animation.py`.

**The browser's live field (ENG-043):**
- `apps/web/src/live/`: `scene.ts`, `led.ts` and `LiveField.tsx`.
- The animation and private art routes.
- `scripts/sprites/live_art.py`.
- The game page shows the field.
- The `live-animation` query refreshes on play events.

**Fixed along the way:**
- **Names:** the choreographer's name pattern took "A.Barner INTERCEPTED" as a name.
- **Clocks:** a scoring play's clock now runs from its snap.
- **Foul numbers:** they come from the game's own record.

## Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 1,176 passed, including `test_nfl_api.py` (10), `test_pacing.py` (5) and `tests/integration/test_nfl_lane.py` (6) |
| Ruff, format, mypy, `pnpm check:contracts`, `make web-check`, `make check` | Passed |
| `check_play_scripts.py --nfl=data/nfl-api/2026-11-05-week8-survey/expanded/direct_only_results/direct_weekly_details_week8_raw.json --paced` | 2,199 week-8 plays from the NFL record. 2 broken rules (R-044) |
| Week 8 interpreted from both sources | Shape differs on 5 of 2,199, start on 4, score on 0 |
| Isolated database copy `arbit_nfl_test` | The lane linked all 15 week-9 games. CHI at SEA: 183 current plays, all from the NFL; a second read changed nothing |
| Isolated app on port 8010 (`arbit_member_fixture`, fixture sign-in, its own build) | The field on the game page; stepping back by keyboard; no page errors or failed requests |
| The running app after the upgrade | Ready; the NFL lane discovered week 9 |

## Decisions, issues and limitations

- **Decisions:** OWN-041 to OWN-044, ENG-041 to ENG-043.
- **Issues:**
  - **R-042:** live behavior is unproven until kickoff.
  - **R-043:** each game's art is built by hand.
  - **R-044:** two cover men wait at a catch spot.
- **Scratch databases:**
  - `arbit_nfl_test` is a copy of the app's data for testing. Drop it when no longer needed.
  - `arbit_member_fixture` now also holds week 8's NFL tables, with week 9 removed.

## Resume here

1. **During JAX at BAL, the live slate proof (automation slice 8):**
   - Watch `journalctl --user -u arbit-worker -o cat | grep '"lane": "nfl"'`.
   - Measure each play's delay from the NFL whistle (`whistle_at`) to its stored revision (`first_observed_at`).
   - Note what the summaries and live-only fields show.
   - Check the game page.
2. **Commit when the owner asks.**
3. **Next:**
   - Build each game's art automatically before its kickoff (slice 6).
   - A request budget for Sunday's full slate.
