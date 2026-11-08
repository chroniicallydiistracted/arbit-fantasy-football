"""How each timed play's re-creation lines up with its real snap-to-whistle time (OWN-051, OWN-052).

Runs the production animation build on NFL games and, for every play with snap and whistle
times, compares the finished script with the real time:

- **whistle error:** the script's whistle against the snap plus the real time. The board's clock
  runs in real time and stops on the play's end clock, so this is when the clock stops while the
  play is still drawn, or how long it waits after the play is over.
- **dead time:** from the moment the action is over (the carrier down, out or scoring, the ball
  dead) to the whistle. A natural dead ball is 0.4 to 1.5 seconds.
- **overrun:** action still going after the real whistle.

Usage (reads team rows and, with --event, stored plays from the local database):
  uv run --env-file .env.local python scripts/live/check_play_timing.py \\
      [--weekly WEEKLY_DETAILS.json ...] [--event ESPN_EVENT_ID ...] [--rows OUT.json] [--before]
"""

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

from arbit_data.db import UnitOfWork
from arbit_data.live import animation, context
from arbit_data.live.choreography import SNAP, PlayScript
from arbit_data.live.nfl_api import GameLink, to_live_plays
from arbit_data.live.nfl_feed import _code
from arbit_data.schema import nfl_team
from arbit_worker.sync_commands import local_database_url
from sqlalchemy import create_engine, select

DEAD_BALL = (0.4, 1.5)  # seconds from the end of the action to a natural whistle
AFTER = ("idle_", "stance_", "stand", "rise")  # poses after the play, not the play


def action_end(script: PlayScript) -> float:
    """When the play is over: the last movement of the play, a player going down, or the ball
    landing, as `choreography._finish` judges it, ignoring what players do after the play."""
    moments = [SNAP]
    for actor in script.actors:
        previous = None
        for seg in actor.segments:
            moved = math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) > 0.05
            if moved and not seg.pose.startswith(AFTER):
                moments.append(seg.end)
            # Going down, not lying there: a finished script continues a last pose to its end.
            if seg.pose.startswith(("ground", "kneel")) and previous != seg.pose:
                moments.append(seg.start)
            previous = seg.pose
    moments += [b.end for b in script.ball if b.state == "flight" and b.end < 1e8]
    return max(moments)


def real_time(entry: dict[str, Any]) -> float | None:
    from datetime import datetime

    if not entry.get("snap_at") or not entry.get("whistle_at"):
        return None
    start = datetime.fromisoformat(entry["snap_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(entry["whistle_at"].replace("Z", "+00:00"))
    seconds = (end - start).total_seconds()
    return seconds if 0 < seconds < 60 else None


def rows_of(made: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in made["entries"]:
        script, real = entry["script"], real_time(entry)
        if script is None or real is None or entry["cancelled"] or script.note is not None:
            continue
        over = action_end(script) - SNAP
        rows.append(
            {
                "event": made["event_id"],
                "play": entry["play_id"],
                "part": entry["part"],
                "template": script.template,
                "real": round(real, 3),
                "action": round(over, 3),
                "whistle_error": round(script.whistle - SNAP - real, 3),
                "dead": round(max(0.0, real - over), 3),
                "overrun": round(max(0.0, over - real), 3),
            }
        )
    return rows


def weekly_games(paths: list[Path], teams: dict[str, Any]) -> list[dict[str, Any]]:
    ids = {
        r["gsis_id"]: str(r["espn_id"])
        for r in context._table("players/players")
        if r.get("gsis_id") and r.get("espn_id")
    }
    events = {
        str(r["old_game_id"]): str(r["espn"])
        for r in context._table("schedules/games")
        if r.get("espn")
    }
    made = []
    for path in paths:
        for raw in json.loads(path.read_text()):
            elias = next(
                (v["id"] for v in raw.get("externalIds") or [] if v["source"] == "elias"), None
            )
            event = events.get(str(elias))
            home, away = _code(raw.get("homeTeam")), _code(raw.get("awayTeam"))
            if not event or home not in teams or away not in teams:
                continue
            ht, at = teams[home], teams[away]
            link = GameLink(raw["id"], event, ht.espn_id, at.espn_id, home, away)
            plays = to_live_plays(raw, link, ids, 2026)
            names = {t.espn_id: [t.location, f"{t.location} {t.name}"] for t in (ht, at)}
            game = {
                "home": ht.espn_id,
                "away": at.espn_id,
                "home_code": home,
                "away_code": away,
                "kickoff": raw.get("time"),
                "names": names,
            }
            with (
                patch.object(animation, "_game", return_value=game),
                patch.object(animation, "current_plays", return_value=list(plays)),
            ):
                built = animation.build(None, event)  # type: ignore[arg-type]
            if built is not None:
                made.append(built)
    return made


def q(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))] if ordered else 0.0


def report(rows: list[dict[str, Any]]) -> None:
    games = len({r["event"] for r in rows})
    print(f"{len(rows)} timed plays in {games} games")
    print(
        f"{'template':<14}{'n':>6}{'real':>7}{'action':>8}{'clock ok':>10}"
        f"{'dead p50':>10}{'dead p90':>10}{'dead >1.5':>11}{'overruns':>10}"
    )
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by[r["template"]].append(r)
    for template, rs in sorted(by.items(), key=lambda kv: -len(kv[1])) + [("all", rows)]:
        dead = [r["dead"] for r in rs]
        print(
            f"{template:<14}{len(rs):>6}{statistics.median(r['real'] for r in rs):>7.1f}"
            f"{statistics.median(r['action'] for r in rs):>8.1f}"
            f"{sum(abs(r['whistle_error']) <= 0.05 for r in rs) / len(rs):>10.0%}"
            f"{q(dead, 0.5):>10.1f}{q(dead, 0.9):>10.1f}"
            f"{sum(d > DEAD_BALL[1] for d in dead) / len(rs):>11.0%}"
            f"{sum(r['overrun'] > 0.05 for r in rs):>10}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly", type=Path, action="append", default=[])
    parser.add_argument("--event", action="append", default=[])
    parser.add_argument("--rows", type=Path, help="write every play's row here (private data/)")
    parser.add_argument(
        "--before",
        action="store_true",
        help="the baseline: build without the real time, then only the uniform stretch (ENG-042)",
    )
    args = parser.parse_args()
    if args.before:
        natural, natural_try = animation.choreograph, animation.choreograph_try
        animation.choreograph = lambda *a, **k: natural(*a[:5])  # type: ignore[assignment]
        animation.choreograph_try = lambda *a, **k: natural_try(*a[:5])  # type: ignore[assignment]
    engine = create_engine(local_database_url(), hide_parameters=True)
    with engine.connect() as connection:
        teams = {r.abbreviation: r for r in connection.execute(select(nfl_team))}
    made = weekly_games(args.weekly, teams)
    uow = UnitOfWork(engine)
    made += [m for event in args.event if (m := animation.build(uow, event)) is not None]
    engine.dispose()
    rows = [row for m in made for row in rows_of(m)]
    report(rows)
    if args.rows:
        args.rows.write_text(json.dumps(rows) + "\n")


if __name__ == "__main__":
    main()
