"""Every difference between two FFA target indexes, classified, for a repair rebuilt on the same
inputs (`build_targets.py --inputs-of`).

A row is matched across the two builds by its game and player (athletes, participation) or its
game and franchise (D/ST). Each difference is one of:

- `team_codes`: only the team or opponent changed, to the same franchise under `arbit_model.teams`;
- `opponent_corrected`: the old row named its own franchise as the opponent;
- `added` or `removed`: the row exists in one build only;
- `values`: points, a statistic, a label or another field changed.

The receipt says which games and teams each difference touches. `--expect SEASONS=TEAMS` names
the franchises a repair may touch in those seasons; a difference in a game without one of them,
or in a season with none, is unexplained, and any unexplained difference fails the run.
Read-only against the store.

  uv run python scripts/model/targets_diff.py --store <main>/data/model --old 4afbd836... \\
    --new <digest> --expect 2012-2015=LV,LAC,LA,ARI,BAL,CLE,HOU 2016=LV,LAC --out receipt.json
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
from arbit_model.teams import FRANCHISE, franchise_expr

KEYS = {
    "athlete": ["game_id", "player_id"],
    "defense": ["game_id", "team"],
    "participation": ["game_id", "player_id"],
}
TEAM_COLUMNS = ("team", "opponent")


def load(objects: Path, digest: str) -> dict[str, Any]:
    raw = (objects / digest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise SystemExit(f"object {digest[:12]} does not match its digest")
    loaded: dict[str, Any] = json.loads(raw)
    return loaded


def table(objects: Path, manifest: dict[str, Any], role: str) -> pl.DataFrame:
    return pl.read_parquet(objects / manifest["tables"][role]["parquet"])


def compare(old: pl.DataFrame, new: pl.DataFrame, role: str) -> pl.DataFrame:
    """One row per difference: keys, kind, the old and new team codes, and the changed columns."""
    keys = KEYS[role]
    old_keyed = old.with_columns(franchise_expr(pl.col("team")).alias("_franchise"))
    new_keyed = new.with_columns(pl.col("team").alias("_franchise"))
    join_keys = ["game_id", "_franchise"] if role == "defense" else keys
    for frame, name in ((old_keyed, "old"), (new_keyed, "new")):
        if frame.select(join_keys).is_duplicated().any():
            raise SystemExit(f"{role}: duplicate keys in the {name} build")
    values = [c for c in old.columns if c not in (*keys, *TEAM_COLUMNS)]
    if set(values) != {c for c in new.columns if c not in (*keys, *TEAM_COLUMNS)}:
        raise SystemExit(f"{role}: the builds' columns differ")
    teams = [c for c in TEAM_COLUMNS if c in old.columns]
    joined = old_keyed.join(new_keyed, on=join_keys, how="full", suffix="_new", coalesce=True)
    present_old = pl.col("team").is_not_null()
    present_new = pl.col("team_new").is_not_null()
    changed_values = [
        pl.when(~pl.col(c).eq_missing(pl.col(c + "_new"))).then(pl.lit(c)) for c in values
    ]
    team_changed = pl.any_horizontal([~pl.col(c).eq_missing(pl.col(c + "_new")) for c in teams])
    same_franchise = pl.all_horizontal(
        [franchise_expr(pl.col(c)).eq_missing(pl.col(c + "_new")) for c in teams]
    )
    self_opponent = (
        franchise_expr(pl.col("team")).eq_missing(franchise_expr(pl.col("opponent")))
        if "opponent" in teams
        else pl.lit(False)
    )
    return (
        joined.with_columns(
            pl.concat_list(changed_values).list.drop_nulls().alias("changed"),
            present_old.alias("_in_old"),
            present_new.alias("_in_new"),
        )
        .with_columns(
            pl.when(~pl.col("_in_old"))
            .then(pl.lit("added"))
            .when(~pl.col("_in_new"))
            .then(pl.lit("removed"))
            .when(pl.col("changed").list.len() > 0)
            .then(pl.lit("values"))
            .when(team_changed & self_opponent)
            .then(pl.lit("opponent_corrected"))
            .when(team_changed & same_franchise)
            .then(pl.lit("team_codes"))
            .when(team_changed)
            .then(pl.lit("values"))
            .otherwise(None)
            .alias("kind")
        )
        .filter(pl.col("kind").is_not_null())
        .select(
            "game_id",
            *(k for k in keys if k != "game_id" and k != "team"),
            "kind",
            *(pl.col(c).alias(c + "_old") for c in teams),
            *(pl.col(c + "_new") for c in teams),
            "changed",
            *(
                [pl.col("points").alias("points_old"), pl.col("points_new")]
                if "points" in values
                else []
            ),
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--expect", nargs="+", type=expectation, default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    objects = args.store / "objects"
    old_index, new_index = load(objects, args.old), load(objects, args.new)
    expect: dict[str, set[str]] = {}
    for seasons, teams in args.expect:
        for season in seasons:
            expect.setdefault(str(season), set()).update(teams)
    receipt: dict[str, Any] = {
        "format": "arbit-ffa-targets-diff-v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "old": {k: old_index.get(k) for k in ("format", "code", "rules", "pinnedFrom")}
        | {"index": args.old},
        "new": {k: new_index.get(k) for k in ("format", "code", "rules", "pinnedFrom", "reason")}
        | {"index": args.new},
        "franchiseMap": dict(FRANCHISE),
        "expect": {season: sorted(teams) for season, teams in sorted(expect.items())},
        "seasons": {},
    }
    unexplained_total = 0
    for season in sorted(set(old_index["seasons"]) | set(new_index["seasons"]), key=int):
        old_m = load(objects, old_index["seasons"][season])
        new_m = load(objects, new_index["seasons"][season])
        entry: dict[str, Any] = {
            "sameInputs": old_m["inputs"] == new_m["inputs"],
            "identicalTables": {
                role: old_m["tables"][role]["parquet"] == new_m["tables"][role]["parquet"]
                for role in KEYS
            },
        }
        if not entry["sameInputs"]:
            raise SystemExit(f"{season}: the builds read different nflverse inputs")
        expected = expect.get(season, set())
        schedule_games = None
        for role in KEYS:
            if entry["identicalTables"][role]:
                entry[role] = {"rows": old_m["tables"][role]["rows"], "differences": 0}
                continue
            diff = compare(table(objects, old_m, role), table(objects, new_m, role), role)
            if schedule_games is None:
                schedule_games = teams_by_game(objects, new_m)
            touched = diff.with_columns(
                pl.col("game_id")
                .replace_strict(schedule_games, default=None, return_dtype=pl.List(pl.String))
                .alias("game_teams")
            ).with_columns(
                pl.col("game_teams")
                .list.eval(pl.element().is_in(list(expected)))
                .list.any()
                .fill_null(False)
                .alias("explained")
            )
            unexplained = touched.filter(~pl.col("explained"))
            unexplained_total += unexplained.height
            kinds = touched.group_by("kind").len().sort("kind")
            entry[role] = {
                "rowsOld": old_m["tables"][role]["rows"],
                "rowsNew": new_m["tables"][role]["rows"],
                "differences": touched.height,
                "byKind": dict(zip(kinds["kind"], kinds["len"], strict=True)),
                "games": touched["game_id"].n_unique(),
                "unexplained": unexplained.height,
                "unexplainedSample": unexplained.head(5).to_dicts(),
            }
            if "points_old" in touched.columns:
                moved = touched.filter(~pl.col("points_old").eq_missing(pl.col("points_new")))
                entry[role]["pointsChanged"] = {
                    "rows": moved.height,
                    "old": float(moved["points_old"].fill_null(0).sum()),
                    "new": float(moved["points_new"].fill_null(0).sum()),
                }
            changed = (
                touched.explode("changed", empty_as_null=True)
                .drop_nulls("changed")
                .group_by("changed")
                .len()
            )
            entry[role]["changedColumns"] = dict(
                zip(changed["changed"], changed["len"], strict=True)
            )
        receipt["seasons"][season] = entry
    receipt["unexplained"] = unexplained_total
    receipt["status"] = "EXPLAINED" if unexplained_total == 0 else "UNEXPLAINED_DIFFERENCES"
    body = json.dumps(receipt, indent=1, sort_keys=True, default=str)
    receipt["receiptSha256"] = hashlib.sha256(body.encode()).hexdigest()
    args.out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({"status": receipt["status"], "unexplained": unexplained_total}))
    if unexplained_total:
        raise SystemExit(1)


def expectation(value: str) -> tuple[list[int], set[str]]:
    seasons, _, teams = value.partition("=")
    low, _, high = seasons.partition("-")
    return list(range(int(low), int(high or low) + 1)), set(teams.split(","))


def teams_by_game(objects: Path, manifest: dict[str, Any]) -> dict[str, list[str]]:
    """Each game's two franchises, from the rebuilt athlete and D/ST tables."""
    frames = [
        table(objects, manifest, role).select("game_id", "team", "opponent")
        for role in ("athlete", "defense")
    ]
    both = pl.concat(frames).unpivot(index="game_id", on=["team", "opponent"]).drop_nulls()
    grouped = both.group_by("game_id").agg(pl.col("value").unique().sort())
    return dict(zip(grouped["game_id"], grouped["value"].to_list(), strict=True))


if __name__ == "__main__":
    main()
