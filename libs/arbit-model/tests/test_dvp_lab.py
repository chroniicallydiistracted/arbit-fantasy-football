"""The M3-3 reliability lab (Phase 2): estimators on synthetic data with known answers.

T12 unequal halves, T13 determinism, T14 variance-component boundaries and non-convergence,
T23 a trait that shifts mid-season, T24 permutation nulls, T28 one outlier's influence.
"""

import math

import numpy as np
import polars as pl
import pytest
from arbit_model.dvp import lab, svg


def synthetic(
    units: int = 160,
    seasons: int = 4,
    games: int | list[int] = 16,
    tau: float = 1.0,
    sigma: float = 3.0,
    seed: int = 7,
    shift: bool = False,
) -> pl.DataFrame:
    """Unit-seasons with a known effect (sd tau) and game noise (sd sigma). With `shift`, the
    effect is redrawn halfway through each season."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in range(2016, 2016 + seasons):
        for u in range(units // seasons):
            n = games if isinstance(games, int) else games[u % len(games)]
            first, second = rng.normal(0, tau), rng.normal(0, tau)
            for week in range(1, n + 1):
                effect = second if shift and week > n // 2 else first
                rows.append(
                    {
                        "season": season,
                        "week": week,
                        "game_id": f"{season}_{week:02d}_{u}",
                        "entity": f"U{u:03d}",
                        "faced": f"F{(u + week) % 32:02d}",
                        "points": 20 + effect + rng.normal(0, sigma),
                        "home": week % 2 == 0,
                    }
                )
    return pl.DataFrame(rows).sort("entity", "season", "week")


def test_adjustments_match_their_definitions():
    frame = pl.DataFrame(
        {
            "season": [2020] * 4,
            "week": [1, 2, 3, 4],
            "game_id": ["a", "b", "c", "d"],
            "entity": ["X", "X", "Y", "Y"],
            "faced": ["O", "O", "O", "P"],
            "points": [10.0, 20.0, 60.0, 5.0],
            "home": [True, False, True, False],
        }
    )
    loo = lab.adjust(frame, "loo_mean").get_column("value").to_list()
    # O's other games: (20 + 60) / 2, (10 + 60) / 2, (10 + 20) / 2; P has no other game.
    assert loo == [10 - 40, 20 - 35, 60 - 15, None]
    median = lab.adjust(frame, "loo_median").get_column("value").to_list()
    assert median == [10 - 40, 20 - 35, 60 - 15, None]
    shrunk_zero = lab.adjust(frame, "loo_shrunk", k_faced=0.0).get_column("value").to_list()
    assert shrunk_zero[:3] == loo[:3]
    # With no other game, the shrunk expectation is the season mean.
    assert shrunk_zero[3] == pytest.approx(5 - 23.75)
    season = lab.adjust(frame, "season").get_column("value")
    assert season.sum() == pytest.approx(0)
    with pytest.raises(ValueError):
        lab.adjust(frame, "loo_shrunk")


def test_split_assignments_follow_week_order_not_row_index():
    frame = lab.adjust(synthetic(units=4, seasons=1, games=14), "none")
    g = lab.groups(frame)
    first = slice(0, 14)
    assert list(lab.assignment(g, "calendar")[first]) == [0, 1] * 7  # odd weeks are half A
    assert list(lab.assignment(g, "alternating")[first]) == [0, 1] * 7
    assert list(lab.assignment(g, "chronological")[first]) == [0] * 7 + [1] * 7
    assert list(lab.assignment(g, "first6_next6")[first]) == [0] * 6 + [1] * 6 + [-1, -1]
    random = lab.random_assignment(g, np.random.default_rng(1))
    assert (random[first] == 0).sum() == 7  # balanced


def test_t12_reml_uses_each_units_own_game_count():
    # Seasons of 8, 12 and 17 games with k = 9 (tau 1, sigma 3).
    frame = lab.adjust(
        synthetic(units=900, seasons=3, games=[8, 12, 17], tau=1.0, sigma=3.0, seed=3), "none"
    )
    g = lab.groups(frame)
    reml = lab.reml_components(g)
    moments = lab.anova_components(g)
    assert reml.converged and not reml.boundary
    assert reml.k == pytest.approx(9.0, rel=0.25)
    assert moments.k == pytest.approx(9.0, rel=0.3)
    # The model's split correlation with unequal halves is below the equal-halves shortcut's.
    sizes_a, sizes_b = np.array([4.0, 6.0, 8.0]), np.array([4.0, 6.0, 9.0])
    m = float(((sizes_a + sizes_b) / 2).mean())
    assert lab.implied_split_r(sizes_a, sizes_b, 9.0) < m / (m + 9.0)


def test_t13_seeded_resampling_is_reproducible_and_seed_dependent():
    frame = lab.adjust(synthetic(), "none")
    g = lab.groups(frame)
    assert lab.random_splits(g, 25, 1729) == lab.random_splits(g, 25, 1729)
    assert lab.random_splits(g, 25, 1729) != lab.random_splits(g, 25, 1730)
    one = lab.permutation_null(frame, 25, 1729)
    two = lab.permutation_null(frame, 25, 1729)
    assert np.array_equal(one.pop("_values"), two.pop("_values")) and one == two
    result = lab.split(g, lab.assignment(g, "calendar"))
    seasons = np.asarray([g.keys[i][1] for i in result.unit_index])
    assert lab.cluster_bootstrap(result, seasons, 50, 5) == lab.cluster_bootstrap(
        result, seasons, 50, 5
    )
    assert lab.bootstrap_components(g, 20, 5, lab.anova_components) == lab.bootstrap_components(
        g, 20, 5, lab.anova_components
    )


def test_t14_equal_group_means_are_a_boundary_estimate_not_an_effect():
    # Every unit-season holds the same values in a different order: no between-unit variance.
    base = [12.0, 3.0, 25.0, 8.0, 17.0, 30.0, 1.0, 20.0]
    rows = [
        {
            "season": 2020,
            "week": w + 1,
            "game_id": f"{u}-{w}",
            "entity": f"U{u:02d}",
            "faced": "F",
            "points": base[(w + u) % 8],
            "home": True,
        }
        for u in range(40)
        for w in range(8)
    ]
    g = lab.groups(lab.adjust(pl.DataFrame(rows), "none"))
    for fit in (lab.reml_components(g), lab.anova_components(g)):
        assert fit.boundary and fit.k is None and fit.tau2 == 0.0


def test_t14_pure_noise_never_yields_a_credible_effect():
    for seed in (11, 12, 13, 14):
        g = lab.groups(lab.adjust(synthetic(tau=0.0, sigma=3.0, seed=seed), "none"))
        reml = lab.reml_components(g)
        # Either the boundary, or a k so large one season's games carry almost nothing.
        assert reml.boundary or (reml.k is not None and reml.k > 50)
        assert reml.converged


def test_t14_a_maximum_at_the_grid_edge_is_flagged_unconverged():
    # No noise within unit-seasons: lambda runs off the top of the grid.
    rows = [
        {
            "season": 2020,
            "week": w,
            "game_id": f"{u}{w}",
            "entity": f"U{u}",
            "faced": "F",
            "points": float(u),
            "home": True,
        }
        for u in range(30)
        for w in range(1, 9)
    ]
    g = lab.groups(lab.adjust(pl.DataFrame(rows), "none"))
    reml = lab.reml_components(g)
    assert not reml.converged and not reml.boundary


def test_t23_a_mid_season_shift_is_seen_by_halves_and_lags_not_by_odd_even():
    frame = lab.adjust(
        synthetic(units=400, seasons=4, games=16, tau=2.0, sigma=2.0, shift=True), "none"
    )
    g = lab.groups(frame)
    odd_even = lab.split(g, lab.assignment(g, "calendar"))
    halves = lab.split(g, lab.assignment(g, "chronological"))
    assert odd_even.r is not None and halves.r is not None
    assert odd_even.r > 0.4 and abs(halves.r) < 0.2
    lags = lab.lag_profile(g)["bins"]
    assert lags["1-2"]["reliability"] > 0.3 and abs(lags["13-17"]["reliability"]) < 0.1
    stable = lab.lag_profile(
        lab.groups(lab.adjust(synthetic(units=400, tau=2.0, sigma=2.0), "none"))
    )
    assert abs(stable["bins"]["1-2"]["reliability"] - stable["bins"]["9-10"]["reliability"]) < 0.1


def test_t24_permutation_nulls_center_on_zero_and_reject_only_real_signal():
    signal = lab.adjust(synthetic(units=320, seasons=10, tau=1.5, sigma=3.0), "none")
    noise = lab.adjust(synthetic(units=320, seasons=10, tau=0.0, sigma=3.0, seed=9), "none")
    for seed in (1, 2, 3):
        null = lab.permutation_null(signal, 200, seed)
        assert null["pValue"] < 0.01
        assert null["null"]["p97_5"] < null["observed"]
    # Shuffling within a week keeps each season's level, so a season-wide effect stays in the
    # null. On season-centered values it sits just below zero: within a season the shuffled halves
    # share fixed totals, about -1/31 for 32 units.
    centered = lab.adjust(synthetic(units=320, seasons=10, tau=1.5, sigma=3.0), "season")
    for seed in (1, 2, 3):
        assert -0.05 < lab.permutation_null(centered, 200, seed)["null"]["mean"] < 0.01
    pure = lab.permutation_null(noise, 200, 1)
    assert pure["pValue"] > 0.01


def test_t28_one_extreme_unit_season_is_found_and_its_effect_measured():
    frame = lab.adjust(synthetic(units=120, seasons=3, tau=0.5, sigma=3.0), "none")
    # Make one unit-season extreme in both halves.
    frame = frame.with_columns(
        pl.when((pl.col("entity") == "U007") & (pl.col("season") == 2017))
        .then(pl.col("value") + 40)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    g = lab.groups(frame)
    result = lab.split(g, lab.assignment(g, "calendar"))
    influence = lab.influence(result)
    assert g.keys[influence["worstUnit"]] == ("U007", 2017)
    assert influence["maxAbsChange"] > 0.2
    trimmed = lab.trim(frame, 3.0)
    assert trimmed.height < frame.height


def test_carryover_and_rolling_windows_on_a_persistent_trait():
    rng = np.random.default_rng(4)
    rows = []
    for u in range(32):
        trait = rng.normal(0, 2)
        for season in range(2016, 2026):
            for week in range(1, 17):
                rows.append(
                    {
                        "season": season,
                        "week": week,
                        "game_id": f"{season}{week}{u}",
                        "entity": f"U{u}",
                        "faced": "F",
                        "points": trait + rng.normal(0, 3),
                        "home": True,
                    }
                )
    frame = lab.adjust(pl.DataFrame(rows), "none")
    summary = lab.carryover_summary(lab.carryover(frame))
    assert summary["pairs"] == 32 * 9 and summary["pearson"] > 0.5
    assert summary["cvMseDecay"] < summary["cvMseReset"]
    g = lab.groups(frame)
    k = lab.reml_components(g).k
    window = lab.rolling_window(g, 5)
    assert window["pearson"] == pytest.approx(lab.implied_window_r(k, 5), abs=0.08)
    assert lab.implied_window_r(None, 5) is None


def test_joint_orderings_and_component_bootstrap_are_bounded():
    strong = lab.adjust(synthetic(units=320, seasons=10, tau=2.0, sigma=3.0, seed=1), "none")
    weak = lab.adjust(synthetic(units=320, seasons=10, tau=0.5, sigma=3.0, seed=2), "none")
    results, seasons = {}, {}
    for name, frame in (("A", strong), ("B", weak)):
        g = lab.groups(frame)
        results[name] = lab.split(g, lab.assignment(g, "calendar"))
        seasons[name] = np.asarray([g.keys[i][1] for i in results[name].unit_index])
    order = lab.joint_orderings(results, seasons, 100, 3)
    assert order["pKLower"]["A<B"] > 0.95
    boot = lab.bootstrap_components(lab.groups(strong), 30, 3, lab.reml_components)
    assert boot["k95"][0] < boot["k95"][1] and 0 <= boot["boundaryShare"] <= 1


def test_svg_plots_are_deterministic_and_titled():
    one = svg.scatter(
        "QB", [1.0, 2.0, 3.0], [1.5, 2.0, 2.5], color="#000000", xlabel="x", ylabel="y", note="n"
    )
    two = svg.scatter(
        "QB", [1.0, 2.0, 3.0], [1.5, 2.0, 2.5], color="#000000", xlabel="x", ylabel="y", note="n"
    )
    assert one == two and "<title>QB</title>" in one and "fill='#ffffff'" in one
    forest = svg.forest("k", [("QB", "QB", 22.0, 15.0, None)], xlabel="k", xlim=(2, 1000), note="")
    assert "polygon" in forest  # the open-ended interval's arrow
    assert math.isfinite(
        len(svg.histograms("n", [("QB", "QB", [0.0, 0.1, -0.1], 0.3)], xlabel="r", note=""))
    )


def test_t13_rank_agreement_does_not_depend_on_row_order():
    frame = synthetic(units=64, seasons=2, tau=1.0, sigma=3.0)
    # Round to create ties among unit-season means.
    frame = frame.with_columns(pl.col("points").round(0))
    raw, adjusted = lab.adjust(frame, "none"), lab.adjust(frame, "season")
    forward = lab.rank_agreement(raw, adjusted)
    backward = lab.rank_agreement(
        raw.reverse(), adjusted.sample(fraction=1.0, shuffle=True, seed=3)
    )
    assert forward == backward
