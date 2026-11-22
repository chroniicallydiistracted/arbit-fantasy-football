"""When each week of the current season first appeared in each nflverse file (ADR-007 evidence).

Every daily import keeps its manifest, so the first version containing a week bounds when nflverse
published it, to within the import cadence. Read-only against the database and the nflverse
object store; writes a JSON receipt.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/nflverse_vintages.py 2026 docs/research/nflverse-vintages-2026-11-10.json
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import dataset_manifest
from sqlalchemy import create_engine, select

PREFIX = "nflverse/nflverse-data/"
SEASON_FILES = (
    "pbp/play_by_play_{s}",
    "stats_player/stats_player_week_{s}",
    "stats_team/stats_team_week_{s}",
    "snap_counts/snap_counts_{s}",
    "pfr_advstats/advstats_week_pass_{s}",
    "pfr_advstats/advstats_week_rec_{s}",
    "ftn_charting/ftn_charting_{s}",
    "injuries/injuries_{s}",
    "weekly_rosters/roster_weekly_{s}",
    "depth_charts/depth_charts_{s}",
    "rosters/roster_{s}",
)
# Next Gen Stats has no per-season file after 2024; the combined file carries every season.
SHARED_FILES = (
    "schedules/games",
    "nextgen_stats/ngs_passing",
    "espn_data/qbr_week_level",
    "officials/officials",
)


def describe(key: str, table: Any, season: int) -> dict[str, Any]:
    names = table.column_names
    if "season" in names and key in SHARED_FILES:
        seasons = pc.cast(table.column("season"), "int64", safe=False)
        table = table.filter(pc.equal(seasons, season))
    info: dict[str, Any] = {"rows": table.num_rows}
    for column in ("week", "game_week", "week_num"):
        if column in names and table.num_rows:
            info["maxWeek"] = pc.max(pc.cast(table.column(column), "int64", safe=False)).as_py()
            break
    for column in ("game_id", "nflverse_game_id"):
        if column in names:
            info["games"] = len(set(table.column(column).to_pylist()))
            break
    if "date_modified" in names:
        info["maxModified"] = str(pc.max(table.column("date_modified")).as_py())
    if "dt" in names:
        info["maxDt"] = str(pc.max(table.column("dt")).as_py())
    if key == "schedules/games":
        scored = table.filter(pc.is_valid(table.column("home_score")))
        with_qb = table.filter(pc.is_valid(table.column("home_qb_id")))
        info["scoredGames"] = scored.num_rows
        info["maxWeekScored"] = pc.max(scored.column("week")).as_py()
        info["maxWeekWithExpectedQb"] = pc.max(with_qb.column("week")).as_py()
    if key.startswith("weekly_rosters/") and "maxWeek" in info:
        latest = table.filter(pc.equal(table.column("week"), info["maxWeek"]))
        inactive = pc.equal(latest.column("status"), "INA")
        info["latestWeekInactive"] = pc.sum(pc.cast(inactive, "int64")).as_py()
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("season", type=int)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    engine = create_engine(os.environ["ARBIT_DATABASE_URL"], hide_parameters=True)
    store = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    keys = [k.format(s=arguments.season) for k in SEASON_FILES] + list(SHARED_FILES)
    with engine.connect() as c:
        rows = c.execute(
            select(
                dataset_manifest.c.logical_key,
                dataset_manifest.c.hash,
                dataset_manifest.c.observed_at,
                dataset_manifest.c.payload["parquet_hash"].as_string(),
            )
            .where(dataset_manifest.c.logical_key.in_([PREFIX + k for k in keys]))
            .order_by(dataset_manifest.c.logical_key, dataset_manifest.c.observed_at)
        ).all()
    versions: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    for logical_key, manifest, observed, parquet in rows:
        if parquet is None:
            continue
        key = str(logical_key).removeprefix(PREFIX)
        table = pq.read_table(store.verify(str(parquet)).path)
        versions[key].append(
            {"observedAt": datetime.fromisoformat(str(observed)).astimezone(UTC).isoformat()}
            | {"manifest": str(manifest)}
            | describe(key, table, arguments.season)
        )
    report = {
        "season": arguments.season,
        "generatedAt": datetime.now(UTC).isoformat(),
        "note": "Each entry is a manifest version the worker imported; the first version holding "
        "a week bounds its publication to within the import cadence (24 hours).",
        "files": versions,
    }
    arguments.output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    for key, found in versions.items():
        print(key, len(found), "versions")


if __name__ == "__main__":
    main()
