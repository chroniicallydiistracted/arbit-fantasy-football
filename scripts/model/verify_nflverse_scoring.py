"""Verify FFA stat lines built from nflverse against ESPN's raw statistics (M3 slice 1 evidence).

Reads ESPN's per-week actual statistics for every QB, RB, WR, TE, K and D/ST in ESPN's player
pool, for the 2025 regular season and 2026 to date, through cookie-free public reads (about eight,
paced), or replays a saved read. Each ESPN player maps to a GSIS ID through stored aliases, each
D/ST to its nflverse team, and each game by ESPN event ID. Lines come from
`arbit_data.nflverse.stat_lines` and are compared metric by metric and as FFA totals under the
stored rules. Read-only against the database; prints a JSON report.

Usage:
  ARBIT_NFLVERSE_PATH=<repo>/data/nflverse uv run --env-file .env.local \
    python scripts/model/verify_nflverse_scoring.py [--capture DIR | --replay DIR] [--output FILE]

`--pin RECEIPT` reads the nflverse manifests and decided period an earlier receipt recorded, so a
replay reproduces that receipt. `--targets INDEX --targets-store ROOT` also checks every compared
line against the Model's stored historical targets (M3 slice 2) and reports the result under
`targetCheck`, outside the hashed comparison.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from arbit_core.rules import RangeRule, RuleSet, StatLine
from arbit_core.scoring import MissingStatError, score
from arbit_data.db import UnitOfWork
from arbit_data.espn.scoring_mapping import CATEGORIES
from arbit_data.espn.transport import EspnTransport
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.nflverse.stat_lines import (
    ADAPTER_VERSION,
    PLAY_COLUMNS,
    athlete_line,
    defense_line,
    game_events,
)
from arbit_model.inputs import NflverseTables
from arbit_model.storage import read_table
from sqlalchemy import create_engine, text

SEASONS = (2025, 2026)
REGULAR_PERIODS = {2025: 18, 2026: 18}
SLOTS = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 17: "K", 16: "D/ST"}
POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
PAGE = 300
# ESPN and nflverse spell two current team abbreviations differently. Every use is checked
# against the game joined by ESPN event ID, so a wrong entry shows as a team mismatch.
ESPN_TO_NFLVERSE_TEAM = {"WSH": "WAS", "LAR": "LA"}


def fetch_pool(capture: Path | None) -> tuple[dict[int, list[dict[str, Any]]], list[str]]:
    transport = EspnTransport()
    pool: dict[int, list[dict[str, Any]]] = {}
    receipts: list[str] = []
    for slot in SLOTS:
        pool[slot] = []
        for page in range(10):
            fetched = transport.get(
                2026,
                views=("kona_player_info",),
                scoring_period=9,
                fantasy_filter={
                    "players": {
                        "filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]},
                        "filterSlotIds": {"value": [slot]},
                        "filterStatsForTopScoringPeriodIds": {
                            "value": 30,
                            "additionalValue": ["002025", "002026"],
                        },
                        "limit": PAGE,
                        "offset": page * PAGE,
                        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                    }
                },
            )
            receipts.append(fetched.receipt.sha256)
            assert isinstance(fetched.payload, dict)
            players = fetched.payload["players"]
            pool[slot].extend(players)
            time.sleep(2)
            if len(players) < PAGE:
                break
    if capture:
        capture.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pool": pool, "receipts": receipts}, default=str)
        (capture / "espn-pool.json").write_text(payload)
    return pool, receipts


def replay_pool(directory: Path) -> tuple[dict[int, list[dict[str, Any]]], list[str]]:
    saved = json.loads((directory / "espn-pool.json").read_text())
    return {int(slot): players for slot, players in saved["pool"].items()}, saved["receipts"]


def load_targets(
    store: ObjectStore, index_hash: str
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    """Stored target rows by role, keyed by (GSIS ID or team, game ID)."""
    index = json.loads(store.read(index_hash))
    found: dict[str, dict[tuple[str, str], dict[str, Any]]] = {"athlete": {}, "defense": {}}
    for digest in index["seasons"].values():
        manifest = json.loads(store.read(digest))
        for role in found:
            for row in read_table(store, manifest["tables"][role]["parquet"]).to_pylist():
                key = (row["team"] if role == "defense" else row["player_id"], row["game_id"])
                found[role][key] = row
    return found


def compare_target(
    line: Any,
    target: dict[str, Any] | None,
    espn_total: Decimal,
    rules: RuleSet,
    check: Counter[str],
    details: list[dict[str, Any]],
) -> None:
    """A stored target must carry the same values and points as the line built here. A value
    unknown here may be known there only through the R-061 snap rule; such a line is then also
    compared with ESPN's total."""
    if target is None:
        check["missing"] += 1
        return
    check["checked"] += 1
    overrides = {o["metric"]: o["value"] for o in target["source_overrides"]}
    resolved = False
    for metric, value in line.line.values.items():
        stored = target[metric]
        if value is not None:
            if stored is None or Decimal(stored) != value:
                check["valueMismatch"] += 1
                details.append({"issue": "VALUE", "metric": metric, "game": target["game_id"]})
                return
        elif stored is not None:
            if "R-061" not in overrides.get(metric, ""):
                check["unexplainedResolution"] += 1
                details.append({"issue": "RESOLVED", "metric": metric, "game": target["game_id"]})
                return
            resolved = True
    try:
        ours: Decimal | None = score(line.line, rules).total
    except MissingStatError:
        ours = None
    points = target["points"]
    if ours is not None:
        check[
            "samePoints" if points is not None and Decimal(points) == ours else "pointsMismatch"
        ] += 1
    elif points is None:
        check["bothRefused"] += 1
    elif resolved:
        same = Decimal(points) == espn_total
        check["resolvedByR061MatchesEspn" if same else "resolvedByR061DiffersFromEspn"] += 1
        if not same:
            details.append(
                {
                    "issue": "R061_ESPN",
                    "player": target["player_id"],
                    "game": target["game_id"],
                    "points": str(points),
                    "espn": str(espn_total),
                }
            )
    else:
        check["pointsMismatch"] += 1


def espn_values(stats: Mapping[str, Any], rules: RuleSet) -> dict[str, Decimal]:
    """Raw ESPN statistics as canonical metrics; an absent counter is zero (M1c sparse policy)."""
    values: dict[str, Decimal] = {}
    for rule in rules.rules:
        category = CATEGORIES[int(rule.id)]
        raw = stats.get(category.raw)
        if raw is None and isinstance(rule, RangeRule):
            raise ValueError("MISSING_RANGE_TOTAL")
        values[category.stat] = Decimal(str(raw if raw is not None else 0))
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--capture", type=Path, help="save the ESPN read here (private)")
    source.add_argument("--replay", type=Path, help="replay a saved ESPN read")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pin", type=Path, help="reproduce this receipt's nflverse inputs")
    parser.add_argument("--targets", help="index hash of stored Model targets to check")
    parser.add_argument("--targets-store", type=Path, help="root of the Model's object store")
    arguments = parser.parse_args()
    pinned = json.loads(arguments.pin.read_text()) if arguments.pin else None
    stored = (
        load_targets(ObjectStore(arguments.targets_store / "objects"), arguments.targets)
        if arguments.targets and arguments.targets_store
        else None
    )

    engine = create_engine(os.environ["ARBIT_DATABASE_URL"], hide_parameters=True)
    uow = UnitOfWork(engine)
    store = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    started = datetime.now(UTC)
    with engine.connect() as c:
        settings_row = c.execute(
            text(
                "select r.payload, (d.payload->>'scoring_period')::int - 1 from rule_version r "
                "join league_document d on d.rules_hash = r.hash "
                "join current_snapshot s on s.snapshot_id = d.snapshot_id"
            )
        ).one()
        rule_payload: dict[str, Any] = settings_row[0]
        decided_through = int(settings_row[1])
        if pinned is not None:
            decided_through = int(pinned["decidedThroughPeriod2026"])
        gsis_by_espn: dict[str, str] = dict(
            c.execute(
                text(
                    "select e.external_id, g.external_id from entity_alias e "
                    "join entity_alias g on g.entity_id = e.entity_id and g.provider = 'gsis' "
                    "and g.kind = 'athlete' and g.valid_to is null "
                    "where e.provider = 'espn' and e.kind = 'athlete' and e.valid_to is null"
                )
            ).all()
        )
        teams: dict[int, str] = {
            int(str(k)): str(v)
            for k, v in c.execute(text("select espn_id, abbreviation from nfl_team"))
        }
    rules = {
        "athlete": RuleSet.model_validate_json(json.dumps(rule_payload["athlete_rules"])),
        "defense": RuleSet.model_validate_json(json.dumps(rule_payload["defense_rules"])),
    }
    metrics = {role: [rule_stat(r) for r in rs.rules] for role, rs in rules.items()}
    if pinned is not None and pinned["rules"] != {r: rs.content_hash for r, rs in rules.items()}:
        raise SystemExit("the stored FFA rules differ from the pinned receipt's")
    pool, receipts = (
        replay_pool(arguments.replay) if arguments.replay else fetch_pool(arguments.capture)
    )

    players: dict[int, dict[str, Any]] = {}
    for slot_players in pool.values():
        for entry in slot_players:
            players.setdefault(entry["player"]["id"], entry["player"])

    tables = NflverseTables(uow, store, pinned["nflverseManifests"] if pinned else None)
    check: Counter[str] = Counter()
    check_details: list[dict[str, Any]] = []
    schedules = tables.read("schedules/games")
    report: dict[str, Any] = {
        "adapter": ADAPTER_VERSION,
        "startedAt": started.isoformat(),
        "rules": {role: rs.content_hash for role, rs in rules.items()},
        "espnReceipts": receipts,
        "espnPlayers": len(players),
        "decidedThroughPeriod2026": decided_through,
        "seasons": {},
        "disagreements": [],
        "unresolvedIdentities": [],
    }
    for season in SEASONS:
        games = {
            str(g["espn"]): g
            for g in schedules
            if g["season"] == season and g["game_type"] == "REG" and g.get("espn")
        }
        by_game_id = {g["game_id"]: g for g in games.values()}
        player_rows: dict[tuple[str, str], dict[str, Any]] = {}
        for row in tables.read(f"stats_player/stats_player_week_{season}"):
            if row["season_type"] == "REG" and row["player_id"]:
                player_rows[(row["player_id"], row["game_id"])] = row
        team_rows = {
            (row["team"], row["game_id"]): row
            for row in tables.read(f"stats_team/stats_team_week_{season}")
            if row["season_type"] == "REG"
        }
        plays: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for play in tables.read(f"pbp/play_by_play_{season}", PLAY_COLUMNS):
            plays[play["game_id"]].append(play)
        events = {game_id: game_events(game_plays) for game_id, game_plays in plays.items()}

        counts: Counter[str] = Counter()
        by_position: dict[str, Counter[str]] = defaultdict(Counter)
        metric_disagreements: Counter[str] = Counter()
        unknown: Counter[str] = Counter()
        matched_rows: set[tuple[str, str]] = set()
        for player in players.values():
            position = POSITIONS.get(player["defaultPositionId"], "other")
            for block in player.get("stats", []):
                if (
                    block.get("seasonId") != season
                    or block.get("statSourceId") != 0
                    or block.get("statSplitTypeId") != 1
                    or not 1 <= block.get("scoringPeriodId", 0) <= REGULAR_PERIODS[season]
                ):
                    continue
                stats = block.get("stats") or {}
                if stats.get("210") is None or Decimal(str(stats["210"])) != 1:
                    continue
                period = block["scoringPeriodId"]
                provisional = season == 2026 and period > decided_through
                tally = by_position[position]
                tally["played"] += 1
                counts["played"] += 1
                game = games.get(str(block.get("externalId")))
                if game is None:
                    counts["game_not_in_schedules"] += 1
                    continue
                role = "defense" if position == "D/ST" else "athlete"
                expected = espn_values(stats, rules[role])
                if role == "defense":
                    espn_team = teams[-player["id"] - 16000]
                    team = ESPN_TO_NFLVERSE_TEAM.get(espn_team, espn_team)
                    if team not in (game["home_team"], game["away_team"]):
                        counts["team_crosswalk_mismatch"] += 1
                        continue
                    opponent = game["away_team"] if team == game["home_team"] else game["home_team"]
                    own, theirs = (
                        team_rows.get((team, game["game_id"])),
                        team_rows.get((opponent, game["game_id"])),
                    )
                    if own is None or theirs is None or game["home_score"] is None:
                        counts["no_nflverse_team_row"] += 1
                        continue
                    opponent_score = int(
                        game["away_score"] if team == game["home_team"] else game["home_score"]
                    )
                    line = defense_line(
                        team, own, theirs, opponent_score, events[game["game_id"]], metrics[role]
                    )
                else:
                    gsis = gsis_by_espn.get(str(player["id"]))
                    if gsis is None:
                        counts["unresolved_identity"] += 1
                        tally["unresolved_identity"] += 1
                        report["unresolvedIdentities"].append(
                            {
                                "season": season,
                                "period": period,
                                "player": player["fullName"],
                                "espnId": player["id"],
                                "position": position,
                                "espnNonzero": any(expected.values()),
                            }
                        )
                        continue
                    found = player_rows.get((gsis, game["game_id"]))
                    if found is None:
                        zero = not any(expected.values())
                        key = "no_row_espn_zero" if zero else "no_row_espn_nonzero"
                        counts[key] += 1
                        tally[key] += 1
                        if stored is not None:
                            zero_line = stored["athlete"].get((gsis, str(game["game_id"])))
                            if (
                                zero_line is not None
                                and zero_line["basis"] == "snaps_without_statistics"
                            ):
                                check[
                                    "noRowZeroLine"
                                    if zero_line["points"] == 0
                                    else "noRowZeroLineUnknown"
                                    if zero_line["points"] is None
                                    else "noRowZeroLineNonzero"
                                ] += 1
                            else:
                                check["noRowWithoutZeroLine"] += 1
                                check_details.append(
                                    {
                                        "issue": "NO_ZERO_LINE",
                                        "player": gsis,
                                        "game": game["game_id"],
                                        "espnZero": zero,
                                        "position": position,
                                    }
                                )
                        if not zero:
                            report["disagreements"].append(
                                {
                                    "season": season,
                                    "period": period,
                                    "player": player["fullName"],
                                    "position": position,
                                    "issue": "NO_NFLVERSE_ROW",
                                    "espn": {k: str(v) for k, v in expected.items() if v},
                                }
                            )
                        continue
                    row = found
                    matched_rows.add((gsis, game["game_id"]))
                    line = athlete_line(
                        row, events.get(game["game_id"], game_events([])), metrics[role]
                    )
                counts["compared"] += 1
                tally["compared"] += 1
                espn_total = score(StatLine(scope="game", values=dict(expected)), rules[role]).total
                if stored is not None:
                    target_key = (str(team if role == "defense" else gsis), str(game["game_id"]))
                    compare_target(
                        line,
                        stored[role].get(target_key),
                        espn_total,
                        rules[role],
                        check,
                        check_details,
                    )
                for metric, reason in line.unknown.items():
                    unknown[f"{metric}:{reason}"] += 1
                differences = {
                    metric: (str(value), str(line.line.values[metric]))
                    for metric, value in expected.items()
                    if line.line.values[metric] is not None and line.line.values[metric] != value
                }
                try:
                    ours = score(line.line, rules[role]).total
                except MissingStatError:
                    counts["refused_unknown"] += 1
                    continue
                theirs_total = espn_total
                if differences or ours != theirs_total:
                    key = "provisional_disagreement" if provisional else "disagreement"
                    counts[key] += 1
                    tally[key] += 1
                    for metric in differences:
                        metric_disagreements[metric] += 1
                    report["disagreements"].append(
                        {
                            "season": season,
                            "period": period,
                            "provisional": provisional,
                            "player": player["fullName"],
                            "position": position,
                            "issue": "VALUE",
                            "metrics": {
                                m: {"espn": e, "nflverse": n} for m, (e, n) in differences.items()
                            },
                            "points": {"espn": str(theirs_total), "nflverse": str(ours)},
                        }
                    )
                else:
                    counts["exact"] += 1
                    tally["exact"] += 1
        # The reverse direction: nflverse statistics for pool players where ESPN shows no game.
        pool_gsis = {gsis_by_espn.get(str(pid)) for pid in players} - {None}
        reverse = [
            key
            for key, row in player_rows.items()
            if key[0] in pool_gsis
            and key not in matched_rows
            and not (season == 2026 and row["week"] > decided_through + 1)
        ]
        counts["nflverse_row_without_espn_game"] = len(reverse)
        report["seasons"][str(season)] = {
            "counts": dict(counts),
            "byPosition": {k: dict(v) for k, v in sorted(by_position.items())},
            "metricDisagreements": dict(metric_disagreements),
            "unknownMetrics": dict(unknown),
            "reverseExamples": [
                {"gsis": g, "game": gid, "week": by_game_id.get(gid, {}).get("week")}
                for g, gid in sorted(reverse)[:20]
            ],
        }
    report["nflverseManifests"] = tables.manifests
    if stored is not None:
        report["targetCheck"] = {"counts": dict(check), "details": check_details}
    report["finishedAt"] = datetime.now(UTC).isoformat()
    report["reportSha256"] = hashlib.sha256(
        json.dumps(report["seasons"], sort_keys=True).encode()
    ).hexdigest()
    output = json.dumps(report, indent=1, sort_keys=True)
    if arguments.output:
        arguments.output.write_text(output + "\n")
    print(output if not arguments.output else json.dumps(report["seasons"], indent=1))


def rule_stat(rule: Any) -> str:
    return str(CATEGORIES[int(rule.id)].stat)


if __name__ == "__main__":
    main()
    sys.exit(0)
