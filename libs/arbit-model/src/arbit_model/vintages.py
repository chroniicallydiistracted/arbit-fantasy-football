"""Arbit's own record of reading each nflverse file (ADR-007 decision 3, amendment A3).

Every daily statistics run registers a new catalog and records one check per file in
`dataset_import`: `published` when the file changed (a new manifest) and `unchanged` when it did
not. Those checks, with each manifest's `observed_at`, are the reads. A gap is any span between
consecutive reads longer than the family's stale window; before the first read, everything is
unobserved. Catch-up runs import through the same path, so their reads are already here.
"""

from bisect import bisect_left
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

import polars as pl
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_data.db import UnitOfWork
from arbit_data.freshness import STATISTICS_STALE_SECONDS
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import dataset_import, dataset_manifest
from sqlalchemy import select

from arbit_model.timing import PREFIX, short_key

NFLVERSE_STALE = timedelta(seconds=STATISTICS_STALE_SECONDS)
SUCCESSFUL = ("published", "unchanged")


@dataclass(frozen=True)
class Version:
    manifest: str
    parquet: str
    observed_at: datetime


@dataclass(frozen=True)
class Gap:
    """No successful read between `start` (None: before the first read) and `end`."""

    start: datetime | None
    end: datetime


@dataclass(frozen=True)
class KeyHistory:
    key: str
    versions: tuple[Version, ...]  # by observed_at
    reads: tuple[datetime, ...]  # successful reads, ascending
    stale: timedelta = NFLVERSE_STALE

    def __post_init__(self) -> None:
        if list(self.versions) != sorted(self.versions, key=lambda v: v.observed_at):
            raise ValueError("VERSIONS_NOT_ORDERED")
        if list(self.reads) != sorted(self.reads):
            raise ValueError("READS_NOT_ORDERED")

    def current(self, at: datetime) -> int | None:
        """Index of the version Arbit held just before `at`."""
        index = bisect_left([v.observed_at for v in self.versions], at) - 1
        return index if index >= 0 else None

    def read_before(self, at: datetime) -> datetime | None:
        index = bisect_left(self.reads, at) - 1
        return self.reads[index] if index >= 0 else None

    def read_from(self, at: datetime) -> datetime | None:
        index = bisect_left(self.reads, at)
        return self.reads[index] if index < len(self.reads) else None

    def gaps(self) -> list[Gap]:
        if not self.reads:
            return []
        found = [Gap(None, self.reads[0])]
        for before, after in zip(self.reads, self.reads[1:], strict=False):
            if after - before > self.stale:
                found.append(Gap(before, after))
        return found


class VintageSource(Protocol):
    def history(self, key: str) -> KeyHistory: ...

    def table(self, version: Version, columns: Sequence[str]) -> pl.DataFrame:
        """One version's rows with these columns, in file order; a missing column is null."""
        ...


class StoredVintages:
    """Versions and reads from the database; tables from the content-addressed store. Read only.
    Recently read tables are cached; a daily file can hold hundreds of thousands of rows."""

    def __init__(self, uow: UnitOfWork, store: ObjectStore, *, cached_tables: int = 4) -> None:
        self.uow, self.store, self.cached_tables = uow, store, cached_tables
        self._histories: dict[str, KeyHistory] = {}
        self._tables: OrderedDict[tuple[str, tuple[str, ...]], pl.DataFrame] = OrderedDict()

    def history(self, key: str) -> KeyHistory:
        short = short_key(key)
        if short in self._histories:
            return self._histories[short]
        logical = PREFIX + short
        with self.uow.engine.connect() as c:
            manifests = c.execute(
                select(
                    dataset_manifest.c.hash,
                    dataset_manifest.c.parquet_hash,
                    dataset_manifest.c.observed_at,
                )
                .where(
                    dataset_manifest.c.logical_key == logical,
                    dataset_manifest.c.parquet_hash.is_not(None),
                )
                .order_by(dataset_manifest.c.observed_at)
            ).all()
            checks: list[datetime] = list(
                c.execute(
                    select(dataset_import.c.checked_at).where(
                        dataset_import.c.logical_key == logical,
                        dataset_import.c.status.in_(SUCCESSFUL),
                    )
                ).scalars()
            )
            reads = sorted({*checks, *(m.observed_at for m in manifests)})
        history = KeyHistory(
            short,
            tuple(Version(m.hash, m.parquet_hash, m.observed_at) for m in manifests),
            tuple(reads),
        )
        self._histories[short] = history
        return history

    def table(self, version: Version, columns: Sequence[str]) -> pl.DataFrame:
        wanted = tuple(dict.fromkeys(columns))
        cached = self._tables.get((version.parquet, wanted))
        if cached is not None:
            self._tables.move_to_end((version.parquet, wanted))
            return cached
        path = self.store.verify(version.parquet).path
        present = set(pq.read_schema(path).names)
        readable = [c for c in wanted if c in present]
        if readable:
            frame = pl.read_parquet(path, columns=readable)
            frame = frame.with_columns(pl.lit(None).alias(c) for c in wanted if c not in present)
        else:
            height = pq.read_metadata(path).num_rows
            frame = pl.DataFrame({c: [None] * height for c in wanted})
        frame = frame.select(wanted)
        self._tables[(version.parquet, wanted)] = frame
        while len(self._tables) > self.cached_tables:
            self._tables.popitem(last=False)
        return frame
