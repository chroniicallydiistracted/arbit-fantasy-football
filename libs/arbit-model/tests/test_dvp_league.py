"""League-constrained D/ST decisions (owner audit Phase B, C05L-2026) on a hand-checked week."""

import polars as pl
import pytest
from arbit_model.dvp import league

FORECASTS = {
    "b00": {"AAA": 6.0, "BBB": 7.0, "CCC": 5.0, "DDD": 8.0, "EEE": 9.0},
    "b06": {"AAA": 8.0, "BBB": 7.0, "CCC": 5.0, "DDD": 8.0, "EEE": 4.0},
}
POINTS = {"AAA": 10.0, "BBB": 3.0, "CCC": 1.0, "DDD": 12.0, "EEE": 0.0}
HOLDINGS = {"t1": ["AAA", "BBB"], "t2": ["CCC"], "t3": ["EEE", "ZZZ"]}  # ZZZ is on bye
PLAYING = {"AAA", "BBB", "CCC", "DDD", "EEE"}


def test_pick_breaks_ties_by_code():
    assert league.pick(["DDD", "AAA"], FORECASTS["b06"]) == "AAA"  # 8.0 each


def test_start_needs_two_playing_units_and_stream_adds_free_agents():
    starts = league.decide(1, HOLDINGS, ["DDD"], PLAYING, FORECASTS, POINTS, league.START)
    assert [r["team"] for r in starts] == ["t1"]  # t3's second unit is on bye
    t1 = starts[0]
    assert (t1["pick_b00"], t1["pick_b06"], t1["best"]) == ("BBB", "AAA", 10.0)
    streams = league.decide(1, HOLDINGS, ["DDD"], PLAYING, FORECASTS, POINTS, league.STREAM)
    by_team = {r["team"]: r for r in streams}
    assert by_team["t2"]["options"] == 2 and by_team["t2"]["pick_b00"] == "DDD"
    assert by_team["t3"]["pick_b00"] == "EEE" and by_team["t3"]["pick_b06"] == "DDD"
    unlabelled = league.decide(
        1,
        HOLDINGS,
        ["FFF"],
        PLAYING | {"FFF"},
        {m: f | {"FFF": 1.0} for m, f in FORECASTS.items()},
        POINTS,
        league.STREAM,
    )
    assert all(not r["labelled"] for r in unlabelled)


def test_summary_counts_changes_points_hits_and_regret():
    rows = league.decide(1, HOLDINGS, ["DDD"], PLAYING, FORECASTS, POINTS, league.STREAM)
    s = league.summarize(pl.DataFrame(rows), "b00", "b06", reps=200, seed=1)
    # t1: b00 DDD (12) vs b06 AAA (10); t2: both DDD; t3: b00 EEE (0) vs b06 DDD (12).
    assert s["changed"] == 2 and s["pointsFromChanges"] == pytest.approx(-2 + 12)
    assert s["candidateRightWhenChanged"] == 0.5
    assert s["b00"]["points"] == 24 and s["b06"]["points"] == 34
    assert s["b06"]["hitRate"] == pytest.approx(2 / 3, abs=1e-4)  # rounded to 4 places
    assert s["b00"]["meanRegret"] == pytest.approx(12 / 3)
    assert len(s["pointsFromChanges95"]) == 2


def test_matchup_effects_count_results_that_change():
    starts = pl.DataFrame(league.decide(3, HOLDINGS, [], PLAYING, FORECASTS, POINTS, league.START))
    lineups = pl.DataFrame(
        {
            "week": [3, 3],
            "team": ["t1", "t1"],
            "unit": ["BBB", "AAA"],
            "slot": ["DST", "BENCH"],
            "points": [3.0, 10.0],
        }
    )
    matchups = [
        {
            "winner": "away",
            "scoring_periods": [3],
            "home": {"team_id": "t1", "official_points": "100.00"},
            "away": {"team_id": "t9", "official_points": "105.00"},
        }
    ]
    effects = league.matchup_effects(starts, lineups, matchups, "b00", "b06")
    # Actual 100 with BBB started (3). B00 starts BBB: still 100, a loss. B06 starts AAA: 107, a win.
    assert effects["resultsDifferBetweenModels"] == 1 and effects["candidateWins"] == 1
    assert effects["resultDiffersFromActual"] == {"b00": 0, "b06": 1}
    assert effects["againstActual"]["b06"] == {"lossesToWins": 1, "winsToLosses": 0, "other": 0}
