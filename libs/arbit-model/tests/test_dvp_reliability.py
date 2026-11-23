"""The v0 split-half arithmetic and its checks: T08-T13, and equality with v0's own code."""

import math
import random
import sys
from pathlib import Path

import polars as pl
import pytest
from arbit_model.dvp import reliability as rel

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/model"))
from ffa_signal_study import field, one, split_half  # noqa: E402


def test_t08_leave_one_out_matches_a_hand_calculation():
    frame = pl.DataFrame({"team": ["A", "A", "A", "B"], "points": [10.0, 20.0, 30.0, 7.0]})
    expected = frame.select(rel.leave_one_out(["team"], "points").alias("e"))["e"].to_list()
    assert expected == [25.0, 20.0, 15.0, None]  # a single game has no baseline, not NaN


def unit_rows(weeks, values, unit="D", season=2025):
    return [
        {"unit": unit, "season": season, "week": w, "v": v}
        for w, v in zip(weeks, values, strict=True)
    ]


def test_t09_halves_follow_nfl_week_parity_not_game_order():
    # A bye in week 6: games in weeks 5 and 7 are both odd weeks.
    frame = pl.DataFrame(unit_rows([1, 2, 3, 4, 5, 7, 8, 9, 10], [1, 2, 3, 4, 5, 7, 8, 9, 10]))
    pairs = rel.halves(frame, ["unit", "season"], "v", min_games=4)
    row = pairs.row(0, named=True)
    assert (row["odd_n"], row["even_n"]) == (5, 4)
    assert row["odd_mean"] == pytest.approx((1 + 3 + 5 + 7 + 9) / 5)


def test_t10_each_half_needs_four_real_games():
    frame = pl.DataFrame(
        unit_rows([1, 2, 3, 4, 5, 6, 8], [1.0] * 7)
        + unit_rows([1, 2, 3, 4, 5, 6, 7, 8], [1.0, 2, None, 4, 5, 6, 7, 8], unit="E")
    )
    pairs = rel.halves(frame, ["unit", "season"], "v", min_games=4)
    assert pairs.height == 0  # D has 3 odd weeks; E's null week 3 is no game


def test_t11_known_values_bounds_and_invalid_inputs():
    k = rel.k_from_r(0.2, 8)
    assert k == pytest.approx(32.0)
    assert rel.single_game(k) == pytest.approx(1 / 33)
    assert rel.weight(8, k) == pytest.approx(0.2)
    assert rel.weight(0, k) == 0.0 and rel.weight(1e9, k) == pytest.approx(1.0)
    assert rel.k_from_r(0.0, 8) is None and rel.k_from_r(-0.1, 8) is None
    assert rel.k_from_r(None, 8) is None and rel.k_from_r(1.0, 8) == 0.0
    assert rel.weight(8, None) is None
    for call in (lambda: rel.k_from_r(0.2, 0), lambda: rel.weight(-1, 5.0)):
        with pytest.raises(ValueError):
            call()
    # v0's WR: r = 0.15766 over halves of 8.2469 games gives 44.06, not the 42.7 of 8-game halves.
    assert rel.k_from_r(0.15766, 8.2469) == pytest.approx(44.06, abs=0.01)
    assert rel.k_from_r(0.15766, 8) == pytest.approx(42.74, abs=0.01)


def test_t12_unequal_halves_follow_the_variance_model():
    k = 30.0
    equal = rel.expected_split_r(8, 8, k)
    assert equal == pytest.approx(8 / 38)
    assert rel.k_from_r(equal, 8) == pytest.approx(k)
    unequal = rel.expected_split_r(9, 7, k)
    assert unequal == pytest.approx(math.sqrt(9 / 39 * 7 / 37))
    assert rel.k_from_r(unequal, 8) != pytest.approx(k)  # the m-averaged shortcut is approximate
    with pytest.raises(ValueError):
        rel.expected_split_r(8, 8, -1)


def synthetic(seed: int, units: int = 120, k: float = 10.0) -> pl.DataFrame:
    rng = random.Random(seed)
    rows = []
    for u in range(units):
        trait = rng.gauss(0, 1)
        for week in range(1, 18):
            if week == 7 + u % 5:
                continue  # a bye
            rows.append(
                {
                    "unit": f"U{u}",
                    "season": 2020 + u % 3,
                    "week": week,
                    "v": trait + rng.gauss(0, math.sqrt(k)),
                }
            )
    return pl.DataFrame(rows)


def test_split_half_equals_v0s_own_function():
    frame = synthetic(7)
    mine = rel.split_half(rel.halves(frame, ["unit", "season"], "v"))
    groups: dict[tuple[str, int], list[dict[str, float]]] = {}
    for row in frame.iter_rows(named=True):
        groups.setdefault((row["unit"], row["season"]), []).append(row)
    theirs = split_half(groups, field("v"), one, 4, True)
    assert mine.units == theirs["unitSeasons"]
    assert round(mine.r or 0, 3) == theirs["splitHalfR"]
    assert round(mine.k or 0, 1) == theirs["gamesForHalfSignal"]
    assert round(mine.season_reliability or 0, 3) == theirs["seasonReliability"]


def test_t13_seeded_resampling_is_deterministic():
    pairs = rel.halves(synthetic(3), ["unit", "season"], "v")
    first = rel.bootstrap(pairs, 200, 1729)
    assert rel.bootstrap(pairs, 200, 1729) == first
    assert rel.bootstrap(pairs, 200, 1730)["pearson95"] != first["pearson95"]
    clustered = rel.bootstrap(pairs, 200, 1729, cluster="season")
    assert clustered["resampled"] == "season" and clustered["pearson95"] is not None


def test_t21_t22_a_real_trait_is_recovered_and_noise_identifies_little():
    trait = rel.split_half(rel.halves(synthetic(11, units=400, k=10.0), ["unit", "season"], "v"))
    assert trait.k is not None and 6 < trait.k < 16
    noise = pl.DataFrame(
        [
            {
                "unit": f"U{u}",
                "season": 2020,
                "week": w,
                "v": random.Random(u * 100 + w).gauss(0, 1),
            }
            for u in range(400)
            for w in range(1, 18)
        ]
    )
    flat = rel.split_half(rel.halves(noise, ["unit", "season"], "v"))
    assert flat.r is not None and abs(flat.r) < 0.15
    assert flat.k is None or flat.k > 50
