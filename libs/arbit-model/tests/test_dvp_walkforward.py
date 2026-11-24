"""M3-3 Phase 3 walk-forward: leakage and behavior on synthetic seasons with known effects.

T15 features only before the cutoff, T16 future changes leave earlier forecasts alone, T17 a game's
own result never reaches its forecast, T18 fold parameters come from earlier seasons, T19 every
variant covers the same rows, T20 forecasts frozen before labels, T21/T22 a real defense effect
helps and pure noise doesn't, T24 placebos give no uplift, T25 cold starts, B10 per-game cutoffs,
B11 a planted projection fails closed.
"""

from datetime import UTC, datetime, timedelta
from functools import cache

import numpy as np
import polars as pl
import pytest
from arbit_model.dvp import asof
from arbit_model.dvp import walkforward as wf
from arbit_model.dvp.provenance import LineageError

TEAMS = [f"T{i:02d}" for i in range(16)]
POSITIONS = ("WR", "DST")


def season_data(
    seasons=(2016, 2017, 2018, 2019),
    weeks: int = 14,
    defense_sd: float = 4.0,
    noise_sd: float = 10.0,
    seed: int = 1,
):
    """Every team plays every week; the first game of each week is on Thursday night."""
    rng = np.random.default_rng(seed)
    rows, games = [], []
    for season in seasons:
        offense = dict(zip(TEAMS, rng.normal(0, 4, len(TEAMS)), strict=True))
        defense = dict(zip(TEAMS, rng.normal(0, defense_sd, len(TEAMS)), strict=True))
        vulnerability = dict(zip(TEAMS, rng.normal(0, 2.5, len(TEAMS)), strict=True))
        sunday = datetime(season, 9, 11, 17, tzinfo=UTC)
        for week in range(1, weeks + 1):
            order = rng.permutation(len(TEAMS))
            for g in range(len(TEAMS) // 2):
                home, away = TEAMS[order[2 * g]], TEAMS[order[2 * g + 1]]
                kickoff = sunday + timedelta(days=7 * (week - 1))
                if g == 0:
                    kickoff -= timedelta(days=3, hours=-7)  # Thursday 00:00 UTC
                game_id = f"{season}_{week:02d}_{away}_{home}"
                available = datetime(
                    kickoff.year, kickoff.month, kickoff.day, 12, tzinfo=UTC
                ) + timedelta(days=1)
                games.append(
                    {"game_id": game_id, "season": season, "week": week, "kickoff": kickoff}
                )
                for off, de in ((home, away), (away, home)):
                    base = {
                        "game_id": game_id,
                        "season": season,
                        "week": week,
                        "kickoff": kickoff,
                        "available_at": available,
                        "offense": off,
                        "defense": de,
                        "status": "valid",
                        "source_type": "FFA_ACTUAL_FINAL",
                        "observed_or_generated": "observed",
                    }
                    wr = 30 + offense[off] + defense[de] + rng.normal(0, noise_sd)
                    dst = 6 + vulnerability[off] + rng.normal(0, 5)
                    rows.append(base | {"position": "WR", "points": wr})
                    rows.append(base | {"position": "DST", "points": dst})
    return pl.DataFrame(rows), pl.DataFrame(games)


def forecast(observations, schedule, season, settings=None):
    rows = wf.prepare(observations)
    params = wf.fit_fold(rows, season, POSITIONS)
    frozen = wf.walk(rows, schedule, params, POSITIONS, settings or wf.Settings())
    return rows, params, frozen


def variant_columns(frame):
    return [c for c in frame.columns if c.startswith("b0")]


def test_t25_week_one_is_the_prior_and_nothing_is_missing():
    observations, schedule = season_data()
    rows, params, frozen = forecast(observations, schedule, 2018)
    frame = frozen.frame
    assert frame.select(variant_columns(frame)).null_count().sum_horizontal().item() == 0
    week1 = frame.join(
        rows.select("game_id", "offense", "position", "week"), on=["game_id", "offense", "position"]
    ).filter(pl.col("week") == 1)
    # No opponent history in week 1: every DvP variant equals B00 except B06 (last-season prior).
    for name in ("b01", "b02", "b03", "b04_k8", "b05_h4", "b07"):
        assert (week1.get_column(name) - week1.get_column("b00")).abs().max() < 1e-12
    assert params.training == (2016, 2017)


def test_t16_t17_future_and_own_results_never_change_a_forecast():
    observations, schedule = season_data()
    _, _, before = forecast(observations, schedule, 2018)
    target_week = 8
    changed = observations.with_columns(
        pl.when(
            (pl.col("season") > 2018)
            | ((pl.col("season") == 2018) & (pl.col("week") >= target_week))
        )
        .then(pl.col("points") + 50)
        .otherwise(pl.col("points"))
        .alias("points")
    )
    _, _, after = forecast(changed, schedule, 2018)
    keys = ["game_id", "offense", "position"]
    weeks = observations.select(*keys, "week")
    a = before.frame.join(weeks, on=keys).filter(pl.col("week") <= target_week).sort(keys)
    b = after.frame.join(weeks, on=keys).filter(pl.col("week") <= target_week).sort(keys)
    columns = variant_columns(a)
    assert a.select(columns).equals(b.select(columns))
    assert a.height > 0


def test_t15_a_thursday_result_reaches_sunday_only_under_per_game_cutoffs():
    observations, schedule = season_data()
    thursday = (
        schedule.filter((pl.col("season") == 2018) & (pl.col("week") == 6))
        .sort("kickoff")
        .row(0, named=True)
    )
    bumped = observations.with_columns(
        pl.when(pl.col("game_id") == thursday["game_id"])
        .then(pl.col("points") + 80)
        .otherwise(pl.col("points"))
        .alias("points")
    )
    keys = ["game_id", "offense", "position"]
    sunday = observations.filter(
        (pl.col("season") == 2018)
        & (pl.col("week") == 6)
        & (pl.col("game_id") != thursday["game_id"])
    ).select(keys)
    for mode, should_change in ((asof.Cutoff.PREWEEK, False), (asof.Cutoff.PER_GAME, True)):
        settings = wf.Settings(mode=mode)
        _, _, before = forecast(observations, schedule, 2018, settings)
        _, _, after = forecast(bumped, schedule, 2018, settings)
        a = before.frame.join(sunday, on=keys).sort(keys)
        b = after.frame.join(sunday, on=keys).sort(keys)
        differs = not a.select(variant_columns(a)).equals(b.select(variant_columns(b)))
        assert differs is should_change, mode


def test_t18_fold_parameters_come_from_earlier_seasons_only():
    observations, _ = season_data()
    rows = wf.prepare(observations)
    later = wf.prepare(
        observations.with_columns(
            pl.when(pl.col("season") >= 2018)
            .then(pl.col("points") * 3)
            .otherwise(pl.col("points"))
            .alias("points")
        )
    )
    assert wf.fit_fold(rows, 2018, POSITIONS) == wf.fit_fold(later, 2018, POSITIONS)
    with pytest.raises(ValueError):
        wf.fit_fold(rows, 2016, POSITIONS)
    assert (
        wf.check_stage(
            "development",
            [2017, 2018],
            {"development": [2016, 2017, 2018], "validation": [2024], "holdout": [2025]},
        )
        is None
    )
    with pytest.raises(ValueError, match="holdout"):
        wf.check_stage(
            "validation", [2025], {"development": [2016], "validation": [2024], "holdout": [2025]}
        )
    with pytest.raises(ValueError, match="not in"):
        wf.check_stage(
            "development",
            [2024],
            {"development": [2016, 2017], "validation": [2024], "holdout": [2025]},
        )


def test_t19_t20_every_variant_covers_the_same_rows_and_labels_join_only_once_frozen():
    observations, schedule = season_data()
    rows, _, frozen = forecast(observations, schedule, 2018)
    assert not asof.LABEL_COLUMNS & set(frozen.frame.columns)
    joined = wf.evaluate(frozen, rows, 2018)
    assert joined.height == rows.filter(pl.col("season") == 2018).height
    assert joined.select(variant_columns(joined)).null_count().sum_horizontal().item() == 0


@cache
def deltas(defense_sd, seed):
    observations, schedule = season_data(
        seasons=(2016, 2017, 2018, 2019), defense_sd=defense_sd, seed=seed
    )
    rows = wf.prepare(observations)
    joined = []
    for season in (2018, 2019):
        params = wf.fit_fold(rows, season, POSITIONS)
        joined.append(
            wf.evaluate(wf.walk(rows, schedule, params, POSITIONS, wf.Settings()), rows, season)
        )
    frame = pl.concat(joined).filter(pl.col("position") == "WR")
    return wf.metrics(
        frame,
        ["b02", "b03", "b09_shuffle", "b09_noise", "b09_lastopp"],
        block="season",
        reps=50,
        seed=1,
    )


def test_t21_a_real_defense_effect_improves_on_the_offense_only_baseline():
    result = deltas(defense_sd=4.0, seed=3)
    assert result["b03"]["deltaRmse"] < 0


def test_t22_pure_noise_defenses_do_not_improve_on_the_baseline():
    noise = deltas(defense_sd=0.0, seed=5)
    assert noise["b03"]["relativeDelta"] > -0.005  # shrinkage doesn't invent signal
    assert noise["b02"]["deltaRmse"] > 0  # unshrunk noise hurts


def test_t24_placebo_opponents_give_no_uplift_where_the_real_one_does():
    signal = deltas(defense_sd=4.0, seed=3)
    assert signal["b03"]["deltaRmse"] < 0
    for control in ("b09_shuffle", "b09_noise", "b09_lastopp"):
        assert signal[control]["relativeDelta"] > -0.005, control


def test_b11_a_planted_projection_fails_closed():
    observations, _ = season_data(seasons=(2016, 2017))
    with pytest.raises(LineageError, match="UNKNOWN_COLUMN"):
        wf.prepare(observations.with_columns(pl.lit(25.0).alias("projected_points")))
    with pytest.raises(LineageError, match="UNKNOWN_COLUMN"):
        wf.prepare(observations.with_columns(pl.lit(25.0).alias("opponent_expected")))


def test_t13_forecasts_and_metrics_are_reproducible():
    observations, schedule = season_data()
    _, _, one = forecast(observations, schedule, 2018)
    _, _, two = forecast(observations, schedule, 2018)
    keys = ["game_id", "offense", "position"]
    assert (
        one.frame.drop("feature_as_of")
        .sort(keys)
        .equals(two.frame.drop("feature_as_of").sort(keys))
    )
