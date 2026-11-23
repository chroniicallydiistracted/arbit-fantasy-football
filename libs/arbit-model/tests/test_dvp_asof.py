"""What a DvP forecast may know at its cutoff: tests T34-T36, T38 and T39.

The fixture slate (test_dvp_observations): week 1 is Sunday 11 September 2016 (KC 13:00 ET,
OAK 16:05 ET); week 2 opens on Thursday 15 September (OAK at SD) before Sunday's KC at ATL.
"""

from datetime import UTC, datetime

import polars as pl
import pytest
from arbit_model.dvp.asof import (
    Cutoff,
    FrozenForecasts,
    cutoffs,
    evaluation_join,
    features_as_of,
    labels_for,
    league_prior,
)
from arbit_model.dvp.provenance import LineageError
from test_dvp_observations import G1, G2, G3, G4, build


@pytest.fixture(scope="module")
def built():
    return build()


def cutoff_of(built, gid: str, mode: Cutoff) -> datetime:
    table = cutoffs(built.scheduled, mode)
    return table.filter(pl.col("game_id") == gid)["cutoff"][0]


def games_in(view) -> set[str]:
    return set(view.frame["game_id"])


def test_t34_unfinished_in_progress_and_later_games_are_never_features(built):
    assert built.rows.filter(pl.col("game_id") == "2016_03_ATL_SD").height == 0
    # At the late Sunday kickoff, the early Sunday game is still being played.
    late = features_as_of(built.rows, cutoff_of(built, G1, Cutoff.PER_GAME), Cutoff.PER_GAME)
    assert games_in(late) == set()
    monday = datetime(2016, 9, 12, 12, tzinfo=UTC)
    assert games_in(features_as_of(built.rows, monday, Cutoff.PER_GAME)) == {G1, G2}


def test_t35_a_thursday_result_reaches_only_the_per_game_forecast(built):
    preweek = features_as_of(built.rows, cutoff_of(built, G3, Cutoff.PREWEEK), Cutoff.PREWEEK)
    per_game = features_as_of(built.rows, cutoff_of(built, G3, Cutoff.PER_GAME), Cutoff.PER_GAME)
    assert cutoff_of(built, G3, Cutoff.PREWEEK) == datetime(2016, 9, 16, 0, 25, tzinfo=UTC)
    assert games_in(preweek) == {G1, G2}
    assert games_in(per_game) == {G1, G2, G4}


def test_t36_features_and_labels_stay_apart_until_forecasts_are_frozen(built):
    cutoff = cutoff_of(built, G3, Cutoff.PREWEEK)
    view = features_as_of(built.rows, cutoff, Cutoff.PREWEEK)
    assert (view.frame["kickoff"] < cutoff).all() and (view.frame["available_at"] <= cutoff).all()
    labels = labels_for(built.rows, [G3])
    forecasts = labels.frame.select("game_id", "offense", "position").with_columns(
        pl.lit(cutoff).alias("feature_as_of"), pl.lit(10.0).alias("forecast")
    )
    joined = evaluation_join(FrozenForecasts(cutoff, forecasts), labels)
    assert joined.height == labels.frame.height
    with pytest.raises(LineageError, match="LABEL_IN_FORECAST"):
        evaluation_join(
            FrozenForecasts(cutoff, forecasts.with_columns(pl.lit(1.0).alias("points"))), labels
        )
    with pytest.raises(LineageError, match="FORECAST_NOT_FROZEN"):
        evaluation_join(FrozenForecasts(datetime(2016, 9, 1, tzinfo=UTC), forecasts), labels)
    with pytest.raises(LineageError, match="UNMATCHED_ROWS"):
        evaluation_join(FrozenForecasts(cutoff, forecasts.head(3)), labels)
    with pytest.raises(LineageError, match="DUPLICATE_KEY"):
        evaluation_join(FrozenForecasts(cutoff, pl.concat([forecasts, forecasts])), labels)
    late = forecasts.with_columns(pl.lit(datetime(2016, 9, 19, tzinfo=UTC)).alias("feature_as_of"))
    with pytest.raises(LineageError, match="FEATURE_AFTER_KICKOFF"):
        evaluation_join(FrozenForecasts(datetime(2016, 9, 20, tzinfo=UTC), late), labels)


def test_t38_a_prior_comes_only_from_observed_ffa_actuals(built):
    view = features_as_of(built.rows, datetime(2016, 9, 13, tzinfo=UTC), Cutoff.PREWEEK)
    # Valid week 1 QB cells: LV 20.5, ATL -1.66, LAC 18.0, KC 22.0.
    assert league_prior(view, "QB") == pytest.approx((20.5 - 1.66 + 18.0 + 22.0) / 4)
    for source_type, kind in (
        ("ARBIT_MODEL_OUTPUT", "generated"),
        ("EXTERNAL_FANTASY_PROJECTION_FORBIDDEN", "observed"),
    ):
        seeded = view.frame.with_columns(
            pl.when(pl.col("offense") == "KC")
            .then(pl.lit(source_type))
            .otherwise(pl.col("source_type"))
            .alias("source_type"),
            pl.when(pl.col("offense") == "KC")
            .then(pl.lit(kind))
            .otherwise(pl.col("observed_or_generated"))
            .alias("observed_or_generated"),
        )
        with pytest.raises(LineageError, match="PRIOR_FROM_NON_ACTUAL"):
            league_prior(type(view)(view.cutoff, view.mode, seeded), "QB")


def test_t39_later_corrections_and_results_never_change_an_earlier_view(built):
    cutoff = cutoff_of(built, G3, Cutoff.PREWEEK)
    before = features_as_of(built.rows, cutoff, Cutoff.PREWEEK).frame
    later = built.rows.filter(pl.col("available_at") > cutoff)
    altered = pl.concat(
        [
            built.rows.filter(pl.col("available_at") <= cutoff),
            later.with_columns(pl.col("points") * 10),
            # A week 1 correction published after the cutoff.
            built.rows.filter(pl.col("game_id") == G1).with_columns(
                pl.col("points") + 50,
                pl.lit(datetime(2016, 9, 20, tzinfo=UTC)).alias("available_at"),
            ),
        ]
    )
    after = features_as_of(altered, cutoff, Cutoff.PREWEEK).frame
    assert after.sort("game_id", "offense", "position").equals(
        before.sort("game_id", "offense", "position")
    )
    # A correction available before the cutoff does count (the test can fail).
    early = altered.with_columns(
        pl.when(pl.col("game_id") == G2).then(pl.col("points") + 1).otherwise(pl.col("points"))
    )
    changed = features_as_of(early, cutoff, Cutoff.PREWEEK).frame
    assert not changed.sort("game_id", "offense", "position").equals(
        before.sort("game_id", "offense", "position")
    )
