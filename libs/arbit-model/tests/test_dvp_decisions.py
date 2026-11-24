"""M3-3 Phase C: start/sit decisions from frozen D/ST forecasts (config/dvp/sitstart.json).

C00/C04/C05 measures on hand-checked and synthetic weeks; the D/ST unit mapping that makes a
group-level D/ST forecast a player-level one (C01/C02, and T26's identity half); the predeclared
rule; and determinism of the week-block bootstrap.
"""

import json
import math
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from arbit_model.dvp import decisions

ROOT = Path(__file__).resolve().parents[3]


def week(season: int, wk: int, rows: list[tuple[str, float, float, float]]) -> pl.DataFrame:
    """rows: (unit, actual, b00, b06)."""
    return pl.DataFrame(
        {
            "season": [season] * len(rows),
            "week": [wk] * len(rows),
            "game_id": [f"{season}_{wk:02d}_{u}" for u, *_ in rows],
            "unit": [r[0] for r in rows],
            "offense": [f"o{r[0]}" for r in rows],
            "points": [r[1] for r in rows],
            "b00": [r[2] for r in rows],
            "b06": [r[3] for r in rows],
        },
        schema_overrides={"season": pl.Int32, "week": pl.Int32},
    )


MODELS = ("b00", "b06")


def measure(table: pl.DataFrame, **overrides):
    arguments = {"close": 1.0, "pool": (2, 3), "top": 1, "reps": 200, "seed": 1729} | overrides
    return decisions.metrics(
        table, decisions.pairs(table, MODELS, "b00"), "b00", "b06", **arguments
    )


def test_hand_checked_week():
    # Actual order A > B > C. b00 ranks C > B > A (every pair wrong); b06 ranks A > B > C (right).
    table = week(2020, 1, [("A", 10.0, 1.0, 9.0), ("B", 5.0, 2.0, 8.0), ("C", 0.0, 3.0, 7.0)])
    m = measure(table)
    assert m["pairs"] == 3 and m["actualTies"] == 0
    assert m["accuracy"] == {"b00": 0.0, "b06": 100.0}
    assert m["deltaPp"] == 100.0
    assert m["changed"]["count"] == 3
    # Gains: A-B 10-5, A-C 10-0, B-C 5-0.
    assert m["pointsFromChanges"]["total"] == 20.0
    assert m["pointsFromChanges"]["perChangedDecision"] == pytest.approx(20 / 3, abs=1e-4)
    assert m["worstCase"]["singleDecision"] == 5.0
    assert m["spearmanWithinWeek"] == {"b00": -1.0, "b06": 1.0}
    # Top-1: b00 starts C (0 points), b06 starts A (10).
    assert m["top1"] == {"b00": 0.0, "b06": 10.0, "deltaPerWeek": 10.0}


def test_ties_actual_excluded_and_forecast_ties_are_half():
    table = week(2020, 1, [("A", 4.0, 2.0, 2.0), ("B", 4.0, 1.0, 1.0), ("C", 0.0, 1.0, 3.0)])
    m = measure(table)
    # A-B: actual tie, excluded. A-C: b00 picks A (right), b06 picks C (wrong).
    # B-C: b00 forecast tie (0.5), b06 picks C (wrong).
    assert m["actualTies"] == 1
    assert m["accuracy"]["b00"] == pytest.approx(75.0)
    assert m["accuracy"]["b06"] == pytest.approx(0.0)
    # A forecast tie is worth the mean of the two units: B-C changes from (4+0)/2 to 0.
    assert m["pointsFromChanges"]["total"] == pytest.approx(-4.0 + -2.0)


def test_close_and_waiver_pool_subgroups():
    table = week(
        2020,
        1,
        [("A", 9.0, 9.0, 9.0), ("B", 1.0, 8.5, 5.0), ("C", 6.0, 3.0, 6.0), ("D", 2.0, 2.0, 1.0)],
    )
    m = measure(table, pool=(2, 3))
    # Close by b00 (< 1 point apart): only A-B.
    assert m["close"]["pairs"] == 1
    # b00 ranks A 1, B 2, C 3, D 4: the pool (ranks 2-3) holds B-C only; b00 picks B, b06 picks C.
    assert m["waiverPool"]["pairs"] == 1
    assert m["waiverPool"]["b00"] == 0.0 and m["waiverPool"]["b06"] == 100.0


def synthetic(signal: float, seed: int, weeks: int = 40, teams: int = 24) -> pl.DataFrame:
    """A true unit effect; b06 sees `signal` of it, b00 none."""
    rng = np.random.default_rng(seed)
    parts = []
    for wk in range(1, weeks + 1):
        truth = rng.normal(0, 2, teams)
        actual = truth + rng.normal(0, 5, teams)
        b00 = 7 + rng.normal(0, 0.01, teams)
        b06 = 7 + signal * truth + rng.normal(0, 0.01, teams)
        parts.append(
            week(2020, wk, [(f"U{i:02d}", actual[i], b00[i], b06[i]) for i in range(teams)])
        )
    return pl.concat(parts)


def test_a_real_effect_shows_and_noise_does_not():
    real = measure(synthetic(1.0, seed=3), reps=300)
    assert real["deltaPp"] > 5 and real["deltaPp95"][0] > 0
    assert real["pointsFromChanges"]["total"] > 0
    noise = [measure(synthetic(0.0, seed=s), reps=300) for s in range(4)]
    assert all(abs(n["deltaPp"]) < 3 for n in noise)


def test_bootstrap_is_deterministic_and_seeded():
    table = synthetic(0.5, seed=9, weeks=12)
    a, b = measure(table, seed=7), measure(table, seed=7)
    c = measure(table, seed=8)
    assert a == b
    assert a["deltaPp"] == c["deltaPp"] and a["deltaPp95"] != c["deltaPp95"]


def test_decision_rule():
    def period(delta: float, points: float):
        return {"deltaPp": delta, "pointsFromChanges": {"total": points}}

    ok = {"development": period(2.0, 5), "validation": period(3.0, 1), "holdout": period(1.9, 2)}
    assert decisions.decide(ok, 1.8)[0] == "PROMISING"
    lost = ok | {"validation": period(3.0, -1)}
    assert decisions.decide(lost, 1.8)[0] == "INCONCLUSIVE"
    weak = {k: period(1.0, 9) for k in ok}
    assert decisions.decide(weak, 1.8)[0] == "NOT_USEFUL"
    mixed = weak | {"holdout": period(2.5, 1)}
    assert decisions.decide(mixed, 1.8)[0] == "INCONCLUSIVE"


def forecast_rows(game: str, a: str, b: str, pa: float, pb: float):
    return [
        {
            "game_id": game,
            "offense": a,
            "position": "DST",
            "points": pa,
            "status": "valid",
            "season": 2020,
            "week": 1,
            "b00": 5.0,
            "b06": 6.0,
        },
        {
            "game_id": game,
            "offense": b,
            "position": "DST",
            "points": pb,
            "status": "valid",
            "season": 2020,
            "week": 1,
            "b00": 4.0,
            "b06": 3.0,
        },
        {
            "game_id": game,
            "offense": a,
            "position": "WR",
            "points": 30.0,
            "status": "valid",
            "season": 2020,
            "week": 1,
            "b00": 25.0,
            "b06": 26.0,
        },
    ]


def observation_rows(game: str, a: str, b: str):
    rows = []
    for off, de in ((a, b), (b, a)):
        # Canonical orientation: a D/ST row studies the offense; the defense is the D/ST scoring.
        rows.append(
            {"game_id": game, "offense": off, "position": "DST", "unit": off, "defense": de}
        )
        rows.append({"game_id": game, "offense": off, "position": "WR", "unit": de, "defense": de})
    return rows


def test_c01_c02_t26_the_dst_forecast_row_is_the_opposing_unit_share_one():
    forecasts = pl.DataFrame(forecast_rows("g1", "KC", "LV", 9.0, -1.0))
    observations = pl.DataFrame(observation_rows("g1", "KC", "LV"))
    table = decisions.units(forecasts, observations, MODELS)
    # Offense KC's D/ST row is LV's D/ST; each unit appears once per game (share 1), and the
    # player-level forecast is the group-level forecast unchanged.
    assert table.select("unit", "offense", "points", "b06").rows() == [
        ("KC", "LV", -1.0, 3.0),
        ("LV", "KC", 9.0, 6.0),
    ]
    assert table.group_by("game_id", "unit").len().get_column("len").to_list() == [1, 1]


def test_t26_an_unmapped_or_mismatched_unit_fails_closed():
    forecasts = pl.DataFrame(forecast_rows("g1", "KC", "LV", 9.0, -1.0))
    observations = pl.DataFrame(observation_rows("g1", "KC", "LV"))
    with pytest.raises(ValueError, match="no canonical D/ST"):
        decisions.units(forecasts, observations.filter(pl.col("offense") != "KC"), MODELS)
    # A D/ST row studied from the wrong side (unit = the D/ST) is refused.
    flipped = observations.with_columns(
        pl.when(pl.col("position") == "DST").then(pl.col("defense")).otherwise("unit").alias("unit")
    )
    with pytest.raises(ValueError, match="not oriented"):
        decisions.units(forecasts, flipped, MODELS)
    # A D/ST credited against its own offense is refused.
    own = observations.with_columns(
        pl.when(pl.col("position") == "DST")
        .then(pl.col("offense"))
        .otherwise("defense")
        .alias("defense")
    )
    with pytest.raises(ValueError, match="not oriented"):
        decisions.units(forecasts, own, MODELS)


def test_common_rows_only():
    forecasts = pl.DataFrame(
        forecast_rows("g1", "KC", "LV", 9.0, -1.0) + forecast_rows("g2", "NE", "NYJ", 1.0, 2.0)
    ).with_columns(
        pl.when(pl.col("offense") == "NE").then(None).otherwise(pl.col("b06")).alias("b06")
    )
    observations = pl.DataFrame(
        observation_rows("g1", "KC", "LV") + observation_rows("g2", "NE", "NYJ")
    )
    table = decisions.units(forecasts, observations, MODELS)
    assert sorted(table.get_column("unit").to_list()) == ["KC", "LV", "NE"]


def test_the_declared_rule_is_the_one_in_the_config():
    config = json.loads((ROOT / "config/dvp/sitstart.json").read_text())
    assert config["scope"]["positions"] == ["DST"]
    assert config["practicalMinimumAccuracyPp"] == 1.8
    rho = 0.1448
    after = math.sqrt(1 - 0.99**2 * (1 - rho**2))
    implied = (math.asin(after) - math.asin(rho)) / math.pi * 100
    assert round(implied, 1) == config["practicalMinimumAccuracyPp"]
    assert config["write_to_production"] is False
