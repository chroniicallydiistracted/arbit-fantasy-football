# Task handoff — TASK-20261123-002 — Columnar point-in-time reader and owner timing order

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Make the point-in-time reader fast enough for whole-season feature building (R-071) by placing rows in columns with polars and returning frames instead of per-row dictionaries, with identical results; answer the owner's local-data question with measurements; and record the owner's timing order (use whatever data Arbit holds at the decision; fall back to source timestamps or family rules only for data that arrived during a gap or was not yet held) as an ADR-007 clarification. No features, service or API change.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/pyproject.toml, uv.lock, libs/arbit-model/src/arbit_model/timing.py, libs/arbit-model/src/arbit_model/vintages.py, libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/tests/test_point_in_time.py, tests/integration/test_model_point_in_time.py, scripts/model/point_in_time_audit.py, docs/research/point-in-time-audit-2026-11-23.md, docs/research/point-in-time-audit-2026-11-23.json, docs/research/point-in-time-audit-columnar-2026-11-23.json, libs/arbit-model/README.md, docs/architecture/decisions/007-model-availability.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json

## Review

Owner direction 2026-11-23: (1) speed: consider housing data locally, or fetch directly from the nflverse repository; (2) timing: 'the primary rule should allow the model to use whatever data is immediately available, then fall back to specific timestamps where the data refreshed during a gap or is not yet available'; (3) injuries: a more current route, with game-day decisions as the final say (TASK-20261123-003). Measured on one 2026 depth chart version (827k rows, 3.7 MB local Parquet): checksum 0.01 s, Parquet read 0.02 s, conversion to Python dicts 0.2 s, per-row placement 1.55 s; columnar parse and grouping 0.05 s. A 2025 play-by-play file (21.6 MB): read 0.06 s, to_pylist 2.0 s. The data is already local; the cost is per-row Python. Reviewed point_in_time.py, timing.py and vintages.py; polars 1.44 is already a dependency of arbit-data. The current reader already uses held data first (observed) and rules only for units first held after a gap or never held.

Files: libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/src/arbit_model/timing.py, libs/arbit-model/src/arbit_model/vintages.py, libs/arbit-data/pyproject.toml, docs/research/point-in-time-audit-2026-11-23.md

## Plan

Rewrite placement as polars expressions: Calendar gains frames for game IDs (with old GSIS aliases and schedule known-from), team-weeks (with franchise-code aliases) and week first/last days; each TableSpec gets place(frame, calendar, season) returning _unit, _known, _basis in input order, and declares the columns it needs. VintageSource.table returns a polars DataFrame (missing columns null). PointInTime keeps unit-level frames per version and a first-holding frame per key (unit, first index, rule, basis, after-game time), computes known-from and basis with expressions, and returns Reading.frame (rows stays as a convenience). Semantics unchanged: the 20 reader tests and 2 integration tests must pass as they are, apart from placement unit tests moved to the columnar functions, and the real-history audit must reproduce every unit count, basis count and latest known-from of the 2026-11-23 receipt. Record the owner's timing order as ADR-007 clarification A5 and OWN-072, and the local-data answer with measurements.

Files: libs/arbit-model/src/arbit_model/timing.py, libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/src/arbit_model/vintages.py

## Implement

timing.py: placement rewritten as polars expressions (Calendar gains id, team-week and week frames; every TableSpec has place() and needs); vintages.py returns polars frames with missing columns as null; point_in_time.py computes unit frames per version, a first-holding frame per key and known-from with expressions, caches each version's labeled part apart from the decision time, and returns Reading.frame. arbit-model declares polars (already an arbit-data dependency; uv.lock +2 lines). Audit script uses columnar placement. Docs: ADR-007 A5 (OWN-072), ENG-054, R-071 resolved, research note section with measurements, README, plan, status, changelog.

Files: libs/arbit-model/src/arbit_model/timing.py, libs/arbit-model/src/arbit_model/vintages.py, libs/arbit-model/src/arbit_model/point_in_time.py, libs/arbit-model/tests/test_point_in_time.py, tests/integration/test_model_point_in_time.py, scripts/model/point_in_time_audit.py, libs/arbit-model/pyproject.toml, uv.lock, docs/research/point-in-time-audit-columnar-2026-11-23.json

## Validate

make runtime-check passed (ruff, mypy, contracts, 1,366 tests). Governance checks foundation, model-tests and point-in-time exited 0. Three deliberate breaks fail 1, 9 and 6 reader tests as before. The real-history audit (read-only) reproduces every figure of the first receipt with 0 rows known at or after a decision. Season benchmark 630 reads in 1.5 s. Not exercised: any feature, backtest or service.

Files: docs/research/point-in-time-audit-columnar-2026-11-23.json, libs/arbit-model/tests/test_point_in_time.py

## Document

ADR-007 owner clarification A5 (OWN-072); decision register OWN-072 and ENG-054; R-071 resolved; research note section 'Columnar reader' with the local-data measurements and before/after table; Model README; M3 plan slice 3 follow-ups; status and changelog (PR #4 merged under the owner's GitHub authorization).

Files: docs/architecture/decisions/007-model-availability.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/research/point-in-time-audit-2026-11-23.md, libs/arbit-model/README.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-23T19:30:02Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=6659121ee9879564a34bff4e7b2b6a6270f97e9b7e9f1fb22fbe2b265354dd73
- `model-tests`: exit=0, 2026-11-23T19:30:05Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=188b130731680fe061b3d7084e904710dbed26d269657d2191a3841c4d56147b
- `point-in-time`: exit=0, 2026-11-23T19:30:07Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=b974209b29e2efbf8d77efbe4acf09c19d0c89f4945c3960a0458bc28246e3d0

## Findings / decisions / contradictions

- 2026-11-23T19:30:17Z [observation] Columnar reader reproduces every figure of the 2026-11-23 audit receipt (0 differences across versions, gaps, units, bases, bounds, untimed units and latest known-from at all four decision times); audit 8.8 s / 0.83 GB vs 34 s / 2.2 GB; a 2025 season of 126 kickoffs x 5 tables = 630 reads in 1.5 s (2.4 ms/read), 0.4 GB. — docs/research/point-in-time-audit-columnar-2026-11-23.json; docs/research/point-in-time-audit-2026-11-23.md
- 2026-11-23T19:30:17Z [observation] Test sensitivity unchanged on the columnar code: no gap bound fails 1, admitting every fetched unit fails 9, ignoring gaps fails 6; source restored byte-identical. — libs/arbit-model/tests/test_point_in_time.py

## Remaining unresolved / blocked

No feature, backtest or service uses the reader yet. R-070 (injury files from 2025 lack date_modified) is addressed by TASK-003's precedence for 2026, not for earlier seasons. The ENG-053 rules the ADR left open remain labeled and revisable by the owner.

## Next executable action

TASK-20261123-003 on the same branch: game-day availability with the owner's precedence (OWN-073): ESPN fantasy status read within 15 minutes of kickoff is final; otherwise Arbit's latest NFL injury report capture; otherwise nflverse injuries through the point-in-time reader; otherwise unknown. Then PR, merge, and M3 slice 3b.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
