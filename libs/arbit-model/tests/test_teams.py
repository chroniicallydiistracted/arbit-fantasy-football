"""One code per franchise (R-072)."""

import polars as pl
from arbit_model.teams import FRANCHISE, franchise, franchise_columns, franchise_row


def test_relocated_and_roster_codes_map_to_the_statistics_codes():
    assert franchise("OAK") == "LV" and franchise("SD") == "LAC" and franchise("STL") == "LA"
    assert [franchise(c) for c in ("ARZ", "BLT", "CLV", "HST", "SL")] == [
        "ARI",
        "BAL",
        "CLE",
        "HOU",
        "LA",
    ]
    assert franchise("KC") == "KC"
    # Mapping is idempotent: no franchise code is itself an old code.
    assert not set(FRANCHISE.values()) & set(FRANCHISE)


def test_rows_and_frames_map_only_team_columns():
    row = {"home_team": "OAK", "away_team": "KC", "player_name": "SD", "team": "SL"}
    assert franchise_row(row) == {
        "home_team": "LV",
        "away_team": "KC",
        "player_name": "SD",
        "team": "LA",
    }
    unchanged = {"home_team": "KC"}
    assert franchise_row(unchanged) is unchanged

    frame = pl.DataFrame({"home_team": ["OAK", "KC"], "away_team": ["SD", "STL"], "x": ["OAK"] * 2})
    assert franchise_columns(frame).to_dict(as_series=False) == {
        "home_team": ["LV", "KC"],
        "away_team": ["LAC", "LA"],
        "x": ["OAK", "OAK"],
    }
