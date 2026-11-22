"""Build the Model's historical FFA targets and participation labels (M3 slice 2).

For each season: every player-game and D/ST team-game of the completed games, as FFA stat lines
from `arbit_data.nflverse.stat_lines`, scored by `arbit_core.scoring.score` under the stored FFA
rules; plus participation labels. Each season is three Parquet tables and a JSON manifest in a
content-addressed store, and an index lists the seasons. Read-only against the database and the
nflverse store; writes only under the output root.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/build_targets.py --output <main checkout>/data/model [--seasons 2012-2026]

`--pin RECEIPT` reads the nflverse manifests a verification receipt lists, for reproduction;
such a build does not move the current pointer.
"""

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arbit_core.rules import RuleSet
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.nflverse.stat_lines import ADAPTER_VERSION, PLAY_COLUMNS
from arbit_model.inputs import NflverseTables
from arbit_model.storage import (
    default_sources,
    participation_table,
    target_table,
    write_parquet,
)
from arbit_model.targets import (
    TARGETS_VERSION,
    SeasonRows,
    participation,
    rule_metrics,
    targets,
)
from sqlalchemy import create_engine, text

LIMITATIONS = [
    "Unknown metrics stay null with a reason, and a line with one is refused rather than scored.",
    "A player who played (snap counts) without a statistics row gets an all-zero line; snap "
    "counts start in 2013, so earlier seasons have none.",
    "Defensive two-point returns are ruled out only for players whose snap row shows no "
    "defensive or special-teams snap (R-061); the rest stay unknown.",
    "Weekly roster status INA appears only in some seasons; without it, inactive and active "
    "players with no snap are labeled rostered_no_snaps.",
    "Position is nflverse's current label; game_position is the snap-count position that game.",
]


def seasons_argument(value: str) -> list[int]:
    low, _, high = value.partition("-")
    return list(range(int(low), int(high or low) + 1))


def code_version() -> str:
    root = Path(__file__).resolve().parents[2]
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return head + ("+uncommitted" if dirty else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seasons", type=seasons_argument, default=seasons_argument("2012-2026"))
    parser.add_argument("--pin", type=Path, help="a receipt whose nflverse manifests to read")
    arguments = parser.parse_args()

    engine = create_engine(os.environ["ARBIT_DATABASE_URL"], hide_parameters=True)
    nflverse = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    pins = json.loads(arguments.pin.read_text())["nflverseManifests"] if arguments.pin else {}
    tables = NflverseTables(UnitOfWork(engine), nflverse, pins)
    store = ObjectStore(arguments.output / "objects")
    started = datetime.now(UTC)
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
    pfr_to_gsis = {
        str(r["pfr_id"]): str(r["gsis_id"])
        for r in tables.read("players/players", ["pfr_id", "gsis_id"])
        if r["pfr_id"] and r["gsis_id"]
    }
    schedules = tables.read("schedules/games")

    index: dict[str, Any] = {
        "format": TARGETS_VERSION + "-index",
        "startedAt": started.isoformat(),
        "code": code_version(),
        "adapter": ADAPTER_VERSION,
        "rules": {role: rs.content_hash for role, rs in rules.items()},
        "pinnedFrom": str(arguments.pin) if arguments.pin else None,
        "seasons": {},
    }
    summary: dict[str, Any] = {}
    for season in arguments.seasons:
        tables.manifests = {"players/players": tables.manifests["players/players"]} | {
            "schedules/games": tables.manifests["schedules/games"]
        }
        snaps = tables.optional(f"snap_counts/snap_counts_{season}")
        rows = SeasonRows(
            season=season,
            games=[g for g in schedules if g["season"] == season],
            plays=tables.read(f"pbp/play_by_play_{season}", PLAY_COLUMNS),
            players=tables.read(f"stats_player/stats_player_week_{season}"),
            teams=tables.read(f"stats_team/stats_team_week_{season}"),
            snaps=snaps,
            rosters=tables.optional(f"weekly_rosters/roster_weekly_{season}"),
            pfr_to_gsis=pfr_to_gsis,
        )
        labels = participation(rows)
        built = targets(rows, rules, labels)
        label_of = {(p.game_id, p.player_id): p.label for p in labels}
        manifest: dict[str, Any] = {
            "format": TARGETS_VERSION,
            "season": season,
            "adapter": ADAPTER_VERSION,
            "rules": index["rules"],
            "inputs": dict(sorted(tables.manifests.items())),
            "tables": {},
            "limitations": LIMITATIONS,
        }
        counts: dict[str, Any] = {}
        for role in ("athlete", "defense"):
            role_rows = [t for t in built if t.role == role]
            sources = default_sources(role_rows)
            metrics = rule_metrics(rules[role])
            ref = write_parquet(store, target_table(role_rows, metrics, label_of, sources))
            manifest["tables"][role] = {
                "parquet": ref.sha256,
                "rows": len(role_rows),
                "defaultSources": sources,
            }
            counts[role] = {
                "rows": len(role_rows),
                "scored": sum(t.points is not None for t in role_rows),
                "byBasis": dict(Counter(t.basis for t in role_rows)),
                "bySeasonType": dict(Counter(t.season_type for t in role_rows)),
                "refusedBy": dict(Counter(str(t.refusal) for t in role_rows if t.refusal)),
                "unknownMetrics": dict(
                    Counter(f"{m}:{r}" for t in role_rows for m, r in t.line.unknown.items())
                ),
                "ruledOutTwoPointReturns": sum(
                    "R-061" in t.line.sources.get("returns.two_point_returns", "")
                    for t in role_rows
                ),
            }
        ref = write_parquet(store, participation_table(labels))
        manifest["tables"]["participation"] = {"parquet": ref.sha256, "rows": len(labels)}
        game_ids = {str(g["game_id"]) for g in rows.games if g.get("home_score") is not None}
        with_plays = {str(p["game_id"]) for p in rows.plays}
        targeted = {t.game_id for t in built}
        counts["participation"] = dict(Counter(p.label for p in labels))
        counts["games"] = {
            "completed": len(game_ids),
            "withoutPlayByPlay": sorted(game_ids - with_plays),
            "withTargets": len(targeted),
        }
        counts["statisticsRowsOutsideCompletedGames"] = sum(
            1 for r in rows.players if str(r["game_id"]) not in targeted
        )
        counts["snapRows"] = len(snaps)
        counts["snapRowsWithoutGsis"] = sum(
            1 for s in snaps if str(s.get("pfr_player_id") or "") not in pfr_to_gsis
        )
        manifest["counts"] = counts
        digest = store.put_json(manifest).sha256
        index["seasons"][str(season)] = digest
        summary[str(season)] = {
            "manifest": digest[:12],
            "athlete": f"{counts['athlete']['scored']}/{counts['athlete']['rows']}",
            "zeroLines": counts["athlete"]["byBasis"].get("snaps_without_statistics", 0),
            "r061": counts["athlete"]["ruledOutTwoPointReturns"],
            "defense": f"{counts['defense']['scored']}/{counts['defense']['rows']}",
            "labels": counts["participation"],
            "gamesWithoutPbp": len(counts["games"]["withoutPlayByPlay"]),
            "statRowsSkipped": counts["statisticsRowsOutsideCompletedGames"],
            "snapRowsWithoutGsis": counts["snapRowsWithoutGsis"],
        }
        print(json.dumps({season: summary[str(season)]}), flush=True)
    index["finishedAt"] = datetime.now(UTC).isoformat()
    digest = store.put_json(index).sha256
    if not arguments.pin:
        pointer = arguments.output / "targets-current.json"
        temporary = pointer.with_suffix(".pending")
        temporary.write_text(json.dumps({"index": digest}) + "\n")
        temporary.replace(pointer)
    print(json.dumps({"index": digest}))


if __name__ == "__main__":
    main()
