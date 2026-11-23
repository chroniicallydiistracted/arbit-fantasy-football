"""Audit game-day availability (OWN-073) against Arbit's real captures. Read only; writes a receipt.

Decisions: week 11's earliest Sunday kickoff (inside the R-068 outage, so ESPN wasn't read), the
week's Monday night game at the time of the run (its game day), and the same moment treated as
before game day.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse \\
  ARBIT_AVAILABILITY_PATH=<main checkout>/data/availability uv run --env-file .env.local \\
    python scripts/model/availability_audit.py docs/research/availability-audit-2026-11-23.json
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_model.availability import StoredAvailability, availability, is_game_day
from arbit_model.point_in_time import PointInTime
from sqlalchemy import create_engine

FORMAT = "arbit-availability-audit-v1"
SEASON, WEEK = 2026, 11


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    uow = UnitOfWork(engine)
    store = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    pit = PointInTime.from_store(uow, store)
    source = StoredAvailability(uow)
    games = pit.calendar.week(SEASON, WEEK)
    sunday = min(g.kickoff for g in games if g.kickoff and g.gameday.weekday() == 6)
    monday = next(g for g in games if g.gameday.weekday() == 0)
    now = datetime.now(UTC)
    decisions: list[tuple[str, datetime, bool]] = [
        ("Week 11 earliest Sunday kickoff (R-068 outage, game day)", sunday, True),
        (f"Monday night {monday.game_id}, at the run (game day)", now, is_game_day(monday, now)),
        ("The same moment, before game day", now, False),
    ]
    report: dict[str, Any] = {
        "format": FORMAT,
        "generatedAt": now.isoformat(),
        "source": "arbit_local, the nflverse store and the availability store, read only",
        "decisions": [],
    }
    for label, at, game_day in decisions:
        reading = availability(source, pit, season=SEASON, week=WEEK, at=at, game_day=game_day)
        frame = reading.frame
        out = frame.filter(frame["status"] == "OUT").height
        entry = {
            "label": label,
            **reading.lineage,
            "out": out,
            "final": int(frame["final"].sum()) if frame.height else 0,
            "latestKnownFrom": (
                frame["_known_from"].max().isoformat() if frame.height else None  # type: ignore[union-attr]
            ),
        }
        report["decisions"].append(entry)
        print(json.dumps(entry, default=str))
    args.receipt.write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    print(f"wrote {args.receipt}")


if __name__ == "__main__":
    main()
