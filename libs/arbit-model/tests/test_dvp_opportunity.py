"""Opportunity volume and scoring efficiency (owner audit AUD-02): admission, volumes, coverage,
reconciliation and the forward predictors, on small fixtures with known answers."""

import numpy as np
import polars as pl
import pytest
from arbit_model.dvp import explore, shadow
from arbit_model.dvp import opportunity as op
from arbit_model.dvp import walkforward as wf
from arbit_model.dvp.provenance import LineageError
from test_dvp_shadow import with_teams
from test_dvp_walkforward import POSITIONS, season_data

PLAYER_SCHEMA = [
    *op.SOURCES_V2["nflverse.stats_player"].used,
    "fantasy_points",
    "fantasy_points_ppr",
]


def players(**overrides) -> pl.DataFrame:
    base = {
        "game_id": ["g1"] * 5 + ["g2"],
        "season": [2020] * 6,
        "week": [1] * 5 + [19],
        "season_type": ["REG"] * 5 + ["POST"],
        "team": ["OAK", "OAK", "OAK", "OAK", "OAK", "OAK"],
        "player_id": ["qb", "fb", "wr", "te", "k", "wr"],
        "position": ["QB", "FB", "WR", "TE", "K", "WR"],
        "attempts": [30, 0, 0, 0, 0, 0],
        "sacks_suffered": [2, 0, 0, 0, 0, 0],
        "carries": [3, 10, 1, 0, 0, 0],
        "targets": [0, 4, 9, 0, 0, 12],
        "receptions": [0, 3, 6, 0, 0, 8],
        "fg_att": [0, 0, 0, 0, 2, 0],
        "pat_att": [0, 0, 0, 0, 3, 0],
        "fantasy_points": [20.0, 8.0, 12.0, 0.0, 9.0, 15.0],
        "fantasy_points_ppr": [20.0, 11.0, 18.0, 0.0, 9.0, 23.0],
    }
    return pl.DataFrame(base | overrides)


def test_admission_follows_the_firewall_rules():
    frame = players()
    admitted = op.admit_realized(
        frame, "nflverse.stats_player", ancestry="test", schema=PLAYER_SCHEMA
    )
    assert set(admitted.dropped) == {"fantasy_points", "fantasy_points_ppr"}  # generic points out
    assert "fantasy_points" not in admitted.frame.columns
    kwargs = {"ancestry": "test"}
    with pytest.raises(LineageError, match="UNKNOWN_COLUMN"):
        op.admit_realized(
            frame.with_columns(pl.lit(1.0).alias("opponent_expected")),
            "nflverse.stats_player",
            schema=[*PLAYER_SCHEMA, "opponent_expected"],
            **kwargs,
        )
    with pytest.raises(LineageError, match="UNKNOWN_VALUE"):
        op.admit_realized(players(season_type=["PROJ"] * 6), "nflverse.stats_player", **kwargs)
    with pytest.raises(LineageError, match="UNKNOWN_SOURCE"):
        op.admit_realized(frame, "espn.player_projections", **kwargs)
    with pytest.raises(LineageError, match="MISSING_ANCESTRY"):
        op.admit_realized(frame, "nflverse.stats_player", ancestry=None)
    with pytest.raises(LineageError, match="MISSING_COLUMN"):
        op.admit_realized(frame.drop("targets"), "nflverse.stats_player", **kwargs)


def test_volume_follows_each_groups_definition_and_skips_the_postseason():
    v = op.player_volumes(players()).sort("position")
    by = {r["position"]: r for r in v.iter_rows(named=True)}
    assert by["QB"]["volume"] == 30 + 2 + 3  # dropbacks + carries
    assert by["RB"]["volume"] == 10 + 4  # FB counts as RB: carries + targets
    assert by["WR"]["volume"] == 9 and by["WR"]["receptions"] == 6  # week 19 (POST) left out
    assert by["TE"]["volume"] == 0
    assert by["K"]["volume"] == 5
    assert set(v.get_column("offense").to_list()) == {"LV"}  # franchise codes


def test_dst_volume_is_the_offenses_plays():
    teams = pl.DataFrame(
        {
            "game_id": ["g1"],
            "season": [2020],
            "week": [1],
            "season_type": ["REG"],
            "team": ["SD"],
            "attempts": [35],
            "sacks_suffered": [3],
            "carries": [25],
            "passing_interceptions": [2],
            "fumbles_lost_total": [1],
        }
    )
    d = op.dst_volumes(teams).row(0, named=True)
    assert (d["offense"], d["volume"], d["dropbacks"], d["turnovers"]) == ("LAC", 63, 38, 3)


def test_cells_keep_missing_zero_and_efficiency_honest():
    observations = pl.DataFrame(
        {
            "game_id": ["g1", "g1", "g1", "g1"],
            "season": [2020] * 4,
            "week": [1] * 4,
            "offense": ["LV"] * 4,
            "defense": ["KC"] * 4,
            "unit": ["KC"] * 4,
            "position": ["WR", "TE", "QB", "RB"],
            "points": [12.0, 0.0, 20.0, 5.0],
            "status": ["valid"] * 4,
        }
    )
    no_rb = players().filter(pl.col("position") != "FB")
    no_teams = pl.DataFrame(
        schema={"game_id": pl.String, "season_type": pl.String, "team": pl.String}
        | dict.fromkeys(op.TEAM_VOLUME, pl.Float64)
    )
    table = op.cells(observations, no_rb, no_teams)
    by = {r["position"]: r for r in table.iter_rows(named=True)}
    assert by["WR"]["volume_status"] == "ok" and by["WR"]["efficiency"] == pytest.approx(12 / 9)
    assert by["TE"]["volume_status"] == "zero" and by["TE"]["efficiency"] is None
    assert by["RB"]["volume_status"] == "missing" and by["RB"]["volume"] is None
    coverage = op.coverage(table)
    assert coverage["RB"]["volume"] == {"missing": 1}


def test_reconciliation_counts_agreement_and_differences():
    p = players()
    teams = pl.DataFrame(
        {
            "game_id": ["g1"],
            "season_type": ["REG"],
            "team": ["LV"],
            "attempts": [30],
            "sacks_suffered": [2],
            "carries": [15],  # players sum to 14: one difference
        }
    )
    r = op.reconcile(p, teams)
    assert r["attempts"] == {"equal": 1, "differ": 0, "maxDifference": 0.0}
    assert r["carries"]["differ"] == 1 and r["carries"]["maxDifference"] == 1.0


def synthetic(trait_sd: float, seed: int = 4):
    """WR volume allowed carries a defense trait; points are volume x 1.2 plus noise."""
    observations, schedule = season_data(seasons=(2016, 2017, 2018), weeks=14, seed=seed)
    schedule = with_teams(observations, schedule)
    rng = np.random.default_rng(seed)
    defenses = sorted(set(observations.get_column("defense").to_list()))
    trait = {(s, d): rng.normal(0, trait_sd) for s in (2016, 2017, 2018) for d in defenses}
    keys = observations.select("season", "defense").rows()
    volume = np.array([max(0.0, 24 + trait[k] + rng.normal(0, 3)) for k in keys]).round()
    points = volume * 1.2 + rng.normal(0, 3, volume.size)
    wr = pl.col("position") == "WR"
    observations = observations.with_columns(
        pl.when(wr).then(pl.Series(points)).otherwise(pl.col("points")).alias("points"),
        pl.Series("_volume", volume),
    )
    volumes = observations.select(
        "game_id",
        "offense",
        "position",
        pl.when(wr).then(pl.col("_volume")).otherwise(pl.lit(60.0)).alias("volume"),
    )
    return observations.drop("_volume"), schedule, volumes


def forecast(observations, schedule, volumes, season=2018):
    rows = wf.prepare(observations)
    params = wf.fit_fold(rows, season, POSITIONS)
    targets = shadow.scheduled_targets(schedule, season, None, POSITIONS)
    hook = explore.make_opportunity_extra(rows, season, POSITIONS, volumes)
    out = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings(), extra=hook)
    plain = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings())
    return rows, out.frame, plain.frame, hook


def test_the_opportunity_hook_adds_columns_and_starts_from_b00():
    observations, schedule, volumes = synthetic(trait_sd=4.0)
    _, out, plain, hook = forecast(observations, schedule, volumes)
    assert out.select(plain.columns).equals(plain)
    week1 = out.filter(pl.col("week") == 1)
    for column in explore.OPPORTUNITY_COLUMNS:
        assert (week1.get_column(column) - week1.get_column("b00")).abs().max() == 0
    dst = out.filter(pl.col("position") == "DST")  # constant volume: no volume residual
    assert (dst.get_column("b07v") - dst.get_column("b00")).abs().max() < 1e-9
    assert hook.parameters["WR"]["kOppVolume"] < 50  # the planted trait is found


def rmse(frame: pl.DataFrame, column: str) -> float:
    return float(np.sqrt(((frame.get_column(column) - frame.get_column("points")) ** 2).mean()))


def test_a_volume_trait_is_recovered_and_noise_is_not_rewarded():
    for trait, better in ((5.0, True), (0.0, False)):
        observations, schedule, volumes = synthetic(trait_sd=trait)
        rows, out, _, _ = forecast(observations, schedule, volumes)
        labels = rows.filter((pl.col("season") == 2018) & (pl.col("position") == "WR")).select(
            "game_id", "offense", "position", "points"
        )
        late = out.join(labels, on=["game_id", "offense", "position"]).filter(pl.col("week") >= 6)
        gain = rmse(late, "b07v") - rmse(late, "b00")
        if better:
            assert gain < -0.1
        else:
            assert abs(gain) < 0.25  # shrinkage keeps a pure-noise channel near B00
