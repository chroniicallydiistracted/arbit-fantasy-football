# Task handoff — TASK-20261123-001 — M3 slice 3a: point-in-time nflverse reader and catalog re-review

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Give every Model feature a reader that returns only what was known before a decision time under ADR-007 as amended (OWN-066 A1-A4): capture gaps from Arbit's own read history, per-table units and timing rules, labeled bases (observed, source-timestamp, retrospective-rule), and a mutation test proving rows published after the decision time never change a result. Re-review the field catalog so timing-only exclusions become applicability rules (A2). No features, fitted model, API or UI; no writes to arbit_local.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/timing.py, libs/arbit-model/src/arbit_model/vintages.py, libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/src/arbit_model/fields.py, libs/arbit-model/src/arbit_model/nflverse_fields.json, libs/arbit-model/tests/test_point_in_time.py, libs/arbit-model/tests/test_model_fields.py, libs/arbit-model/README.md, libs/arbit-model/AGENTS.md, tests/integration/test_model_point_in_time.py, scripts/model/point_in_time_audit.py, scripts/model/field_catalog.py, docs/research/point-in-time-audit-2026-11-23.md, docs/research/point-in-time-audit-2026-11-23.json, docs/architecture/model-specification.md, docs/architecture/decisions/007-model-availability.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/roadmap.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Review

Read ADR-007 with amendments A1-A4, the M3 plan's slice 3 scope, the field catalog (63 rules; 528 excluded, 5 outcome), model inputs/storage, and Arbit's nflverse read history in arbit_local (read-only). Findings: (1) each daily statistics run registers a new catalog, so dataset_import keeps one read per file per run (11 runs 2026-10-31..11-22); with the 36 h statistics stale window this yields two capture gaps: 11-01 10:00 to 11-03 02:11 (40 h) and 11-10 04:01 to 11-22 22:45 (R-068). (2) nflverse injuries files lack date_modified from 2025 on, so ADR-007's source-timestamp rule applies only to 2024 and earlier; newer rows need a labeled game-day rule. (3) Depth charts from 2025 are daily dt snapshots per team (827k rows in 2026). (4) Next Gen Stats week 0 rows are season aggregates. (5) Season-aggregate files (stats reg/regpost, PFR season) are rebuilt weekly. (6) Catalog exclusions made only for timing: current-snapshot (15) and draft-career-totals (23); weather-after-game (5) is an outcome rule that A2 makes history. Policy exclusions stay (OWN-061, legacy duplicate, free text, release tests); betting lines move to the OWN-067 gate.

Files: docs/architecture/decisions/007-model-availability.md, docs/superpowers/plans/2026-11-09-m3-model.md, libs/arbit-model/src/arbit_model/fields.py, libs/arbit-model/src/arbit_model/inputs.py, libs/arbit-model/src/arbit_model/nflverse_fields.json, libs/arbit-data/src/arbit_data/freshness.py, libs/arbit-data/src/arbit_data/nflverse/service.py, libs/arbit-data/src/arbit_data/schema.py

## Plan

Three modules in libs/arbit-model. timing.py: kickoff calendar from the schedule (gameday/gametime are US Eastern) and known-from rules per ADR-007 decision 4 (game day+1 12:00 UTC for statistics and play-by-play; +2 days for snaps and NGS; +4 days 00:00 UTC for PFR, FTN, QBR; next 07:00 UTC after an injury date_modified or depth chart dt, else 07:00 UTC on game day for injuries without date_modified; after the week's games for weekly rosters; after the season for participation and season aggregates; draft, contract and trade dates; always for fixed facts; as-imported only for current snapshots), and a registry giving every readable table its unit (game, player-week, team snapshot or row) and row timing. vintages.py: per-file versions and successful reads from dataset_manifest and dataset_import, and gaps by the family stale window (A3). point_in_time.py: read(key, columns, at) returns rows only from the version Arbit held at the decision time (basis observed), plus, when the decision time falls in a gap or before the first read, units first held after it whose known-from is min(first read holding them, max(source time or rule, gap start)) (A1); each row carries known-from and basis, and a lineage record lists manifests, gaps and basis counts. Unregistered tables, policy-excluded fields and gated fields (OWN-067) are refused unless the gate is named. Catalog A2: new use as_imported for current-snapshot and draft-career-totals; weather-after-game becomes history; betting lines stay excluded under the OWN-067 gate; a test pins the policy-only exclusion set. Tests: synthetic multi-version histories with a mutation test (alter every row published after the decision time; identical result), gap admission bounds, labels, refusals; DB adapter integration test; audit script over real data writing a research receipt. Docs, decisions and status after.

Files: libs/arbit-model/src/arbit_model/timing.py, libs/arbit-model/src/arbit_model/vintages.py, libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/src/arbit_model/fields.py, libs/arbit-model/tests/test_point_in_time.py, tests/integration/test_model_point_in_time.py, scripts/model/point_in_time_audit.py

## Implement

Added arbit_model.timing (kickoff calendar from the newest schedule with franchise-code fallback; known-from rules per ADR-007 decision 4 plus labeled rules where the ADR is silent; 23 registered table patterns with units), arbit_model.vintages (versions from dataset_manifest, successful reads from dataset_import, gaps by the 36 h stale window, bounded table cache) and arbit_model.point_in_time (held version plus A1 gap admission; known-from = t1 when the previous read is within the window, else min(t1, max(source time or rule, gap start)); per-row _known_from/_basis; lineage; refusal of unregistered tables, uncatalogued fields and policy-excluded fields without their gate). Catalog A2 re-review: new use as_imported (current-snapshot 15, draft-career-totals 23), weather-after-game to history, betting lines under OWN-067; regenerated nflverse_fields.json (also 8 upstream type changes). Tests: 20 reader tests incl. mutation test, 2 PostgreSQL integration tests, catalog tests pin policy exclusions. Audit script and receipt over real history. Docs: research note, ADR-007 implementation note, model spec status, M3 plan slice order 3a-3e, ENG-053, R-070, R-071, README/AGENTS, status (incl. PR #3 merge and worker restart) and changelog.

Files: libs/arbit-model/src/arbit_model/timing.py, libs/arbit-model/src/arbit_model/vintages.py, libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/src/arbit_model/fields.py, libs/arbit-model/src/arbit_model/nflverse_fields.json, libs/arbit-model/tests/test_point_in_time.py, libs/arbit-model/tests/test_model_fields.py, tests/integration/test_model_point_in_time.py, scripts/model/point_in_time_audit.py, docs/research/point-in-time-audit-2026-11-23.md, docs/research/point-in-time-audit-2026-11-23.json, libs/arbit-model/README.md, libs/arbit-model/AGENTS.md, docs/architecture/decisions/007-model-availability.md, docs/architecture/model-specification.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/status.md, docs/project/changelog.md

## Validate

make runtime-check passed in the worktree: ruff lint, mypy, contracts and 1,366 tests (incl. the 2 new PostgreSQL tests and 20 reader tests). Governance checks foundation, model-tests and point-in-time exited 0. Mutation check of the tests: three deliberate reader breaks each failed tests (1, 9, 6) and the source was restored byte-identical. Real-history audit (read-only): 56 table reads at four decision times, 0 rows known at or after their decision; receipt docs/research/point-in-time-audit-2026-11-23.json. Not exercised: any feature, backtest or service; the reader runs in no lane.

Files: docs/research/point-in-time-audit-2026-11-23.json, libs/arbit-model/tests/test_point_in_time.py, tests/integration/test_model_point_in_time.py

## Document

Research note and receipt for the audit; ADR-007 implementation note (injury rule for files without date_modified, meaning of the observed label); model specification status line (ADR-007 accepted, reader named); M3 plan slice 3 order 3a-3e; ENG-053; R-070 and R-071 plus the officials note; Model README and AGENTS rule that features read only through PointInTime; status (PR #3 merged by the owner, worker restarted on e005aa6, slice 3a not merged) and changelog.

Files: docs/research/point-in-time-audit-2026-11-23.md, docs/architecture/decisions/007-model-availability.md, docs/architecture/model-specification.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/status.md, docs/project/changelog.md, libs/arbit-model/README.md, libs/arbit-model/AGENTS.md

## Recorded commands

- `foundation`: exit=0, 2026-11-23T19:09:36Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=de7ddbdbe0a7de27fbeac6ce79684ee8b60bd835ec72f87c01ab1066d4e49c06
- `model-tests`: exit=0, 2026-11-23T19:09:37Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=0c8173b11698f2f3941c2743cb7c8b879562f206ae57e4487437e6aed0e9dae1
- `point-in-time`: exit=0, 2026-11-23T19:09:39Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=21b78a12f1ca1de55ff899bc20d38dacdf92ce5ac9a71cfb17d657084e3b3391

## Findings / decisions / contradictions

- 2026-11-23T18:54:11Z [observation] nflverse injuries files have no date_modified column from 2025 on (2020 and 2023 have it; 2025 and 2026 do not). ADR-007 decision 4 assumed it; those rows use a labeled retrospective rule instead. — read-only schema check of injuries_2020/2023/2025/2026 current manifests in arbit_local
- 2026-11-23T18:54:11Z [observation] Capture gaps under the 36 h statistics stale window: 2026-11-01T10:00Z to 2026-11-03T02:11Z (no import on 2 November) and 2026-11-10T04:01Z to 2026-11-22T22:45Z (R-068). — dataset_import checked_at per catalog run, arbit_local read-only
- 2026-11-23T19:08:22Z [observation] Mutation check of the tests: removing the gap-start bound fails 1 reader test; admitting every unit fetched after the decision fails 9; ignoring gaps fails 6. The implementation was restored byte-identical (diff -q). — libs/arbit-model/tests/test_point_in_time.py; scratchpad copy of point_in_time.py
- 2026-11-23T19:08:22Z [observation] Real-history audit: 56 table reads at four decision times (2025 wk11, 2026 wk9 observed, 2026 wk10 and wk11 inside R-068) returned 0 rows known at or after the decision; 0 units bounded by a gap start; officials has 28 unplaceable rows (4 games); runtime 34 s, peak RSS 2.2 GB. — docs/research/point-in-time-audit-2026-11-23.json
- 2026-11-23T19:08:22Z [assumption] Where ADR-007 is silent, ENG-053 sets labeled rules: injury rows without date_modified at 07:00 UTC game day; pre-2025 weekly depth charts 12:00 UTC the day before the week's first game; REG schedule rows 1 June, postseason rows the day after the previous round; season files 1 March after the season; draft 1 May; contracts 1 June of the next year. The owner may revise any of them. — docs/project/decision-register.md ENG-053
- 2026-11-23T19:09:52Z [next_step] Owner reviews and merges the PR for claude/m3-slice3-reader. Then slice 3b under a new model-class task: team environment and defense against the position (OWN-068), with placement done in columns (R-071); weather W1 beside it. — docs/superpowers/plans/2026-11-09-m3-model.md

## Remaining unresolved / blocked

No feature, backtest or service uses the reader yet. R-070 (injury files from 2025 lack date_modified; game-day rule), R-071 (per-row placement: 34 s and 2.2 GB on the full history), four officials games unplaceable. The ENG-053 rules the ADR left open are labeled and await any owner revision. The owner's uncommitted .claude/settings.json permission entries in the main checkout are untouched.

## Next executable action

Merge the PR for claude/m3-slice3-reader (TASK-20261123-001). Then M3 slice 3b under a model-class task: team environment and defense against the position (OWN-068) built on arbit_model.point_in_time, with column-wise placement (R-071); weather W1 (venue table, forecast record) beside it. Ask the owner for the NWS User-Agent contact before W3.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
