"""Build team features on Arbit's real history and record coverage and examples (slice 3b).

Decisions: every 2025 week 10 game at its kickoff (a past season, retrospective rules), and every
2026 week 12 game at the time of the run (Arbit's current data). Reports timing, coverage per
feature, the league means used, and each 2026 week 12 team's strongest and weakest matchups by
the opponent's adjusted, shrunk FFA points allowed per position. Read only; writes a receipt.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/team_features_audit.py docs/research/team-features-audit-2026-11-23.json
"""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arbit_core.rules import RuleSet
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_model.feature_specs import FEATURES, POSITIONS
from arbit_model.gamebook import Gamebooks
from arbit_model.point_in_time import PointInTime
from arbit_model.team_features import team_features
from sqlalchemy import create_engine, text

FORMAT = "arbit-team-features-audit-v1"


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
    with engine.connect() as c:
        payload: dict[str, Any] = c.execute(
            text(
                "select r.payload from rule_version r "
                "join league_document d on d.rules_hash = r.hash "
                "join current_snapshot s on s.snapshot_id = d.snapshot_id"
            )
        ).scalar_one()
    rules = {
        role: RuleSet.model_validate_json(json.dumps(payload[f"{role}_rules"]))
        for role in ("athlete", "defense")
    }
    books = Gamebooks(pit, rules)
    now = datetime.now(UTC)
    report: dict[str, Any] = {"format": FORMAT, "generatedAt": now.isoformat(), "runs": []}
    for label, season, week, at in (
        ("2025 week 10 at each kickoff", 2025, 10, None),
        ("2026 week 12 at the run", 2026, 12, now),
    ):
        games = [g.game_id for g in pit.calendar.week(season, week)]
        started = time.monotonic()
        built = team_features(pit, books, games, at=at)
        seconds = round(time.monotonic() - started, 1)
        frame = built.frame
        run: dict[str, Any] = {
            "label": label,
            "games": len(games),
            "rows": frame.height,
            "seconds": seconds,
            "featureColumns": len(FEATURES),
            "coverage": built.lineage["coverage"],
            "decisions": [
                {
                    k: d[k]
                    for k in (
                        "at",
                        "gamebook",
                        "previousSeason",
                        "leagueMeans",
                        "positionLeagueMeans",
                        "dstLeagueMean",
                    )
                }
                for d in built.lineage["decisions"]
            ],
        }
        if season == 2026:
            matchups = []
            for row in frame.sort("team").iter_rows(named=True):
                adj = {p: row[f"opp_dvp_{p}_adj_shrunk"] for p in POSITIONS}
                matchups.append(
                    {
                        "team": row["team"],
                        "opponent": row["opponent"],
                        "gamesPlayed": row["games_played"],
                        "offEpaPerPlayShrunk": round(row["off_epa_per_play_shrunk"], 3),
                        "oppAdjustedAllowedShrunk": {
                            p: round(v, 2) for p, v in adj.items() if v is not None
                        },
                        "oppOffenseDstAllowedShrunk": round(row["opp_off_dst_allowed_pg_shrunk"], 2)
                        if row["opp_off_dst_allowed_pg_shrunk"] is not None
                        else None,
                    }
                )
            run["matchups"] = matchups
        report["runs"].append(run)
        low = {k: v for k, v in run["coverage"].items() if v is not None and v < 1}
        print(label, f"{frame.height} rows in {seconds}s; features below full coverage: {low}")
    args.receipt.write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    print(f"wrote {args.receipt}")


if __name__ == "__main__":
    main()
