# Arbit Model

The shared Model ([ADR-003](../../docs/architecture/decisions/003-shared-intelligence.md), [ADR-006](../../docs/architecture/decisions/006-model-architecture.md)). It is built only from nflverse data (OWN-061) and is judged in FFA points scored by `arbit_core.scoring`.

Implemented (M3 slice 2):
- `arbit_model.fields`: one recorded use for every imported nflverse field, and the committed catalog `nflverse_fields.json`. `scripts/model/field_catalog.py` checks it against the imported manifests or regenerates it.
- `arbit_model.targets`: FFA lines and points for every player-game and D/ST team-game, plus participation labels. These are pure functions over nflverse rows.
- `arbit_model.teams`: one code per franchise across nflverse tables (R-072). The schedule, snap counts and rosters keep old codes (OAK, SD, STL, and roster-only codes for 2012–2015), while statistics use franchise codes. Every join maps through it, and the targets refuse a row whose team didn't play in its game.
- `arbit_model.inputs`: read-only access to nflverse tables, current or pinned to exact manifests.
- `arbit_model.storage`: Parquet tables and manifests in a content-addressed store.

Implemented (M3 slice 3a, ENG-053; columnar since ENG-054):
- `arbit_model.point_in_time`: the only way feature code reads nflverse. `PointInTime.read(key, columns, at)` returns a polars frame (`Reading.frame`) of the rows known before decision time `at`, with held data first (A5, OWN-072), under [ADR-007](../../docs/architecture/decisions/007-model-availability.md) as amended (OWN-066). Each row carries `_known_from` and `_basis` (`observed`, `source-timestamp` or `retrospective-rule`), and each reading carries a lineage record. Fields excluded by policy are refused unless their gate is named.
- `arbit_model.timing`: the kickoff calendar, known-from rules by family, and the registry of readable tables with their units. A table without an entry is refused.
- `arbit_model.vintages`: Arbit's versions and reads of each file, and its capture gaps (A3).
- `arbit_model.availability`: each player's availability at a decision time in the owner's order (OWN-073, ENG-055). On game day ESPN's current status is final; otherwise the freshest copy of NFL's injury report, Arbit's capture or nflverse's; otherwise unknown.

Implemented (M3 slice 3b, ENG-056):
- `arbit_model.gamebook`: completed games known at a decision time, with FFA points by position and by D/ST from the shared scorer, cached per game version.
- `arbit_model.team_features`: one row per team per game. It covers team rates, the opponent's defense, defense against the position (raw and adjusted for the offenses faced), D/ST points allowed by the opponent's offense, and pre-game context.
- `arbit_model.feature_specs`: each feature's definition, unit, window, cutoff, sources and measured shrinkage constant.

Research (M3-3 defense against the position, ENG-057; [runbook](../../docs/research/dvp/README.md)):
- `arbit_model.dvp.provenance`: the lineage allowlist every DvP input passes; it fails closed and forbids provider projections by lineage, not name.
- `arbit_model.dvp.observations`: completed-game team-game-position cells from the canonical FFA actuals, with schedule-decided opponents and missing kept missing.
- `arbit_model.dvp.asof`: preweek and per-game cutoffs, feature views apart from labels, a frozen-forecast evaluation join.
- `arbit_model.dvp.reliability` and `results`: v0's split-half arithmetic with intervals, and experiment records a projection dependency invalidates.
- `arbit_model.dvp.lab` and `svg`: the Phase 2 reliability lab (ENG-059): adjustments, split methods, method-of-moments and REML variance components, lag and carryover, permutation nulls, cluster bootstraps, and deterministic SVG plots.
- `arbit_model.dvp.walkforward`: the Phase 3 walk-forward (ENG-060). Fold parameters come from earlier seasons, forecasts from rows available by the cutoff; B00 and the DvP variants; frozen forecasts, block-bootstrap metrics.
- `scripts/model/dvp.py`: `audit`, `reproduce-v0`, `reliability`, `backtest`, `report`, `registry`.

`scripts/model/point_in_time_audit.py` checks the reader against the real history ([audit](../../docs/research/point-in-time-audit-2026-11-23.md)).

`scripts/model/build_targets.py` builds the historical targets. Features, projections, rankings and advisor policies come in later slices ([M3 plan](../../docs/superpowers/plans/2026-11-09-m3-model.md)); no model has been trained.
