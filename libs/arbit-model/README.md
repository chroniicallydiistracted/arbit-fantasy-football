# Arbit Model

The shared Model ([ADR-003](../../docs/architecture/decisions/003-shared-intelligence.md), [ADR-006](../../docs/architecture/decisions/006-model-architecture.md)). It is built only from nflverse data (OWN-061) and is judged in FFA points scored by `arbit_core.scoring`.

Implemented (M3 slice 2):
- `arbit_model.fields`: one recorded use for every imported nflverse field, and the committed catalog `nflverse_fields.json`. `scripts/model/field_catalog.py` checks it against the imported manifests or regenerates it.
- `arbit_model.targets`: FFA lines and points for every player-game and D/ST team-game, plus participation labels. These are pure functions over nflverse rows.
- `arbit_model.inputs`: read-only access to nflverse tables, current or pinned to exact manifests.
- `arbit_model.storage`: Parquet tables and manifests in a content-addressed store.

Implemented (M3 slice 3a, ENG-053; columnar since ENG-054):
- `arbit_model.point_in_time`: the only way feature code reads nflverse. `PointInTime.read(key, columns, at)` returns a polars frame (`Reading.frame`) of the rows known before decision time `at`, with held data first (A5, OWN-072), under [ADR-007](../../docs/architecture/decisions/007-model-availability.md) as amended (OWN-066). Each row carries `_known_from` and `_basis` (`observed`, `source-timestamp` or `retrospective-rule`), and each reading carries a lineage record. Fields excluded by policy are refused unless their gate is named.
- `arbit_model.timing`: the kickoff calendar, known-from rules by family, and the registry of readable tables with their units. A table without an entry is refused.
- `arbit_model.vintages`: Arbit's versions and reads of each file, and its capture gaps (A3).

`scripts/model/point_in_time_audit.py` checks the reader against the real history ([audit](../../docs/research/point-in-time-audit-2026-11-23.md)).

`scripts/model/build_targets.py` builds the historical targets. Features, projections, rankings and advisor policies come in later slices ([M3 plan](../../docs/superpowers/plans/2026-11-09-m3-model.md)); no model has been trained.
