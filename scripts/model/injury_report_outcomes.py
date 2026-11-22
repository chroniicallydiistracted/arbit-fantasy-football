"""What each final injury-report status turned into, and how the report changed day by day.

For the given weeks, joins nflverse's injury report (NFL's official report, republished) with the
weekly roster's game-day status and snap counts. It then walks every daily version Arbit imported
of the season's injury file to show when statuses appeared or changed. Read-only.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/injury_report_outcomes.py 2026 7 8 9
"""

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import dataset_manifest
from arbit_model.inputs import PREFIX, NflverseTables
from sqlalchemy import create_engine, select


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("season", type=int)
    parser.add_argument("weeks", type=int, nargs="+")
    arguments = parser.parse_args()
    season, weeks = arguments.season, set(arguments.weeks)
    engine = create_engine(os.environ["ARBIT_DATABASE_URL"], hide_parameters=True)
    store = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    tables = NflverseTables(UnitOfWork(engine), store)
    report = [r for r in tables.read(f"injuries/injuries_{season}") if r["week"] in weeks]
    roster = {
        (r["gsis_id"], r["week"]): r["status"]
        for r in tables.read(f"weekly_rosters/roster_weekly_{season}")
        if r["week"] in weeks
    }
    pfr = {
        r["gsis_id"]: r["pfr_id"]
        for r in tables.read("players/players", ["gsis_id", "pfr_id"])
        if r["pfr_id"]
    }
    snapped = {
        (r["pfr_player_id"], r["week"])
        for r in tables.read(f"snap_counts/snap_counts_{season}")
        if (r["offense_snaps"] or 0) + (r["defense_snaps"] or 0) + (r["st_snaps"] or 0) > 0
    }
    outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    for row in report:
        key = (row["gsis_id"], row["week"])
        status = roster.get(key, "no roster row")
        label = {"INA": "inactive", "ACT": "active"}.get(status, status)
        played = (pfr.get(row["gsis_id"]), row["week"]) in snapped
        outcomes[str(row["report_status"])][label + (", played" if played else ", no snap")] += 1
    on_report = {(r["gsis_id"], r["week"]): str(r["report_status"]) for r in report}
    inactive = [k for k, s in roster.items() if s == "INA"]
    result: dict[str, Any] = {
        "season": season,
        "weeks": sorted(weeks),
        "inputs": tables.manifests,
        "outcomeByFinalStatus": {k: dict(v.most_common()) for k, v in outcomes.items()},
        "inactivesByReportStatus": dict(
            Counter(on_report.get(k, "not on report") for k in inactive).most_common()
        ),
        "dailyVersions": [],
    }
    with engine.connect() as c:
        versions = c.execute(
            select(
                dataset_manifest.c.observed_at,
                dataset_manifest.c.payload["parquet_hash"].as_string(),
            )
            .where(dataset_manifest.c.logical_key == f"{PREFIX}injuries/injuries_{season}")
            .order_by(dataset_manifest.c.observed_at)
        ).all()
    latest = max(weeks)
    previous: dict[tuple[str, int], str] = {}
    for observed, digest in versions:
        rows = pq.read_table(
            store.verify(str(digest)).path, columns=["gsis_id", "week", "report_status"]
        ).to_pylist()
        now = {(r["gsis_id"], r["week"]): str(r["report_status"]) for r in rows}
        now = {k: v for k, v in now.items() if k[1] == latest}
        changes = Counter(
            f"{previous[k]} -> {now[k]}" for k in set(now) & set(previous) if previous[k] != now[k]
        )
        result["dailyVersions"].append(
            {
                "observedAt": str(observed),
                "week": latest,
                "rows": len(now),
                "new": len(set(now) - set(previous)),
                "changes": dict(changes),
            }
        )
        previous = now
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
