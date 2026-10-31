import pytest


def test_player_directory_keeps_unknowns_and_separates_defenses():
    from arbit_data.sleeper.reader import normalize_sleeper

    r = normalize_sleeper(
        "sleeper.players",
        {
            "101": {
                "player_id": "101",
                "position": "RB",
                "espn_id": "123",
                "gsis_id": "00-0012345",
                "injury_status": None,
                "new_metric": None,
            },
            "CAR": {"player_id": "CAR", "position": "DEF", "fantasy_positions": ["DEF"]},
        },
    )
    assert r["data"]["101"]["injury_status"] is None
    assert r["data"]["101"]["new_metric"] is None
    assert r["entity_kinds"] == {"101": "athlete", "CAR": "defense_unit"}
    assert r["ownership_authority"] is False and r["recommendations_enabled"] is False


def test_mismatched_directory_id_fails_before_joining():
    from arbit_data.sleeper.reader import normalize_sleeper

    with pytest.raises(ValueError):
        normalize_sleeper("sleeper.players", {"101": {"player_id": "102"}})


def test_state_mismatch_is_visible_and_trends_do_not_imply_ownership():
    from arbit_data.sleeper.reader import normalize_sleeper

    r = normalize_sleeper("sleeper.state", {"season": "2027", "week": 1, "season_type": "regular"})
    assert not r["season_matches_config"]
    t = normalize_sleeper("sleeper.trending.add", [{"player_id": "101", "count": 50}])
    assert t["data"][0]["count"] == 50 and not t["ownership_authority"]
    with pytest.raises(ValueError):
        normalize_sleeper("sleeper.trending.add", [{"player_id": "101", "count": -1}])
    with pytest.raises(ValueError):
        normalize_sleeper(
            "sleeper.trending.add",
            [{"player_id": "101", "count": 1}, {"player_id": "101", "count": 2}],
        )


def test_candidate_stats_stay_unverified_and_preserve_all_fields():
    from arbit_data.sleeper.reader import normalize_sleeper

    r = normalize_sleeper(
        "sleeper.stats.v1", {"101": {"pass_yd": 20, "pts_ppr": 1, "unknown": None}}
    )
    assert r["usage"] == "candidate" and not r["ffa_scoring_verified"]
    assert r["scope_evidence"] == "request_only" and r["data"]["101"]["unknown"] is None
