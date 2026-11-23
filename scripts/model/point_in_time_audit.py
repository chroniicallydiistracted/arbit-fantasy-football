"""Audit the point-in-time reader against Arbit's real nflverse history (M3 slice 3, ADR-007).

For each registered table it reports Arbit's capture gaps, how many rows its rule can place in a
game or season, and, at a set of decision times, what the reader returns: units by basis, units
bounded by a gap's start, and the latest known-from time, which must precede the decision. Read
only against the database and the nflverse object store; writes a JSON receipt.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/point_in_time_audit.py docs/research/point-in-time-audit-2026-11-23.json
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_model.point_in_time import KNOWN_FROM, PointInTime
from arbit_model.timing import KNOWN, Calendar, key_season, spec_for
from sqlalchemy import create_engine

FORMAT = "arbit-point-in-time-audit-v1"

# Columns read per table: keys the catalog lists, enough to count units.
TABLES: dict[str, tuple[str, ...]] = {
    "schedules/games": ("game_id", "roof", "surface"),
    "pbp/play_by_play_{s}": ("game_id", "play_id"),
    "stats_player/stats_player_week_{s}": ("game_id", "player_id", "team"),
    "stats_team/stats_team_week_{s}": ("game_id", "team"),
    "snap_counts/snap_counts_{s}": ("game_id", "pfr_player_id"),
    "nextgen_stats/ngs_receiving": ("season", "week", "season_type", "team_abbr"),
    "pfr_advstats/advstats_week_rec_{s}": ("game_id", "pfr_player_id"),
    "ftn_charting/ftn_charting_{s}": ("nflverse_game_id", "nflverse_play_id"),
    "injuries/injuries_{s}": ("season", "week", "team", "gsis_id", "report_status"),
    "weekly_rosters/roster_weekly_{s}": ("season", "week", "team", "gsis_id", "status"),
    "depth_charts/depth_charts_{s}": ("team", "gsis_id", "pos_rank"),
    "rosters/roster_{s}": ("season", "team", "gsis_id"),
    "officials/officials": ("game_id", "official_id"),
    "trades/trades": ("trade_id", "trade_date"),
}


def sunday_kickoff(cal: Calendar, season: int, week: int) -> datetime:
    """The earliest Sunday kickoff of a week (an international game when there is one)."""
    kickoffs = [g.kickoff for g in cal.week(season, week) if g.kickoff and g.gameday.weekday() == 6]
    if not kickoffs:
        raise LookupError(f"NO_SUNDAY_GAMES: {season} week {week}")
    return min(kickoffs)


def placement(pit: PointInTime, key: str) -> dict[str, Any]:
    """How many rows of the newest version the table's rule can time."""
    history = pit.source.history(key)
    if not history.versions:
        return {"versions": 0}
    spec = spec_for(key)
    frame = pit.source.table(history.versions[-1], spec.needs)
    placed = spec.place(frame, pit.calendar, key_season(key))
    untimed = placed[KNOWN].null_count()
    return {"versions": len(history.versions), "rows": frame.height, "untimedRows": untimed}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    store = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    pit = PointInTime.from_store(UnitOfWork(engine), store)
    cal = pit.calendar
    decisions = [
        ("2025 week 11, Sunday (before Arbit's first read)", sunday_kickoff(cal, 2025, 11), 2025),
        ("2026 week 9, Sunday (observed stretch)", sunday_kickoff(cal, 2026, 9), 2026),
        ("2026 week 10, Sunday (inside the R-068 outage)", sunday_kickoff(cal, 2026, 10), 2026),
        ("2026 week 11, Sunday (outage; caught up 22:45 UTC)", sunday_kickoff(cal, 2026, 11), 2026),
    ]
    keys = {season: [pattern.format(s=season) for pattern in TABLES] for season in (2025, 2026)}
    report: dict[str, Any] = {
        "format": FORMAT,
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "arbit_local and the nflverse object store, read only",
        "staleWindowHours": None,
        "tables": {},
        "decisions": [],
    }
    for names in keys.values():
        for key in names:
            history = pit.source.history(key)
            report["staleWindowHours"] = history.stale.total_seconds() / 3600
            report["tables"][key] = {
                "gaps": [
                    [g.start.isoformat() if g.start else None, g.end.isoformat()]
                    for g in history.gaps()
                ],
                **placement(pit, key),
            }
            print(f"{key}: {report['tables'][key]}", file=sys.stderr)
    violations = 0
    for label, at, season in decisions:
        entry: dict[str, Any] = {"label": label, "at": at.isoformat(), "tables": {}}
        for key in keys[season]:
            started = time.monotonic()
            reading = pit.read(key, TABLES[key.replace(str(season), "{s}")], at)
            known = reading.frame[KNOWN_FROM]
            latest = known.max() if reading.frame.height else None
            violations += int((known >= at).sum()) if reading.frame.height else 0
            lineage = dict(reading.lineage)
            lineage.pop("columns", None)
            entry["tables"][key] = {
                **lineage,
                "latestKnownFrom": latest.isoformat() if latest else None,
                "seconds": round(time.monotonic() - started, 1),
            }
            print(f"{label} {key}: {entry['tables'][key]}", file=sys.stderr)
        report["decisions"].append(entry)
    report["rowsKnownAtOrAfterDecision"] = violations
    args.receipt.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(f"wrote {args.receipt}; rows known at or after their decision: {violations}")
    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
