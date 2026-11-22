# Task handoff — TASK-20261122-006 — Correct TASK-005's playoff test so it exercises the postseason live week

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** The regular-season cap is proven by a test that fails without it: a January state whose live week is postseason (season type 3)

**Requirements:** DATA-008, GOVAI-017

**Change class:** live

**Scoped files:** tests/integration/test_catchup.py, docs/governance/state.json, docs/project/status.md, docs/project/changelog.md

## Review

Mutation check after TASK-005 closed: its test passes with the cap removed. outstanding_games skips (2, period) >= current; with current (2, 11) period 19 is already skipped. In January current is (3, w), so (2, 19) < (3, 1) and only the cap excludes it.

Files: tests/integration/test_catchup.py, services/worker/src/arbit_worker/catchup.py

## Plan

Seed a postseason live week (nfl_game season_type 3, week 1, final) in the playoff test; verify RED with the cap removed and GREEN with it; record both runs.

Files: tests/integration/test_catchup.py

## Implement

test_playoff_periods_are_left_to_the_live_lanes now seeds a postseason live week (nfl_game season_type 3, week 1) and asserts current_week == (3, 1) and the plan is [10, 11] (week 11 is outstanding once it is no longer live). Changelog and status updated.

Files: tests/integration/test_catchup.py

## Validate

Recorded check mutation-cap-removed: with the scoring_period <= 18 filter deleted, the playoff test fails (assert [10, 11, 19] == [10, 11]); the file is restored afterwards (git diff empty). With the cap: catch-up tests 12 passed; foundation, live-replay, runtime-check (full suite) and web-check exit 0.

Files: not separately listed

## Document

Changelog entry describing the false TASK-005 claim and its correction; status scope line cites this task. Written before validation.

Files: docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `mutation-cap-removed`: exit=0, 2026-11-22T23:33:53Z; argv=["bash", "-c", "cp services/worker/src/arbit_worker/catchup.py /tmp/claude-1000/-home-andre-arbit-fantasy-football/2ce75ffa-5c13-4be1-b560-0af3d67cef32/scratchpad/c.bak && sed -i '/scoring_period <= REGULAR_SEASON_WEEKS,/d' services/worker/src/arbit_worker/catchup.py && ! uv run pytest tests/integration/test_catchup.py -q -k playoff; s=$?; cp /tmp/claude-1000/-home-andre-arbit-fantasy-football/2ce75ffa-5c13-4be1-b560-0af3d67cef32/scratchpad/c.bak services/worker/src/arbit_worker/catchup.py; exit $s"]; output SHA-256=490ada6e8ddcf89778edea643d571a3d89dbb2e6d3b5ef3d91dbfaa66dc04bd2
- `foundation`: exit=0, 2026-11-22T23:33:53Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=5b10b74b8f67d46869520584a06550988e05e9988735d0a4c0d46b6f03b52a83
- `live-replay`: exit=0, 2026-11-22T23:33:54Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_live_actions.py", "libs/arbit-data/tests/test_live_motion.py"]; output SHA-256=0613449f232d012f5e999b75ef0b077952a166b9fd110c1304cf0ad1b5862827
- `runtime-check`: exit=0, 2026-11-22T23:34:48Z; argv=["make", "runtime-check"]; output SHA-256=76f6f789c0a8a5f54c0f0660de5a9ea624271435791cf2d2e1ac1d870e6ca096
- `web-check`: exit=0, 2026-11-22T23:34:53Z; argv=["make", "web-check"]; output SHA-256=a0385c3d2a0315a1c4ca48b8e3650f340cd0f562cad2e8dad61d6ea50573e041

## Findings / decisions / contradictions

- 2026-11-22T23:32:58Z [correction] TASK-20261122-005's validation said the new test fails without the cap; a mutation run shows it passes without it, because the seeded live week (2, 11) already excludes period 19 through the live-week filter. The real case needs a postseason live week (3, w). TASK-005's code change is correct; its test did not prove it. — Removing the scoring_period <= REGULAR_SEASON_WEEKS filter: test_playoff_periods_are_left_to_the_live_lanes still passed (1 passed)

## Remaining unresolved / blocked

None for this correction.

## Next executable action

Finish TASK-20261122-002 (worker restart between games, real catch-up), then push the branch and open the PR.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
