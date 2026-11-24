"""Exploratory estimators v2 (owner audit AUD-03) on synthetic seasons with known behavior.

Rolling windows shrink the last m residuals; a window at least as long as the history is B03.
Split-half k is fit on training seasons only. No exploratory column changes a frozen one, uses
data after the cutoff, or consumes the frozen variants' random stream.
"""

import math

import polars as pl
import pytest
from arbit_model.dvp import explore, shadow
from arbit_model.dvp import walkforward as wf
from test_dvp_shadow import setup
from test_dvp_walkforward import POSITIONS


def run(season=2018, extra=True, **kwargs):
    observations, schedule, rows, params = setup(season, **kwargs)
    targets = shadow.scheduled_targets(schedule, season, None, POSITIONS)
    hook = explore.make_extra(rows, season, POSITIONS) if extra else None
    out = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings(), extra=hook)
    return observations, rows, hook, shadow.forecast_only(out, targets)


def test_exploratory_columns_never_change_the_frozen_ones():
    _, _, _, with_extra = run()
    _, _, _, without = run(extra=False)
    assert set(explore.COLUMNS) <= set(with_extra.columns)
    assert with_extra.select(without.columns).equals(without)  # incl. B09's random draws


def test_rolling_windows_shrink_the_last_m_residuals():
    _, _, _, f = run()
    week1 = f.filter(pl.col("week") == 1)
    for column in explore.COLUMNS:
        assert (week1.get_column(column) - week1.get_column("b00")).abs().max() == 0
    short = f.filter(pl.col("n_d").fill_null(0) <= 8)
    assert (short.get_column("b05w8") - short.get_column("b03")).abs().max() < 1e-12
    late = f.filter(pl.col("n_d") > 8)
    assert (late.get_column("b05w8") - late.get_column("b03")).abs().max() > 0  # old games leave
    # A shorter window has fewer games, so its shrinkage leaves it nearer B00 on average.
    distance = {m: (f.get_column(f"b05w{m}") - f.get_column("b00")).abs().mean() for m in (3, 8)}
    assert distance[3] < distance[8]


def test_split_half_k_comes_from_training_seasons_only():
    observations, rows, hook, _ = run()
    later = observations.with_columns(
        pl.when(pl.col("season") >= 2018)
        .then(pl.col("points") * 5)
        .otherwise("points")
        .alias("points")
    )
    k_later = explore.split_half_k(wf.prepare(later), 2018, POSITIONS)
    assert k_later == hook.split_half_k
    assert all(v > 0 for v in hook.split_half_k.values())


def test_with_the_frozen_k_the_split_half_column_is_b03():
    observations, schedule, rows, params = setup()
    targets = shadow.scheduled_targets(schedule, 2018, None, POSITIONS)
    k_same = dict(params.k_dvp)
    swapped = explore.make_extra(rows, 2018, POSITIONS)  # its k is read when it runs
    swapped.split_half_k.clear()
    swapped.split_half_k.update(k_same)
    out = shadow.walk_targets(
        rows, targets, schedule, params, POSITIONS, wf.Settings(), extra=swapped
    ).frame
    assert (out.get_column("b03sh") - out.get_column("b03")).abs().max() < 1e-12


def test_an_unidentified_split_half_k_gives_the_record_no_weight():
    """r <= 0 identifies no k (reliability.k_from_r); the record then earns no weight."""
    observations, schedule, rows, params = setup()
    targets = shadow.scheduled_targets(schedule, 2018, None, POSITIONS)
    hook = explore.make_extra(rows, 2018, POSITIONS)
    hook.split_half_k["WR"] = math.inf
    out = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings(), extra=hook)
    wr = out.frame.filter(pl.col("position") == "WR")
    assert (wr.get_column("b03sh") - wr.get_column("b00")).abs().max() < 1e-9
    dst = out.frame.filter(pl.col("position") == "DST")
    assert (dst.get_column("b03sh") - dst.get_column("b00")).abs().max() > 0


def test_a_hook_that_alters_a_frozen_column_is_refused():
    observations, schedule, rows, params = setup()
    targets = shadow.scheduled_targets(schedule, 2018, range(1, 4), POSITIONS)

    def tamper(forecast, hist, pit, params):
        return forecast.with_columns(pl.col("b06") + 1.0)

    with pytest.raises(Exception, match="EXTRA_CHANGED_FROZEN"):
        shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings(), extra=tamper)
