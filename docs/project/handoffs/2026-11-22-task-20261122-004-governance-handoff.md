# Task handoff — TASK-20261122-004 — Catch-up ingestion after downtime, NFL relink fix and stable live schedule scope (ENG-052)

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** When the PC wakes after missing data, the worker recovers every finished game the live lanes never read (ESPN scoreboard, summary and plays; NFL full record), records capture gaps and recovery times for ADR-007 A1/A3, and week 10 2026 is recovered; NFL games link to ESPN within minutes of a startup race

**Requirements:** DATA-008, MD-004, LV-001, GOVAI-011

**Change class:** live

**Scoped files:** libs/arbit-data/src/arbit_data/live/store.py, libs/arbit-data/src/arbit_data/live/feed.py, libs/arbit-data/src/arbit_data/live/nfl_feed.py, services/worker/src/arbit_worker/catchup.py, services/worker/src/arbit_worker/daemon.py, services/worker/src/arbit_worker/main.py, tests/integration/test_catchup.py, services/worker/tests/test_daemon.py, docs/engineering/catch-up.md, docs/engineering/member-application.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/governance/state.json, docs/project/status.md, docs/project/changelog.md, .env.example, foundation-manifest.json

## Review

Read daemon lanes, LiveFeed, NflFeed, live store, availability capture, league_history and tests. Self-healing on restart: league lane reads current state, every unrecorded lineup week and every period's transactions; statistics imports current nflverse revisions; the injury-report capture reads the whole season each time. Not self-healing: LiveFeed and NflFeed follow only the current week (store.game_timings scope = most recently observed week; NflFeed.discover = today's week), so a week that started and ended while nothing ran is never read. Read-only DB query 2026-11-22: periods 1-7 never captured (worker began week 8), 8 complete ESPN, 9 complete ESPN+NFL, 10 nothing (14 games), 11 current. Publishing a past week's board with observed_at=now would make it the most recently observed week and flip the live schedule scope. NflFeed rediscovers only every 6 h, so a startup race left all week 11 NFL games unlinked.

Files: services/worker/src/arbit_worker/daemon.py, libs/arbit-data/src/arbit_data/live/feed.py, libs/arbit-data/src/arbit_data/live/nfl_feed.py, libs/arbit-data/src/arbit_data/live/store.py, libs/arbit-data/src/arbit_data/availability/capture.py, libs/arbit-data/src/arbit_data/league_history.py, tests/integration/test_nfl_lane.py, tests/integration/test_live_store.py

## Plan

(1) store.game_timings scopes by the season's latest (season_type, week), so a recovered past week never becomes the live schedule. (2) NflFeed: rediscover every 120 s while current-week games are unlinked; recover_week(season_type, week) links a past week's schedule and reads each linked game's full record once. (3) LiveFeed: read_week_board(week) for a past scoreboard; recover_game(event) reads the summary, plays unless the NFL record owns them, then completes final checks. (4) New arbit_worker.catchup: outstanding finished games (kickoff+5h) in periods from the first captured one (or --from-period), excluding the current week; recover oldest week first (ESPN board, NFL record from the first NFL-lane week, ESPN summary/plays); source-gap snapshot from source health; append-only private receipt (ARBIT_CATCHUP_PATH) with kickoff and read time per game, no bodies. (5) catchup lane in the default worker lanes: never while a slate is active, one week per step, 30 min idle checks. (6) arbit-worker catchup [--dry-run] [--from-period] [--games-only]: also runs due availability and statistics steps. Tests: real-PostgreSQL integration for scope, relink, plan, recovery, receipt, deferral. Docs: catch-up guide, ENG-052, R-068, R-069, status, changelog. Rollback: revert the commit; lanes are independent.

Files: libs/arbit-data/src/arbit_data/live/store.py, libs/arbit-data/src/arbit_data/live/feed.py, libs/arbit-data/src/arbit_data/live/nfl_feed.py, services/worker/src/arbit_worker/catchup.py, services/worker/src/arbit_worker/daemon.py, services/worker/src/arbit_worker/main.py, tests/integration/test_catchup.py, docs/engineering/catch-up.md

## Implement

store.game_timings scopes by the season's latest (season_type, week); store.complete_final_checks. LiveFeed.read_week_board and recover_game. NflFeed: _store_schedule split from discover with unlinked count, RELINK_SECONDS=120 rediscovery while unlinked (R-069), recover_week for past weeks. New arbit_worker.catchup (outstanding_games, source_gaps, recover_week, run, plan_summary, append-only receipts under ARBIT_CATCHUP_PATH). daemon: CatchupLane (defers while active, one week per step, gap snapshot at construction) in default LANES; catchup_once CLI with --dry-run, --from-period, --with-lanes; main.py dispatch (and restored availability-capture's return). 12 real-PostgreSQL tests in tests/integration/test_catchup.py; the scope and relink tests fail with each fix reverted. Docs: catch-up guide, .env.example, member operations note, ENG-052, R-068, R-069.

Files: libs/arbit-data/src/arbit_data/live/store.py, libs/arbit-data/src/arbit_data/live/feed.py, libs/arbit-data/src/arbit_data/live/nfl_feed.py, services/worker/src/arbit_worker/catchup.py, services/worker/src/arbit_worker/daemon.py, services/worker/src/arbit_worker/main.py, tests/integration/test_catchup.py, docs/engineering/catch-up.md, docs/engineering/member-application.md, docs/project/decision-register.md, docs/project/known-issues.md, .env.example

## Validate

Observed exit 0 for foundation, live-replay, runtime-check (Ruff, strict mypy on 119 files, contracts, full pytest: 1341 passed in 52.6 s including real-PostgreSQL integration) and web-check (client generation, design rules, 32 Vitest tests, build, PWA). 12 new tests in tests/integration/test_catchup.py; the scope and relink tests fail with each fix reverted. Real-data dry run on a restored copy of arbit_local (arbit_catchup_test, 366 MB): first captured period 8, NFL records from 9, live week 11, outstanding exactly week 10's 14 unstored games. Not yet observed: network recovery against the copy and the real database (done in TASK-20261122-002 after the late games); the lane on the running worker (needs merge and restart).

Files: not separately listed

## Document

Status block (branch, not merged or released), changelog entry, catch-up operator guide, member operations note on restart policy and catch-up, ENG-052 decision row, R-068 outage and R-069 relink race in known issues, .env.example ARBIT_CATCHUP_PATH. Written before validation; unchanged since the checks.

Files: docs/project/status.md, docs/project/changelog.md, docs/engineering/catch-up.md, docs/engineering/member-application.md, docs/project/decision-register.md, docs/project/known-issues.md, .env.example

## Recorded commands

- `foundation`: exit=0, 2026-11-22T23:26:48Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=a56a19a3551d8e0ee994548e8171385d29294431bc00d6624d3bea6c89a41691
- `live-replay`: exit=0, 2026-11-22T23:26:49Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_live_actions.py", "libs/arbit-data/tests/test_live_motion.py"]; output SHA-256=f35eee7c7000a0d757965a7c81b0a12a144a59ffe2d98ba1fbfb28882f4f7eca
- `runtime-check`: exit=0, 2026-11-22T23:27:47Z; argv=["make", "runtime-check"]; output SHA-256=b67aa4a06af1bd38f4a547cecec2432c1d437979089aeac8bea787e231e62981
- `web-check`: exit=0, 2026-11-22T23:27:52Z; argv=["make", "web-check"]; output SHA-256=0c883eedbac7c49f0fa525ed4d5aba073033418adb6a8fb8e2fed7b1ccf2a2ca

## Findings / decisions / contradictions

- 2026-11-22T23:29:13Z [risk] Running worker (main, pre-fix game_timings) orders the schedule by most recent observation: a catch-up run against arbit_local before this branch is deployed briefly makes week 10 the live lane's schedule until its next current-board read. Run it only with no active games. — libs/arbit-data/src/arbit_data/live/store.py before ENG-052; running worker started 15:25 MST on de72924
- 2026-11-22T23:29:13Z [assumption] Kickoff + 5 h marks a game as settled for catch-up; later games belong to the live lanes. Overtime and weather delays rarely exceed it; a game still not final is reported not_final and retried on the next start. — catchup.GAME_LENGTH

## Remaining unresolved / blocked

Not merged or released. Postseason catch-up deferred (R-059). Weeks 1-7 only with --from-period. No alert when the database stays down (R-068).

## Next executable action

Push branch claude/catch-up-and-decisions and open a PR; after CI is green the owner merges, then restart arbit-worker (no migration) between games so the catchup lane and relink fix run; confirm a 'catchup' started line and receipts.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
