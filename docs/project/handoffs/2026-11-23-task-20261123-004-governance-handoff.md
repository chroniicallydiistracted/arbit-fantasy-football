# Task handoff — TASK-20261123-004 — M3 slice 3b: team environment and defense against the position

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Point-in-time team features for each game as of its decision time, built only through the point-in-time reader: per-game FFA points from the shared scorer on rows the reader returns, team environment (pace, dropback rate, pass rate over expected, EPA, success, drives, red zone, scoring) for offense and defense with the signal study's measured shrinkage, game context (home, rest, roof, surface, division), and defense against the position (OWN-068): FFA points and opportunities allowed to QB, RB, WR, TE and K and D/ST points allowed by each offense, raw and adjusted for the offenses faced, shrunk with constants measured here. Every feature has definition, unit, window, cutoff, coverage and provenance, and a mutation test proves rows published after the decision never change a feature. No fitted model, projection, service or API change.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/team_features.py, libs/arbit-model/src/arbit_model/feature_specs.py, libs/arbit-model/tests/test_point_in_time.py, libs/arbit-model/tests/test_gamebook.py, libs/arbit-model/tests/test_team_features.py, scripts/model/defense_position_study.py, scripts/model/team_features_audit.py, docs/research/defense-position-study-2026-11-23.json, docs/research/team-features-2026-11-23.md, docs/research/team-features-audit-2026-11-23.json, libs/arbit-model/README.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/architecture/model-specification.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Review

Read ADR-006's team-first structure and the methods research: team environment and opponent first, D/ST mostly the opponent, constants as games for half signal. Read the signal study's team definitions (stats_team: plays = attempts + sacks + carries, dropbacks = attempts + sacks, EPA = passing + rushing; sacks forced and takeaways from the opponent row) and its split_half method; the targets module (per-game SeasonRows, athlete and defense lines); and the stat-line adapter's play and team columns. The stored slice 2 targets (index 4afbd836) cover 2012-2026 through 2026-11-10. No measured constant existed for FFA points allowed by position.

Files: docs/architecture/decisions/006-model-architecture.md, docs/research/ffa-projection-methods-2026-11-09.md, docs/research/ffa-signal-study-2026-11-09.json, scripts/model/ffa_signal_study.py, libs/arbit-model/src/arbit_model/targets.py, libs/arbit-data/src/arbit_data/nflverse/stat_lines.py

## Plan

Add _manifest to readings; gamebook.py scoring each completed game known at the decision with the shared scorer, cached per version combination; a study measuring split-half constants for FFA points allowed by position and D/ST points allowed (raw and adjusted for offenses faced) with the signal study's method; feature_specs.py with definition, unit, window, cutoff, sources and constants for every column; team_features.py producing team rates (raw, shrunk, last season), opponent defense, defense against the position and context per team per game; tests including a mutation test and constants-versus-receipt; a read-only real-data audit; docs.

Files: libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/team_features.py, libs/arbit-model/src/arbit_model/feature_specs.py, scripts/model/defense_position_study.py

## Implement

point_in_time: readings carry _manifest. gamebook.py: Gamebooks.at(season, at) reads schedules (scores), pbp, player and team statistics through the reader, keeps games with all four known, scores each with targets() once per version combination, and returns team-games (signal study definitions), FFA points and opportunities by position, and D/ST points. defense_position_study.py: stability of points allowed by position and D/ST points allowed, raw and leave-one-out adjusted, 2016-2025, receipt committed. feature_specs.py: 65 specs and 20 constants with receipt paths. team_features.py: features per team per game, grouped by decision time, with coverage and lineage. team_features_audit.py and receipt. Docs: research note, ENG-056, README, plan, status, changelog.

Files: libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/feature_specs.py, libs/arbit-model/src/arbit_model/team_features.py, libs/arbit-model/tests/test_team_features.py, scripts/model/defense_position_study.py, scripts/model/team_features_audit.py, docs/research/defense-position-study-2026-11-23.json, docs/research/team-features-audit-2026-11-23.json

## Validate

make runtime-check passed (ruff, mypy, contracts, 1,377 tests including 6 new). Governance checks foundation, model-tests and point-in-time exited 0. Two deliberate breaks each fail a test. Real-data audit (read only): 2025 week 10 at each kickoff and 2026 week 12 at the run build with every feature fully covered, about 5 s per week. Not exercised: any fitted model, backtest or service.

Files: docs/research/team-features-audit-2026-11-23.json, docs/research/defense-position-study-2026-11-23.json, libs/arbit-model/tests/test_team_features.py

## Document

Research note team-features-2026-11-23.md (study table and what it means for sit/start, feature list, real-data results, tests, limits); ENG-056; Model README; M3 plan slice 3 order; status (PR #5 merged, 3b summary, open work) and changelog.

Files: docs/research/team-features-2026-11-23.md, docs/project/decision-register.md, libs/arbit-model/README.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-23T19:49:29Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=9077cfbe00f9028571007f575e1ff22b70a43c7885d89e39993eac22b3fcffdb
- `model-tests`: exit=0, 2026-11-23T19:49:36Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=3db82f5e524516abba03f510f8f214740c937bf520a58c260516aafe4c536e3e
- `point-in-time`: exit=0, 2026-11-23T19:49:37Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=c43aa8f1633ea79bbb2939dffa347976f905e822c7eed850294278328308979d

## Findings / decisions / contradictions

- 2026-11-23T19:48:16Z [correction] The review and plan sections of this task were recorded after implementation had started; their content is what was read and designed before the code was written. — docs/governance/tasks/TASK-20261123-004.json
- 2026-11-23T19:49:46Z [observation] Defense-against-position stability 2016-2025 (315-320 team-seasons each), games for half signal raw/adjusted: QB 30.6/22.2, RB 18.7/20.0, WR 44.1/42.0, TE 37.6/40.1, K 49.4/55.3, D/ST points allowed by offense 9.2/9.1. — docs/research/defense-position-study-2026-11-23.json
- 2026-11-23T19:49:46Z [observation] Feature test sensitivity: reading three days past the decision fails the mutation test; dropping the opponent adjustment fails the defense-against-position test; source restored byte-identical. — libs/arbit-model/tests/test_team_features.py

## Remaining unresolved / blocked

Play-by-play team rates (pass rate over expected, success, drives, red zone) are deferred until their constants are measured. Positions use nflverse's current labels. No fitted model, backtest or service uses the features yet; slice 4 decides their weights.

## Next executable action

Merge the PR for claude/m3-slice3b (TASK-20261123-004). Then M3 slice 3c under a model-class task: availability and role features (snap, target, air-yard, carry and red-zone shares; injury and practice status through arbit_model.availability; teammates' absences), with weather W1 beside it. Ask the owner for the NWS User-Agent contact before W3.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
