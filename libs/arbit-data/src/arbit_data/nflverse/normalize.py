"""Lossless columnar acquisition profiles; source scopes and unknown values stay explicit."""

import csv
import gzip
import io
import json
import os
import subprocess
import sys
import tempfile
import zlib
from collections.abc import Iterator
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.csv as pacsv  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from arbit_data.contracts import DataModel
from arbit_data.league import content_hash
from arbit_data.nflverse.catalog import Asset
from arbit_data.nflverse.objects import ObjectRef, ObjectStore

MAX_ROWS = 5_000_000
MAX_UNCOMPRESSED = 2 * 1024**3


class NormalizedDataset(DataModel):
    raw_hash: str
    parquet_hash: str | None
    row_count: int
    schema_hash: str
    columns: list[dict[str, Any]]
    coverage: dict[str, Any]
    missing: dict[str, int]
    status: Literal["validated", "archive_only"]
    limitations: list[str]


class _Bounded(io.RawIOBase):
    def __init__(self, source: Any):
        self.source, self.count = source, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        data = self.source.read(len(buffer))
        self.count += len(data)
        if self.count > MAX_UNCOMPRESSED:
            raise ValueError("SOURCE_EXPANSION_LIMIT")
        buffer[: len(data)] = data
        return len(data)

    def close(self) -> None:
        self.source.close()
        super().close()


def _required(asset: Asset) -> set[str]:
    if asset.family == "pbp":
        return {"game_id", "play_id", "season", "week"}
    if asset.family == "stats_player":
        return {"player_id", "season", "season_type"} | (
            {"week"} if "_week_" in asset.filename else set()
        )
    if asset.family == "stats_team":
        return {"team", "season", "season_type"} | (
            {"week"} if "_week_" in asset.filename else set()
        )
    if asset.family == "players":
        return {"gsis_id", "espn_id"}
    if asset.family == "teams":
        return {"team_abbr", "team_id"}
    if asset.family == "schedules":
        return {"game_id", "season", "week", "game_type"}
    if asset.family == "depth_charts" and any(
        str(year) in asset.filename for year in range(2025, 2101)
    ):
        return {"dt", "team", "espn_id"}
    return set()


def _convert(asset: Asset, raw: ObjectRef, target: Path) -> None:
    if asset.format == "rds":
        try:
            outcome = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "arbit_data.nflverse.rds_decode",
                    str(raw.path),
                    str(target),
                ],
                env={**os.environ, "POLARS_MAX_THREADS": "2", "OPENBLAS_NUM_THREADS": "1"},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=90,
                check=False,
            )
            if outcome.returncode or not target.exists():
                raise ValueError("RDS_DECODE_FAILED")
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError("RDS_DECODE_FAILED") from None
        return
    opener = gzip.open if asset.format == "csv.gz" else open
    with opener(raw.path, "rt", encoding="utf-8-sig", newline="") as text:
        header = next(csv.reader(text))
    if not header or len(header) > 1024 or len(set(header)) != len(header):
        raise ValueError("INVALID_COLUMNS")
    source = opener(raw.path, "rb")
    with io.BufferedReader(_Bounded(source)) as bounded:
        reader = pacsv.open_csv(
            bounded,
            read_options=pacsv.ReadOptions(block_size=1024 * 1024),
            convert_options=pacsv.ConvertOptions(
                column_types={name: pa.string() for name in header},
                strings_can_be_null=True,
                quoted_strings_can_be_null=False,
                null_values=["", "NA", "NaN", "NULL"],
            ),
        )
        with pq.ParquetWriter(target, reader.schema, compression="zstd") as writer:
            rows = 0
            for batch in reader:
                rows += batch.num_rows
                if rows > MAX_ROWS:
                    raise ValueError("ROW_LIMIT")
                writer.write_batch(batch)
    os.chmod(target, 0o600)


def normalize(asset: Asset, raw: ObjectRef, store: ObjectStore) -> NormalizedDataset:
    store.verify(raw.sha256)
    limits = [
        "Local observation is the conservative availability cutoff; historical row publication is not established.",
        "Source fantasy points, rankings and expected points are not FFA-scored recommendations.",
    ]
    if asset.usage == "metadata" or asset.format not in ("parquet", "csv", "csv.gz", "rds"):
        return NormalizedDataset(
            raw_hash=raw.sha256,
            parquet_hash=None,
            row_count=0,
            schema_hash=content_hash([]),
            columns=[],
            coverage={},
            missing={},
            status="archive_only",
            limitations=limits
            + ["Metadata or opaque artifact preserved as original bytes; not a statistical table."],
        )
    with tempfile.TemporaryDirectory(prefix="arbit-columnar-") as temporary:
        path = raw.path
        if asset.format != "parquet":
            path = Path(temporary) / "table.parquet"
            try:
                _convert(asset, raw, path)
            except (
                pa.ArrowException,
                zlib.error,
                ValueError,
                OSError,
                StopIteration,
                csv.Error,
                UnicodeError,
                EOFError,
            ) as error:
                code = (
                    str(error)
                    if isinstance(error, ValueError)
                    and str(error).startswith(("RDS_", "ROW_", "SOURCE_", "INVALID_"))
                    else "TABULAR_DECODE_FAILED"
                )
                raise ValueError(code) from None
        try:
            reader = pq.ParquetFile(path)
            schema = reader.schema_arrow
            names = schema.names
            if len(names) > 1024 or len(set(names)) != len(names):
                raise ValueError("INVALID_COLUMNS")
            if not _required(asset) <= set(names):
                raise ValueError("REQUIRED_COLUMNS_MISSING")
            if reader.metadata.num_rows > MAX_ROWS:
                raise ValueError("ROW_LIMIT")
            columns = [
                {"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema
            ]
            missing = {name: 0 for name in names}
            sets: dict[str, set[str]] = {
                name: set()
                for name in ("season", "season_type", "game_type", "week")
                if name in names
            }
            times: dict[str, list[str]] = {
                name: [] for name in ("dt", "date", "report_date", "gameday") if name in names
            }
            key_columns = [
                name
                for name in (
                    ("game_id", "play_id")
                    if asset.family == "pbp"
                    else ("gsis_id",)
                    if asset.family == "players"
                    else ("team_abbr",)
                    if asset.family == "teams"
                    else ("game_id",)
                    if asset.family == "schedules"
                    else ("player_id", "season", "season_type", "week", "team", "game_id")
                    if asset.family == "stats_player"
                    else ("team", "season", "season_type", "week")
                    if asset.family == "stats_team"
                    else ()
                )
                if name in names
            ]
            seen: set[tuple[Any, ...]] = set()
            absent, duplicates = 0, 0
            for batch in reader.iter_batches(batch_size=16384):
                if key_columns:
                    key_values = [
                        batch.column(names.index(name)).to_pylist() for name in key_columns
                    ]
                    for key in zip(*key_values, strict=True):
                        if any(value is None for value in key):
                            absent += 1
                        elif key in seen:
                            duplicates += 1
                        else:
                            seen.add(key)
                for i, name in enumerate(names):
                    missing[name] += batch.column(i).null_count
                for name, values in sets.items():
                    values.update(
                        str(x) for x in batch.column(names.index(name)).to_pylist() if x is not None
                    )
                    if len(values) > 512:
                        raise ValueError("INVALID_COVERAGE_SCOPE")
                for name, ranges in times.items():
                    observed = [
                        str(x) for x in batch.column(names.index(name)).to_pylist() if x is not None
                    ]
                    if observed:
                        ranges[:] = [min(ranges + observed), max(ranges + observed)]
            coverage: dict[str, Any] = {
                "key_columns": key_columns,
                "rows_missing_keys": absent,
                "duplicate_keys": duplicates,
            }
            if schema.metadata and b"arbit:nested_json_columns" in schema.metadata:
                coverage["nested_json_columns"] = json.loads(
                    schema.metadata[b"arbit:nested_json_columns"]
                )
                limits.append(
                    "Nested R history columns are explicit JSON strings preserving inner columns, types, indices and rows; original R bytes remain authoritative."
                )
            for name, values in sets.items():
                label = {
                    "season": "seasons",
                    "season_type": "season_types",
                    "game_type": "game_types",
                    "week": "weeks",
                }[name]
                try:
                    coverage[label] = (
                        sorted(_scope_integer(v) for v in values)
                        if name in ("season", "week")
                        else sorted(values)
                    )
                except ValueError:
                    raise ValueError("INVALID_COVERAGE_SCOPE") from None
            for name, ranges in times.items():
                if ranges:
                    coverage[name + "_range"] = ranges
            if asset.family == "depth_charts":
                limits.append(asset.availability_note)
            if asset.family == "pbp_participation":
                limits.append(asset.availability_note)
            normalized = raw if asset.format == "parquet" else store.write(iter_file(path))
            return NormalizedDataset(
                raw_hash=raw.sha256,
                parquet_hash=normalized.sha256,
                row_count=reader.metadata.num_rows,
                schema_hash=content_hash(columns),
                columns=columns,
                coverage=coverage,
                missing=missing,
                status="validated",
                limitations=limits,
            )
        except pa.ArrowException:
            raise ValueError("TABULAR_DECODE_FAILED") from None


def iter_file(path: Path) -> Iterator[bytes]:
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            yield chunk


def _scope_integer(value: str) -> int:
    try:
        number = Decimal(value)
        if (
            not number.is_finite()
            or not 0 <= number <= 2100
            or number != number.to_integral_value()
        ):
            raise ValueError("INVALID_COVERAGE_SCOPE")
        return int(number)
    except DecimalException:
        raise ValueError("INVALID_COVERAGE_SCOPE") from None
