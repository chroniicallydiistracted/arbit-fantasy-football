"""One NFL injury report capture (OWN-063): the original bytes, a parsed table, and when it was
read.

A capture's `observedAt` is when its reads finished, the time its values count as known to the
Model (ADR-007). Captures are content-addressed and add-only; `captures.jsonl` lists them in order.
"""

import io
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_core.identity import require_aware

from arbit_data.availability.sources import (
    GameStatus,
    JsonGetter,
    Response,
    game_statuses,
    read_injury_report,
)
from arbit_data.errors import SourceError
from arbit_data.nflverse.objects import ObjectStore

FORMAT = "arbit-nfl-availability-v1"
INDEX = "captures.jsonl"
REQUIRED = ("nfl.week", "nfl.injuries")

GAME_STATUS_SCHEMA = pa.schema(
    [
        ("season", pa.int16()),
        ("season_type", pa.string()),
        ("week", pa.int16()),
        ("team_name", pa.string()),
        ("nfl_team_id", pa.string()),
        ("gsis_id", pa.string()),
        ("nfl_person_id", pa.string()),
        ("name", pa.string()),
        ("position", pa.string()),
        ("game_status", pa.string()),
        ("practice_status", pa.string()),
        ("practice_days", pa.list_(pa.list_(pa.string()))),
        ("injuries", pa.list_(pa.string())),
    ]
)
assert [f.name for f in fields(GameStatus)] == GAME_STATUS_SCHEMA.names


@dataclass(frozen=True)
class Capture:
    manifest: str
    observed_at: datetime
    week: tuple[int, str, int] | None
    counts: dict[str, int]
    errors: dict[str, str]


def current_week(nfl: JsonGetter, now: datetime) -> tuple[int, str, int]:
    """NFL's season, season type and week for the day of `now` (UTC)."""
    body, _ = nfl.get(f"/football/v2/weeks/date/{now.astimezone(UTC).date().isoformat()}")
    try:
        return int(body["season"]), str(body.get("seasonType") or "REG"), int(body["week"])
    except (KeyError, TypeError, ValueError):
        raise SourceError("NFL_WEEK_SHAPE") from None


def _parquet(rows: list[GameStatus]) -> bytes:
    table = pa.Table.from_pylist([asdict(r) for r in rows], schema=GAME_STATUS_SCHEMA)
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="zstd")
    return buffer.getvalue()


def _append_index(root: Path, entry: dict[str, Any]) -> None:
    line = (json.dumps(entry, sort_keys=True) + "\n").encode()
    descriptor = os.open(root / INDEX, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def capture(
    nfl: JsonGetter,
    root: Path,
    *,
    season: int,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Capture:
    """Read the season's injury report. It counts as known from when the reads finished, never
    from when they started. A failure is recorded in `errors` and the capture is still kept."""
    now = clock()
    require_aware(now)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = ObjectStore(root / "objects")
    responses: list[Response] = []
    errors: dict[str, str] = {}
    statuses: list[GameStatus] = []
    week: tuple[int, str, int] | None = None
    try:
        week = current_week(nfl, now)
    except SourceError as error:
        errors["nfl.week"] = error.code
    season_type = week[1] if week and week[0] == season else "REG"
    try:
        rows, pages = read_injury_report(nfl, season, season_type)
        responses += pages
        statuses = game_statuses(rows)
    except SourceError as error:
        errors["nfl.injuries"] = error.code
    sources = []
    for response in responses:
        ref = store.write((response.body,), expected_size=len(response.body))
        sources.append(
            {
                "source": response.source,
                "path": response.path,
                "params": response.params,
                "sha256": ref.sha256,
                "bytes": ref.size,
            }
        )
    data = _parquet(statuses)
    table = store.write((data,), expected_size=len(data)).sha256
    counts = {
        "gameStatusRows": len(statuses),
        "gameStatusOut": sum(s.game_status == "OUT" for s in statuses),
        "responses": len(responses),
    }
    observed = clock().astimezone(UTC)
    manifest = {
        "format": FORMAT,
        "startedAt": now.astimezone(UTC).isoformat(),
        "observedAt": observed.isoformat(),
        "season": season,
        "week": list(week) if week else None,
        "sources": sources,
        "tables": {"gameStatus": {"parquet": table}},
        "counts": counts,
        "errors": errors,
    }
    digest = store.put_json(manifest).sha256
    _append_index(
        root,
        {"observedAt": observed.isoformat(), "manifest": digest, "week": manifest["week"]}
        | {"errors": sorted(errors)},
    )
    return Capture(digest, observed, week, counts, errors)
