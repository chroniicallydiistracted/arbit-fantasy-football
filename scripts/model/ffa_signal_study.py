"""What drives FFA points by position, and how quickly each raw statistic carries signal.

Read-only: the nflverse object store and the stored FFA rules. Every line is built by
`arbit_data.nflverse.stat_lines` and scored by `arbit_core.scoring.score`; nothing here
re-implements fantasy arithmetic.

1. Drivers: for fantasy-relevant player-weeks (top N per position by FFA points per game)
   and every D/ST team-game, each category's mean points and its share of FFA point
   variance, cov(category, total) / var(total).
2. Stability: split-half reliability, odd weeks against even weeks within a season. The
   per-game reliability gives the number of games at which observed performance and the
   population mean deserve equal weight, the shrinkage constant for an empirical-Bayes
   estimate.

    ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
      python scripts/model/ffa_signal_study.py docs/research/ffa-signal-study-2026-11-09.json
"""

import argparse
import hashlib
import json
import os
import statistics
from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_core.rules import RuleSet, StatLine
from arbit_core.scoring import MissingStatError, score
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.nflverse.repository import get_dataset
from arbit_data.nflverse.stat_lines import (
    ADAPTER_VERSION,
    PLAY_COLUMNS,
    athlete_line,
    defense_line,
    game_events,
)
from sqlalchemy import create_engine, text

SEASONS = range(2016, 2026)
TOP = {"QB": 32, "RB": 64, "WR": 96, "TE": 48, "K": 32}
MIN_GAMES = 8
PLAYER_FIELDS = (
    "player_id",
    "position",
    "season",
    "week",
    "team",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "receiving_air_yards",
    "receiving_yards_after_catch",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "rushing_epa",
    "attempts",
    "passing_yards",
    "passing_tds",
    "passing_interceptions",
    "sacks_suffered",
    "passing_epa",
    "fg_att",
    "fg_made",
    "pat_att",
)

Row = dict[str, Any]
Value = Callable[[Row], float | None]


class Tables:
    def __init__(self, uow: UnitOfWork, store: ObjectStore) -> None:
        self.uow, self.store = uow, store
        self.manifests: dict[str, str] = {}

    def read(self, key: str, columns: list[str] | None = None) -> list[Row]:
        manifest = get_dataset(self.uow, f"nflverse/nflverse-data/{key}")
        if manifest is None or manifest.get("parquet_hash") is None:
            raise SystemExit(f"dataset unavailable: {key}")
        self.manifests[key] = str(manifest["manifest_hash"])
        path = self.store.verify(str(manifest["parquet_hash"])).path
        rows: list[Row] = pq.read_table(path, columns=columns).to_pylist()
        return rows


def scored(line: StatLine, rules: RuleSet) -> tuple[float, dict[str, float]]:
    breakdown = score(line, rules)
    parts: dict[str, float] = defaultdict(float)
    for item in breakdown.contributions:
        parts[item.stat_id] += float(item.points)
    return float(breakdown.total), dict(parts)


def num(row: Row, key: str) -> float:
    value = row.get(key)
    return float(value) if value is not None else 0.0


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 20:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else None


def split_half(
    units: Mapping[tuple[str, int], list[Row]],
    numerator: Value,
    denominator: Value,
    min_denominator: float,
    per_game: bool,
) -> dict[str, Any]:
    first, second, games, totals = [], [], [], []
    for weeks in units.values():
        halves: list[tuple[float, int, float]] = []
        for parity in (1, 0):
            rows = [
                w
                for w in weeks
                if w["week"] % 2 == parity
                and numerator(w) is not None
                and denominator(w) is not None
            ]
            bottom = sum(denominator(w) or 0.0 for w in rows)
            if len(rows) < 4 or bottom < min_denominator:
                break
            halves.append((sum(numerator(w) or 0.0 for w in rows) / bottom, len(rows), bottom))
        if len(halves) == 2:
            first.append(halves[0][0])
            second.append(halves[1][0])
            games.append((halves[0][1] + halves[1][1]) / 2)
            totals.append((halves[0][2] + halves[1][2]) / 2)
    r = pearson(first, second)
    if r is None or r <= 0:
        return {"unitSeasons": len(first), "splitHalfR": r}
    per_half = statistics.fmean(games)
    per_game_reliability = r / (per_half - (per_half - 1) * r)
    games_for_half = (1 - per_game_reliability) / per_game_reliability
    return {
        "unitSeasons": len(first),
        "splitHalfR": round(r, 3),
        "seasonReliability": round(2 * r / (1 + r), 3),
        "gamesForHalfSignal": round(games_for_half, 1),
        "denominatorForHalfSignal": None
        if per_game
        else round(games_for_half * statistics.fmean(totals) / per_half),
    }


def field(key: str) -> Value:
    return lambda row: None if row.get(key) is None else float(row[key])


def one(_: Row) -> float:
    return 1.0


def dropbacks(row: Row) -> float:
    return num(row, "attempts") + num(row, "sacks_suffered")


def player_tests(position: str) -> dict[str, tuple[Value, Value, float, bool]]:
    tests: dict[str, tuple[Value, Value, float, bool]] = {
        "ffa_points_per_game": (field("ffa"), one, 4, True)
    }
    if position in ("RB", "WR", "TE"):
        tests |= {
            "offense_snap_share": (field("snap_pct"), one, 4, True),
            "targets_per_game": (field("targets"), one, 4, True),
            "target_share": (field("targets"), field("team_targets"), 40, False),
            "air_yards_share": (field("receiving_air_yards"), field("team_air_yards"), 200, False),
            "catch_rate": (field("receptions"), field("targets"), 10, False),
            "yards_per_target": (field("receiving_yards"), field("targets"), 10, False),
            "receiving_td_per_target": (field("receiving_tds"), field("targets"), 10, False),
            "air_yards_per_target": (field("receiving_air_yards"), field("targets"), 10, False),
            "yac_per_reception": (
                field("receiving_yards_after_catch"),
                field("receptions"),
                8,
                False,
            ),
        }
    if position in ("RB", "QB"):
        tests |= {
            "carries_per_game": (field("carries"), one, 4, True),
            "rushing_yards_per_carry": (field("rushing_yards"), field("carries"), 15, False),
            "rushing_td_per_carry": (field("rushing_tds"), field("carries"), 15, False),
            "rushing_epa_per_carry": (field("rushing_epa"), field("carries"), 15, False),
        }
    if position == "RB":
        tests["carry_share"] = (field("carries"), field("team_carries"), 40, False)
    if position == "QB":
        tests |= {
            "pass_attempts_per_game": (field("attempts"), one, 4, True),
            "passing_yards_per_attempt": (field("passing_yards"), field("attempts"), 80, False),
            "passing_td_per_attempt": (field("passing_tds"), field("attempts"), 80, False),
            "interceptions_per_attempt": (
                field("passing_interceptions"),
                field("attempts"),
                80,
                False,
            ),
            "sack_rate": (field("sacks_suffered"), dropbacks, 80, False),
            "passing_epa_per_dropback": (field("passing_epa"), dropbacks, 80, False),
            "rushing_yards_per_game": (field("rushing_yards"), one, 4, True),
        }
    if position == "K":
        tests |= {
            "field_goal_attempts_per_game": (field("fg_att"), one, 4, True),
            "field_goal_accuracy": (field("fg_made"), field("fg_att"), 6, False),
            "extra_point_attempts_per_game": (field("pat_att"), one, 4, True),
        }
    return tests


TEAM_TESTS: dict[str, tuple[Value, Value, float, bool]] = {
    "dst_ffa_points_per_game": (field("ffa"), one, 4, True),
    "offensive_plays_per_game": (field("plays"), one, 4, True),
    "dropback_rate": (field("dropbacks"), field("plays"), 100, False),
    "points_scored_per_game": (field("points"), one, 4, True),
    "offensive_epa_per_play": (field("off_epa"), field("plays"), 100, False),
    "points_allowed_per_game": (field("allowed"), one, 4, True),
    "defensive_epa_per_play_allowed": (field("def_epa"), field("opp_plays"), 100, False),
    "sack_rate_forced": (field("sacks"), field("opp_dropbacks"), 100, False),
    "takeaways_per_game": (field("takeaways"), one, 4, True),
}


def drivers(rows: list[Row]) -> dict[str, Any]:
    totals = [float(r["ffa"]) for r in rows]
    mean_total, variance = statistics.fmean(totals), statistics.pvariance(totals)
    categories: dict[str, Any] = {}
    for category in sorted({c for r in rows for c in r["parts"]}):
        values = [float(r["parts"].get(category, 0.0)) for r in rows]
        mean = statistics.fmean(values)
        cov = statistics.fmean(
            (v - mean) * (t - mean_total) for v, t in zip(values, totals, strict=True)
        )
        if abs(mean) >= 0.005 or abs(cov / variance) >= 0.0005:
            categories[category] = {
                "meanPoints": round(mean, 3),
                "varianceShare": round(cov / variance, 3),
            }
    return {
        "rows": len(rows),
        "meanFFA": round(mean_total, 2),
        "sdFFA": round(variance**0.5, 2),
        "categories": categories,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()

    engine = create_engine(os.environ["ARBIT_DATABASE_URL"], hide_parameters=True)
    tables = Tables(
        UnitOfWork(engine),
        ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects"),
    )
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
    metrics = {
        role: [str(getattr(rule, "stat", "")) for rule in rs.rules] for role, rs in rules.items()
    }
    pfr_to_gsis = {
        str(r["pfr_id"]): str(r["gsis_id"])
        for r in tables.read("players/players", ["pfr_id", "gsis_id"])
        if r["pfr_id"] and r["gsis_id"]
    }
    schedules = tables.read("schedules/games")

    player_weeks: list[Row] = []
    team_weeks: list[Row] = []
    refused: dict[str, int] = defaultdict(int)
    for season in SEASONS:
        games = {
            g["game_id"]: g
            for g in schedules
            if g["season"] == season and g["game_type"] == "REG" and g["home_score"] is not None
        }
        plays: dict[str, list[Row]] = defaultdict(list)
        for play in tables.read(f"pbp/play_by_play_{season}", list(PLAY_COLUMNS)):
            plays[play["game_id"]].append(play)
        events = {game_id: game_events(game_plays) for game_id, game_plays in plays.items()}
        team_rows = {
            (r["team"], r["game_id"]): r
            for r in tables.read(f"stats_team/stats_team_week_{season}")
            if r["season_type"] == "REG"
        }
        snaps = {
            (pfr_to_gsis[r["pfr_player_id"]], r["week"]): r["offense_pct"]
            for r in tables.read(f"snap_counts/snap_counts_{season}")
            if r["game_type"] == "REG" and r["pfr_player_id"] in pfr_to_gsis
        }
        for row in tables.read(f"stats_player/stats_player_week_{season}"):
            if row["season_type"] != "REG" or not row["player_id"] or row["game_id"] not in games:
                continue
            line = athlete_line(
                row, events.get(row["game_id"], game_events([])), metrics["athlete"]
            )
            try:
                total, parts = scored(line.line, rules["athlete"])
            except MissingStatError:
                refused["athlete"] += 1
                continue
            team = team_rows.get((row["team"], row["game_id"]), {})
            player_weeks.append(
                {key: row[key] for key in PLAYER_FIELDS}
                | {
                    "team_targets": team.get("targets"),
                    "team_carries": team.get("carries"),
                    "team_air_yards": team.get("receiving_air_yards"),
                    "snap_pct": snaps.get((row["player_id"], row["week"])),
                    "ffa": total,
                    "parts": parts,
                }
            )
        for (team, game_id), own in team_rows.items():
            game = games.get(game_id)
            if game is None:
                continue
            home = team == game["home_team"]
            opponent = game["away_team"] if home else game["home_team"]
            theirs = team_rows.get((opponent, game_id))
            if theirs is None:
                continue
            allowed = int(game["away_score"] if home else game["home_score"])
            line = defense_line(team, own, theirs, allowed, events[game_id], metrics["defense"])
            try:
                total, parts = scored(line.line, rules["defense"])
            except MissingStatError:
                refused["defense"] += 1
                continue
            team_weeks.append(
                {
                    "team": team,
                    "season": season,
                    "week": own["week"],
                    "ffa": total,
                    "parts": parts,
                    "plays": dropbacks(own) + num(own, "carries"),
                    "dropbacks": dropbacks(own),
                    "points": int(game["home_score"] if home else game["away_score"]),
                    "allowed": allowed,
                    "off_epa": num(own, "passing_epa") + num(own, "rushing_epa"),
                    "def_epa": num(theirs, "passing_epa") + num(theirs, "rushing_epa"),
                    "opp_plays": dropbacks(theirs) + num(theirs, "carries"),
                    "opp_dropbacks": dropbacks(theirs),
                    "sacks": num(theirs, "sacks_suffered"),
                    "takeaways": num(theirs, "passing_interceptions")
                    + num(theirs, "fumbles_lost_total"),
                }
            )

    by_player: dict[tuple[str, int], list[Row]] = defaultdict(list)
    for r in player_weeks:
        by_player[(r["player_id"], r["season"])].append(r)
    relevant: set[tuple[str, int]] = set()
    for season in SEASONS:
        for position, count in TOP.items():
            ranked = sorted(
                (
                    (statistics.fmean(w["ffa"] for w in weeks), key)
                    for key, weeks in by_player.items()
                    if key[1] == season
                    and weeks[0]["position"] == position
                    and len(weeks) >= MIN_GAMES
                ),
                reverse=True,
            )
            relevant.update(key for _, key in ranked[:count])

    report: dict[str, Any] = {
        "adapter": ADAPTER_VERSION,
        "startedAt": started.isoformat(),
        "seasons": [SEASONS.start, SEASONS.stop - 1],
        "rules": {role: rs.content_hash for role, rs in rules.items()},
        "population": {
            position: f"top {count} by FFA points per game, {MIN_GAMES}+ regular-season games"
            for position, count in TOP.items()
        }
        | {"D/ST": "every team-game"},
        "refusedLines": dict(refused),
        "drivers": {},
        "stability": {},
    }
    for position in TOP:
        rows = [
            r
            for r in player_weeks
            if r["position"] == position and (r["player_id"], r["season"]) in relevant
        ]
        report["drivers"][position] = drivers(rows)
        units = {
            key: weeks
            for key, weeks in by_player.items()
            if key in relevant and weeks[0]["position"] == position
        }
        report["stability"][position] = {
            name: split_half(units, *spec) for name, spec in player_tests(position).items()
        }
    report["drivers"]["D/ST"] = drivers(team_weeks)
    by_team: dict[tuple[str, int], list[Row]] = defaultdict(list)
    for r in team_weeks:
        by_team[(r["team"], r["season"])].append(r)
    report["stability"]["TEAM"] = {
        name: split_half(by_team, *spec) for name, spec in TEAM_TESTS.items()
    }
    report["nflverseManifests"] = dict(sorted(tables.manifests.items()))
    body = json.dumps(report, indent=1, sort_keys=True)
    report["reportSha256"] = hashlib.sha256(body.encode()).hexdigest()
    arguments.output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
