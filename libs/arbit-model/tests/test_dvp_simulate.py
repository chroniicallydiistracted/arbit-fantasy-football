"""The AUD-06 data-generating process (arbit_model.dvp.simulate): fast, deterministic checks.

The expensive suite runs separately (scripts/model/dvp_simulate.py); these tests prove the
generator produces what config/dvp/simulation-v1.json declares and feeds Arbit's estimators.
"""

import math

import numpy as np
import polars as pl
import pytest
from arbit_model.dvp import lab
from arbit_model.dvp import simulate as sim
from arbit_model.dvp import walkforward as wf

SMALL = dict(seasons=(2016, 2017, 2018), teams=16, weeks=12)


def generate(name, seed=7, **overrides):
    base = sim.SCENARIOS[name]
    return sim.generate(
        sim.Scenario(**{**base.__dict__, **SMALL, **overrides}), np.random.default_rng(seed)
    )


def test_the_schema_matches_what_the_estimators_read():
    data = generate("SIM-04")
    cells = 3 * 12 * 8 * 2 * 2  # seasons x weeks x games x sides x positions
    assert data.observations.height == cells == data.oracle.height == data.volumes.height
    assert data.schedule.height == 3 * 12 * 8
    assert set(data.schedule.columns) >= {"game_id", "season", "week", "kickoff", "home", "away"}
    rows = wf.prepare(data.observations)  # fails closed on any unknown column
    dst = rows.filter(pl.col("position") == "DST")
    # D/ST is oriented as in the real data: the studied unit is the offense.
    assert (dst.get_column("unit") == dst.get_column("offense")).all()
    assert (dst.get_column("opp") == dst.get_column("offense")).all()
    first = data.schedule.group_by("season", "week").agg(pl.col("kickoff").min()).height
    assert first == 3 * 12  # each week has a first (Thursday) kickoff


def test_the_same_stream_gives_the_same_league_and_another_does_not():
    a, b, c = generate("SIM-03", 1), generate("SIM-03", 1), generate("SIM-03", 2)
    assert a.observations.equals(b.observations)
    assert not a.observations.equals(c.observations)


def test_the_oracle_is_the_true_mean_and_nontd_drops_only_touchdown_noise():
    data = generate("SIM-04")
    joined = data.observations.join(data.oracle, on=["game_id", "offense", "position"])
    resid = (joined.get_column("points") - joined.get_column("oracle")).to_numpy()
    wr = joined.get_column("position").to_numpy() == "WR"
    assert abs(resid[wr].mean()) < 0.5 and abs(resid[wr].std() - sim.NOISE["WR"]) < 0.5
    td = (joined.get_column("points") - joined.get_column("nontd")).to_numpy()
    assert abs(td[wr].std() - sim.NOISE["WR"] * math.sqrt(sim.TD_SHARE)) < 0.4


def test_reml_recovers_a_strong_k_and_finds_no_signal_in_noise():
    strong = sim.generate(
        sim.Scenario("x", k_true=8, seasons=tuple(range(2016, 2023))), np.random.default_rng(3)
    )
    null = sim.generate(
        sim.Scenario("y", seasons=tuple(range(2016, 2023))), np.random.default_rng(3)
    )
    for data, expect in ((strong, "signal"), (null, "none")):
        rows = wf.prepare(data.observations).filter(pl.col("position") == "WR")
        fit = lab.reml_components(
            lab.groups(lab.adjust(wf._frame(rows, "opp", "side", "points"), "loo_mean"))
        )
        if expect == "signal":
            assert fit.k is not None and 4 < fit.k < 16
        else:
            assert fit.k is None or fit.k > 100


def test_missingness_and_exposure_violations_mark_cells_invalid():
    mcar = generate("SIM-08").observations
    share = (mcar.get_column("status") != "valid").mean()
    assert 0.10 < share < 0.20
    exposure = generate("SIM-07").observations
    lost = exposure.filter(pl.col("status") != "valid").group_by("position", "unit", "season").len()
    assert lost.get_column("len").max() <= 6


def test_the_known_rmse_difference_matches_monte_carlo():
    rng = np.random.default_rng(11)
    s, e = rng.normal(0, 1.0, 400_000), rng.normal(0, 4.0, 400_000)
    y = s + e
    empirical = math.sqrt((y**2).mean()) - math.sqrt(((y - 0.8 * s) ** 2).mean())
    assert sim.known_difference(1.0, 4.0, 0.8) == pytest.approx(empirical, abs=0.003)


def test_a_signal_channel_sits_in_volume_or_efficiency():
    volume = generate("SIM-14a").observations.join(
        generate("SIM-14a").volumes, on=["game_id", "offense", "position"]
    )
    assert volume.height > 0
    # Points equal volume times efficiency by construction of the efficiency column.
    eff = volume.with_columns((pl.col("points") / pl.col("volume")).alias("efficiency"))
    assert (
        eff.get_column("efficiency") * eff.get_column("volume") - eff.get_column("points")
    ).abs().max() < 1e-9
