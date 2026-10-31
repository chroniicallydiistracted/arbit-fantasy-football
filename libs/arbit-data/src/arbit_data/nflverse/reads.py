"""Stored coverage and canonical athlete statistics; no provider network or fantasy arithmetic."""

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from sqlalchemy import or_, select

from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.nflverse.repository import get_dataset
from arbit_data.schema import (
    dataset_current,
    dataset_import,
    dataset_manifest,
    entity_alias,
    identity_import,
)


def coverage(uow: UnitOfWork) -> dict[str, Any]:
    with uow.engine.connect() as c:
        rows = (
            c.execute(
                select(dataset_manifest.c.family, dataset_manifest.c.payload).join(
                    dataset_current, dataset_current.c.manifest_hash == dataset_manifest.c.hash
                )
            )
            .mappings()
            .all()
        )
        statuses: list[str] = list(c.execute(select(dataset_import.c.status)).scalars().all())
        identities: list[dict[str, Any]] = list(
            c.execute(select(identity_import.c.payload)).scalars().all()
        )
    families: dict[str, dict[str, Any]] = {}
    for row in rows:
        m = row["payload"]
        family = row["family"]
        item = families.setdefault(
            family,
            {
                "files": 0,
                "table_rows": 0,
                "seasons": set(),
                "usages": set(),
                "archive_only": 0,
                "timestamped_depth": False,
            },
        )
        item["files"] += 1
        item["table_rows"] += m["row_count"]
        item["seasons"].update(m["coverage"].get("seasons", []))
        item["usages"].add(m["source"].get("usage", "unknown"))
        item["archive_only"] += m["status"] == "archive_only"
        item["timestamped_depth"] |= "dt_range" in m["coverage"]
    for item in families.values():
        item["seasons"] = sorted(item["seasons"])
        item["usages"] = sorted(item["usages"])
    return {
        "families": families,
        "import_statuses": {status: statuses.count(status) for status in set(statuses)},
        "identity_reports": identities,
        "recommendations_enabled": False,
        "limitations": [
            "Row counts are stored file rows across distinct source variants, not unique combined NFL events.",
            "As-of availability begins at local observation; current files do not prove historical publication.",
        ],
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, float):
        return str(value) if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_value(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    return str(value)


def player_stats(
    uow: UnitOfWork,
    store: ObjectStore,
    entity_id: UUID,
    season: int,
    *,
    week: int | None = None,
    cutoff: datetime | None = None,
) -> dict[str, Any]:
    if not 1999 <= season <= 2100 or week is not None and not 0 <= week <= 25:
        raise ValueError("INVALID_STAT_SCOPE")
    cutoff = cutoff or datetime.now(UTC)
    with uow.engine.connect() as c:
        ids: list[str] = list(
            c.execute(
                select(entity_alias.c.external_id).where(
                    entity_alias.c.provider == "gsis",
                    entity_alias.c.kind == "athlete",
                    entity_alias.c.entity_id == entity_id,
                    entity_alias.c.valid_from <= cutoff,
                    or_(entity_alias.c.valid_to.is_(None), entity_alias.c.valid_to > cutoff),
                )
            )
            .scalars()
            .all()
        )
    base = {
        "entity_id": str(entity_id),
        "season": season,
        "week": week,
        "recommendations_enabled": False,
        "stat_authority": "nflverse; source fantasy_points fields use upstream rules, not FFA rules",
        "rows": [],
    }
    if len(ids) != 1:
        return {**base, "status": "unresolved_identity"}
    key = f"nflverse/nflverse-data/stats_player/stats_player_week_{season}"
    manifest = get_dataset(uow, key, cutoff=cutoff)
    if manifest is None or manifest["parquet_hash"] is None:
        return {**base, "status": "dataset_unavailable_at_cutoff"}
    data = pq.ParquetFile(store.verify(manifest["parquet_hash"]).path)
    result = []
    for batch in data.iter_batches(batch_size=16384):
        matched = batch.filter(
            pc.equal(batch.column(batch.schema.get_field_index("player_id")), ids[0])
        )
        for row in matched.to_pylist():
            if week is None or str(row.get("week")) == str(week):
                result.append(_json_value(row))
    return {
        **base,
        "status": "available" if result else "no_observation",
        "manifest_hash": manifest["manifest_hash"],
        "observed_at": manifest["observed_at"],
        "gsis_id": ids[0],
        "rows": result,
        "limitations": manifest["limitations"],
    }
