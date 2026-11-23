"""How quickly a defense's FFA points allowed to each position carry signal (OWN-068, slice 3b).

Same method as `ffa_signal_study.py` (its `split_half`): each team-season's odd weeks against its
even weeks, regular season 2016–2025, reported as games for half signal. That is the shrinkage
constant k a feature uses: after n games, weight the defense's own rate by n / (n + k).

Measured per position (QB, RB, WR, TE, K) and for D/ST points allowed by an offense:
- raw: FFA points allowed per game;
- adjusted: points allowed minus what each offense faced scores at that position in its other
  games of the season (leave one out), so a defense isn't credited for its schedule.

Reads the stored FFA targets (`data/model`, built by `build_targets.py` from final revisions); an
offline study of stability, not a feature. Writes a JSON receipt.

  uv run python scripts/model/defense_position_study.py \\
    --targets <main checkout>/data/model docs/research/defense-position-study-2026-11-23.json
"""

import argparse
import hashlib
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arbit_model.gamebook import FFA_POSITIONS, POSITIONS  # noqa: E402
from ffa_signal_study import field, one, split_half  # noqa: E402

SEASONS = range(2016, 2026)
FORMAT = "arbit-defense-position-study-v1"


def load(root: Path, season: int, role: str, index: dict[str, Any]) -> pl.DataFrame:
    manifest = json.loads((root / "objects" / index["seasons"][str(season)]).read_bytes())
    digest = manifest["tables"][role]["parquet"]
    return pl.read_parquet(root / "objects" / digest)


def leave_one_out(frame: pl.DataFrame, by: list[str], value: str) -> pl.Expr:
    """Mean of `value` over the group's other rows (null when it has none)."""
    total = pl.col(value).sum().over(by)
    count = pl.col(value).count().over(by)
    return pl.when(count > 1).then((total - pl.col(value)) / (count - 1)).otherwise(None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    pointer = json.loads((args.targets / "targets-current.json").read_text())["index"]
    index = json.loads((args.targets / "objects" / pointer).read_bytes())
    units: dict[str, dict[tuple[str, int], list[dict[str, Any]]]] = {}
    summary: dict[str, list[float]] = {}
    for season in SEASONS:
        athletes = load(args.targets, season, "athlete", index).filter(
            (pl.col("season_type") == "REG") & (pl.col("basis") == "statistics")
        )
        by_position = (
            athletes.with_columns(
                pl.col("position").replace_strict(dict(POSITIONS), default=None).alias("pos"),
                pl.col("points").cast(pl.Float64),
            )
            .filter(pl.col("pos").is_not_null())
            .group_by(["game_id", "week", "team", "opponent", "pos"])
            .agg(pl.col("points").sum())
        )
        # Every team-game appears for every position, with 0 when nobody scored there.
        games = athletes.select("game_id", "week", "team", "opponent").unique()
        grid = games.join(pl.DataFrame({"pos": list(FFA_POSITIONS)}), how="cross")
        filled = grid.join(
            by_position, on=["game_id", "week", "team", "opponent", "pos"], how="left"
        ).with_columns(pl.col("points").fill_null(0.0))
        filled = filled.with_columns(
            leave_one_out(filled, ["team", "pos"], "points").alias("expected")
        ).with_columns((pl.col("points") - pl.col("expected")).alias("adjusted"))
        for row in filled.iter_rows(named=True):
            for kind in ("raw", "adjusted"):
                value = row["points"] if kind == "raw" else row["adjusted"]
                if value is None:
                    continue
                name = f"{row['pos']}_{kind}"
                units.setdefault(name, {}).setdefault((row["opponent"], season), []).append(
                    {"week": row["week"], "value": value}
                )
                if kind == "raw":
                    summary.setdefault(row["pos"], []).append(value)
        dst = (
            load(args.targets, season, "defense", index)
            .filter(pl.col("season_type") == "REG")
            .select("game_id", "week", "team", "opponent", pl.col("points").cast(pl.Float64))
        )
        dst = dst.with_columns(
            leave_one_out(dst, ["team"], "points").alias("expected")
        ).with_columns((pl.col("points") - pl.col("expected")).alias("adjusted"))
        for row in dst.iter_rows(named=True):
            for kind in ("raw", "adjusted"):
                value = row["points"] if kind == "raw" else row["adjusted"]
                if value is None:
                    continue
                # The unit is the offense: D/ST points it allows.
                units.setdefault(f"DST_{kind}", {}).setdefault(
                    (row["opponent"], season), []
                ).append({"week": row["week"], "value": value})
    stability = {
        name: split_half(groups, field("value"), one, 4, True)
        for name, groups in sorted(units.items())
    }
    report: dict[str, Any] = {
        "format": FORMAT,
        "startedAt": datetime.now(UTC).isoformat(),
        "seasons": [SEASONS.start, SEASONS.stop - 1],
        "targetsIndex": pointer,
        "method": "ffa_signal_study.split_half: odd vs even weeks per defense-season, "
        "Spearman-Brown to games for half signal",
        "pointsAllowedPerTeamGame": {
            pos: {
                "mean": round(statistics.fmean(v), 2),
                "sd": round(statistics.stdev(v), 2),
                "teamGames": len(v),
            }
            for pos, v in sorted(summary.items())
        },
        "stability": stability,
    }
    body = json.dumps(report, indent=1, sort_keys=True)
    report["reportSha256"] = hashlib.sha256(body.encode()).hexdigest()
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    for name, result in stability.items():
        print(name, result)


if __name__ == "__main__":
    main()
