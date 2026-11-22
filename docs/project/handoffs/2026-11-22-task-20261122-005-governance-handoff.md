# Task handoff — TASK-20261122-005 — Catch-up considers regular-season weeks only (periods 1-18)

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** In the postseason the catch-up never reads ESPN scoring periods 19+ as regular-season weeks; postseason games stay with the live lanes (R-059)

**Requirements:** DATA-008, LV-001

**Change class:** live

**Scoped files:** services/worker/src/arbit_worker/catchup.py, tests/integration/test_catchup.py, docs/engineering/catch-up.md, docs/governance/state.json, docs/project/status.md, docs/project/changelog.md

## Review

Self-review of ENG-052 after TASK-004 closed: outstanding_games filters nfl_schedule_game by scoring_period >= start only. ESPN's pro schedule continues scoring periods past the 18-week regular season for playoff games, and current_week compares (2, period) with (3, w) in January, so postseason periods would be read as REG weeks 19+ on every worker start: wasted ESPN/NFL requests and not_listed receipts.

Files: services/worker/src/arbit_worker/catchup.py, libs/arbit-data/src/arbit_data/live/store.py

## Plan

Add REGULAR_SEASON_WEEKS = 18 and filter scoring_period <= 18 in outstanding_games; one integration test seeding a period 19 game in the past; guide's Limits line. Checks: live class.

Files: services/worker/src/arbit_worker/catchup.py, tests/integration/test_catchup.py, docs/engineering/catch-up.md

## Implement

catchup.REGULAR_SEASON_WEEKS = 18 and outstanding_games filters scoring_period <= 18; test_playoff_periods_are_left_to_the_live_lanes (period 19 game in January stays out of the plan); guide Limits line; status scope line; changelog entry with correction of TASK-004's test count (11, not 12).

Files: services/worker/src/arbit_worker/catchup.py, tests/integration/test_catchup.py, docs/engineering/catch-up.md

## Validate

Observed exit 0: foundation, live-replay, runtime-check (Ruff, strict mypy, contracts, full pytest including PostgreSQL integration; catch-up file 12 passed) and web-check. The new test fails without the cap: a period 19 game from early January would be planned.

Files: not separately listed

## Document

Changelog entry with the TASK-004 test-count correction, status scope line, catch-up guide Limits. Written before validation; unchanged since.

Files: docs/project/status.md, docs/project/changelog.md, docs/engineering/catch-up.md

## Recorded commands

- `foundation`: exit=0, 2026-11-22T23:31:31Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=31f68a45638eda9a025ec01eb08f4000fa0a69b9a0ad27cbc0074118afe5a6fa
- `live-replay`: exit=0, 2026-11-22T23:31:32Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_live_actions.py", "libs/arbit-data/tests/test_live_motion.py"]; output SHA-256=13ddb55cca1bca496f87efa45d432907137319fbfc4fdbb33adcaf83871c40f5
- `runtime-check`: exit=0, 2026-11-22T23:32:24Z; argv=["make", "runtime-check"]; output SHA-256=67448a29f17cb385304b3422b6a83cf1bfec31b3e25aede60ca54ceaa0fb74d4
- `web-check`: exit=0, 2026-11-22T23:32:29Z; argv=["make", "web-check"]; output SHA-256=214cddd43e94a93b830147962e60e74a922096b19e862be6a2731a7e1dbf944e

## Findings / decisions / contradictions

- 2026-11-22T23:31:31Z [correction] TASK-20261122-004's implementation and validation summaries and changelog said 12 tests in tests/integration/test_catchup.py; that commit (34d212e) had 11. The changelog line is corrected; the closed task's record is left as history. — git show 34d212e:tests/integration/test_catchup.py | grep -c '^def test' -> 11

## Remaining unresolved / blocked

None for this change.

## Next executable action

Finish TASK-20261122-002 (worker restart between games, real catch-up), then push the branch and open the PR.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
