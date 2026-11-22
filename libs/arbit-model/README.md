# Arbit Model

The shared Model ([ADR-003](../../docs/architecture/decisions/003-shared-intelligence.md), [ADR-006](../../docs/architecture/decisions/006-model-architecture.md)). It is built only from nflverse data (OWN-061) and is judged in FFA points scored by `arbit_core.scoring`.

Implemented (M3 slice 2):
- `arbit_model.fields`: one recorded use for every imported nflverse field, and the committed catalog `nflverse_fields.json`. `scripts/model/field_catalog.py` checks it against the imported manifests or regenerates it.
- `arbit_model.targets`: FFA lines and points for every player-game and D/ST team-game, plus participation labels. These are pure functions over nflverse rows.
- `arbit_model.inputs`: read-only access to nflverse tables, current or pinned to exact manifests.
- `arbit_model.storage`: Parquet tables and manifests in a content-addressed store.

`scripts/model/build_targets.py` builds the historical targets. Features, projections, rankings and advisor policies come in later slices ([M3 plan](../../docs/superpowers/plans/2026-11-09-m3-model.md)); no model has been trained.
