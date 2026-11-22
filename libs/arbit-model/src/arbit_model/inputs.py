"""Read nflverse tables for the Model, current or pinned to exact manifests; never writes."""

from collections.abc import Mapping, Sequence
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_data.db import UnitOfWork
from arbit_data.league import content_hash
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.nflverse.repository import get_dataset
from arbit_data.schema import dataset_manifest
from sqlalchemy import select

PREFIX = "nflverse/nflverse-data/"


class NflverseTables:
    """Tables by short key (`pbp/play_by_play_2025`). A pinned key reads exactly that manifest;
    others read the current one. Every manifest read is recorded for the output's lineage."""

    def __init__(
        self, uow: UnitOfWork, store: ObjectStore, pins: Mapping[str, str] | None = None
    ) -> None:
        self.uow, self.store, self.pins = uow, store, dict(pins or {})
        self.manifests: dict[str, str] = {}

    def manifest(self, key: str) -> dict[str, Any] | None:
        pinned = self.pins.get(key)
        if pinned is None:
            return get_dataset(self.uow, PREFIX + key)
        with self.uow.engine.connect() as c:
            payload = c.scalar(
                select(dataset_manifest.c.payload).where(
                    dataset_manifest.c.hash == pinned,
                    dataset_manifest.c.logical_key == PREFIX + key,
                )
            )
        if payload is None or content_hash(payload) != pinned:
            raise ValueError(f"PINNED_MANIFEST_UNAVAILABLE: {key}")
        return {"manifest_hash": pinned, **payload}

    def read(self, key: str, columns: Sequence[str] | None = None) -> list[dict[str, Any]]:
        manifest = self.manifest(key)
        if manifest is None or manifest.get("parquet_hash") is None:
            raise LookupError(f"DATASET_UNAVAILABLE: {key}")
        self.manifests[key] = str(manifest["manifest_hash"])
        path = self.store.verify(str(manifest["parquet_hash"])).path
        rows: list[dict[str, Any]] = pq.read_table(
            path, columns=list(columns) if columns else None
        ).to_pylist()
        return rows

    def optional(self, key: str, columns: Sequence[str] | None = None) -> list[dict[str, Any]]:
        """Rows of a table that may not exist for this season (snap counts before 2013)."""
        try:
            return self.read(key, columns)
        except LookupError:
            return []
