"""When ESPN's fantasy injury status settled each player's game-day availability.

Arbit stores every version of the ESPN league document (about every minute on game days). Each
version holds ESPN's `injury_status` for every player in the pool. For the given weeks, this
follows each player's status around his team's kickoff. It groups players by what nflverse later
recorded: inactive (weekly roster `INA`) or listed Questionable on NFL's injury report.

Read-only against the database and the nflverse object store.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/espn_status_timing.py 2026 8 9
"""

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import entity_alias
from arbit_model.inputs import NflverseTables
from sqlalchemy import create_engine, select, text

ET = ZoneInfo("America/New_York")
Timeline = list[tuple[datetime, str | None]]


def status_at(timeline: Timeline, when: datetime) -> str | None:
    found = None
    for at, status in timeline:
        if at > when:
            break
        found = status
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("season", type=int)
    parser.add_argument("weeks", type=int, nargs="+")
    arguments = parser.parse_args()
    season = arguments.season
    engine = create_engine(os.environ["ARBIT_DATABASE_URL"], hide_parameters=True)
    store = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    tables = NflverseTables(UnitOfWork(engine), store)
    schedules = tables.read("schedules/games")
    roster = tables.read(f"weekly_rosters/roster_weekly_{season}")
    report = tables.read(f"injuries/injuries_{season}")
    snaps = tables.read(f"snap_counts/snap_counts_{season}")
    pfr = {
        r["gsis_id"]: r["pfr_id"]
        for r in tables.read("players/players", ["gsis_id", "pfr_id"])
        if r["pfr_id"]
    }
    with engine.connect() as c:
        gsis = {
            UUID(str(k)): str(v)
            for k, v in c.execute(
                select(entity_alias.c.entity_id, entity_alias.c.external_id).where(
                    entity_alias.c.provider == "gsis", entity_alias.c.kind == "athlete"
                )
            ).all()
        }
    result: dict[str, Any] = {"season": season, "weeks": {}, "inputs": {}}
    for week in arguments.weeks:
        kickoff: dict[str, datetime] = {}
        for g in schedules:
            if g["season"] == season and g["week"] == week and g["game_type"] == "REG":
                local = datetime.fromisoformat(f"{g['gameday']}T{g['gametime']}")
                kickoff[g["home_team"]] = kickoff[g["away_team"]] = local.replace(
                    tzinfo=ET
                ).astimezone(UTC)
        start, end = min(kickoff.values()), max(kickoff.values())
        with engine.connect() as c:
            rows = c.execute(
                text(
                    "select d.published_at, p->>'id', p->>'injury_status' from league_document d,"
                    " jsonb_array_elements(d.payload->'players') p"
                    " where d.published_at between :a and :b order by d.published_at"
                ),
                {"a": start - timedelta(days=2), "b": end + timedelta(hours=4)},
            ).all()
        timelines: dict[str, Timeline] = defaultdict(list)
        versions = set()
        for at, entity, status in rows:
            versions.add(at)
            player = gsis.get(UUID(str(entity)))
            if player is None:
                continue
            line = timelines[player]
            code = None if status is None else str(status)
            if not line or line[-1][1] != code:
                line.append(
                    (at if isinstance(at, datetime) else datetime.fromisoformat(str(at)), code)
                )
        on_report = {r["gsis_id"]: r["report_status"] for r in report if r["week"] == week}
        snapped = {
            r["pfr_player_id"]
            for r in snaps
            if r["week"] == week
            and (r["offense_snaps"] or 0) + (r["defense_snaps"] or 0) + (r["st_snaps"] or 0) > 0
        }
        groups: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
        for r in roster:
            player, team = r["gsis_id"], r["team"]
            if r["week"] != week or player not in timelines or team not in kickoff:
                continue
            if r["status"] == "INA":
                listed = on_report.get(player, "not on report")
                groups[f"inactive; report: {listed}"].append((player, kickoff[team]))
            elif on_report.get(player) == "Questionable":
                played = pfr.get(player) in snapped
                groups["Questionable; " + ("played" if played else "active, no snap")].append(
                    (player, kickoff[team])
                )
        summary = {}
        for name, members in sorted(groups.items()):
            to_out = []
            for player, kick in members:
                line = timelines[player]
                for index, (at, status) in enumerate(line):
                    if status == "OUT" and (index == 0 or line[index - 1][1] != "OUT"):
                        minutes = round((at - kick).total_seconds() / 60)
                        if -24 * 60 <= minutes <= 24 * 60:
                            to_out.append(minutes)
            summary[name] = {
                "players": len(members),
                "twoHoursBefore": dict(
                    Counter(
                        str(status_at(timelines[p], k - timedelta(hours=2))) for p, k in members
                    ).most_common()
                ),
                "atKickoff": dict(
                    Counter(str(status_at(timelines[p], k)) for p, k in members).most_common()
                ),
                "becameOutMinutesFromKickoffWithinADay": sorted(to_out),
            }
        result["weeks"][str(week)] = {
            "games": len(kickoff) // 2,
            "documentVersions": len(versions),
            "groups": summary,
        }
    result["inputs"] = tables.manifests
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
