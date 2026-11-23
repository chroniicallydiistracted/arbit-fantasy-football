# Task handoff — TASK-20261123-003 — Game-day availability in the owner's order

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Give the Model one reader of each player's availability at a decision time in the owner's order (OWN-073): on the player's game day, ESPN's fantasy status read within 15 minutes is final (OWN-064, it carries inactives); otherwise the freshest copy of NFL's injury report, Arbit's own twice-daily capture (OWN-063) or nflverse's republication through the point-in-time reader; otherwise unknown, never assumed active (R-066). Normalize status and practice wording across sources and label every value's source, known-from time and basis. No feature, service or API change.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/availability.py, libs/arbit-model/tests/test_availability.py, scripts/model/availability_audit.py, docs/research/availability-audit-2026-11-23.json, docs/research/point-in-time-audit-2026-11-23.md, libs/arbit-model/README.md, docs/architecture/decisions/007-model-availability.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Review

Owner direction 2026-11-23: 'Previously weve tested Active List and Injury data from both ESPN and NFL. We should have a better route for more up to date injuries, however game day decisions should be the final say.' Read OWN-063 (NFL injury report twice daily for weekly game status), OWN-064 (ESPN fantasy status is the game-day input; current only within 15 minutes of a read), arbit_data.availability (capture index captures.jsonl with observedAt; the gameStatus table holds the whole season's report per capture; espn_status.status_as_of keyed by Arbit entity IDs). Real data, read-only: three NFL captures since 2026-11-22 23:43 UTC; the NFL capture and nflverse's injuries_2026 carry the same report (identical counts: 712 OUT, 762 QUESTIONABLE, 61 DOUBTFUL) in different wording (DIDNOT vs 'Did Not Participate In Practice'); ESPN's league document lists 1,063 pool players (1,031 athletes) with codes ACTIVE, INJURY_RESERVE, QUESTIONABLE, OUT, DOUBTFUL or none; entity_alias holds 18,875 current GSIS aliases.

Files: libs/arbit-data/src/arbit_data/availability/capture.py, libs/arbit-data/src/arbit_data/availability/espn_status.py, libs/arbit-data/src/arbit_data/availability/sources.py, docs/project/decision-register.md

## Plan

New arbit_model.availability: availability(source, pit, season, week, at, game_day) returns a frame per GSIS ID with status, practice, source, _known_from, _basis and final, plus lineage. Layers: nflverse injuries through PointInTime; the latest NFL capture finished before the decision without an injuries error; between those two copies of the same report the fresher known-from wins per player (NFL on a tie); on game day, when ESPN is current, ESPN's status replaces them and is final; on game day without a current ESPN read the lineage says game-day status unknown. Vocabulary: status upper-case codes, practice FULL/LIMITED/DNP. is_game_day(game, at) helper. StoredAvailability reads captures.jsonl and the object store under ARBIT_AVAILABILITY_PATH, ESPN status through status_as_of and the GSIS alias map. Unit tests with fakes; a read-only audit on real data before and on game day; docs: OWN-073, ADR-007 implementation note, R-070 update, plan, status, changelog.

Files: libs/arbit-model/src/arbit_model/availability.py, libs/arbit-model/tests/test_availability.py, scripts/model/availability_audit.py

## Implement

New arbit_model.availability: availability(source, pit, season, week, at, game_day) with nflverse injuries through PointInTime, the latest successful NFL capture before the decision, freshest-copy merge per player (capture on a tie), and on game day a current ESPN status that replaces them and is final; StoredAvailability reads captures.jsonl, capture manifests and ESPN status (status_as_of, GSIS athlete aliases); is_game_day helper; status and practice vocabulary normalized. Tests (5) and a read-only audit script with receipt. Docs: OWN-073, ENG-055, ADR-007 availability note, R-070, research note section, README, plan, status, changelog.

Files: libs/arbit-model/src/arbit_model/availability.py, libs/arbit-model/tests/test_availability.py, scripts/model/availability_audit.py, docs/research/availability-audit-2026-11-23.json

## Validate

make runtime-check passed (ruff, mypy, contracts, 1,371 tests including 5 new availability tests). Governance checks foundation, model-tests and point-in-time exited 0. Three deliberate breaks each fail availability tests. Real-data audit receipt written read-only. Not exercised: any feature, backtest or service.

Files: docs/research/availability-audit-2026-11-23.json, libs/arbit-model/tests/test_availability.py

## Document

Decision register OWN-073 and ENG-055; ADR-007 availability note; R-070 update; research note section with the real-data table; Model README; M3 plan; status and changelog.

Files: docs/project/decision-register.md, docs/architecture/decisions/007-model-availability.md, docs/project/known-issues.md, docs/research/point-in-time-audit-2026-11-23.md, libs/arbit-model/README.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-23T19:36:25Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=7c04aa679ebe5183b964fc626d03edb626e160498833f10bead875f7b49a3a54
- `model-tests`: exit=0, 2026-11-23T19:36:28Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=c2f67fe114dc068cf32e893fd53e3ef64c608f802d46acf4427a4556e7c5c289
- `point-in-time`: exit=0, 2026-11-23T19:36:30Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=d985275b972b60dcae6b8a7d270eaff5ce62ed5f974667e7eccfb7a066b26530

## Findings / decisions / contradictions

- 2026-11-23T19:36:39Z [observation] Real data (read-only): week 11 Sunday kickoff inside R-068: ESPN last read 2026-11-10, game-day status flagged unknown, 282 players from nflverse by the game-day rule; Monday night game day at 19:34 UTC 2026-11-23: ESPN current (read 14 s earlier), 1,026 final statuses, 37 unmapped pool entries (32 D/ST, 5 athletes), 216 more from NFL's 17:00 UTC capture; same moment before game day: all 313 from NFL's capture, fresher than nflverse. — docs/research/availability-audit-2026-11-23.json
- 2026-11-23T19:36:39Z [observation] Availability test sensitivity: using captures after the decision fails 2 tests, using a stale ESPN status fails 1, letting the older report copy win fails 2; source restored byte-identical. — libs/arbit-model/tests/test_availability.py

## Remaining unresolved / blocked

No feature, backtest or service uses the readers yet. Backtests of 2025 and earlier see only nflverse's final weekly injury report (R-070). Game-day inactives exist only from ESPN reads since 2026-10-31. The ENG-053 open rules remain labeled and revisable.

## Next executable action

Merge the PR for claude/m3-reader-speed-availability (TASK-20261123-002 and -003). Then M3 slice 3b under a model-class task: team environment and defense against the position (OWN-068) on the columnar reader; weather W1 beside it.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
