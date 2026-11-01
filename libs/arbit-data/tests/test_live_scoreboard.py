"""Scoreboard facts as ESPN sent them on 2026-11-01, with fictional teams and players."""

from decimal import Decimal

import pytest
from arbit_data.live.normalize import normalize_game, normalize_summary_detail


def event(**competition):
    home = {
        "id": "12",
        "homeAway": "home",
        "score": "24",
        "team": {"color": "003594", "alternateColor": "ffd100"},
        "linescores": [{"value": Decimal("3.0")}, {"value": Decimal("7.0")}, {"value": 14}],
        "records": [
            {"type": "total", "summary": "3-4"},
            {"type": "home", "summary": "1-3"},
        ],
    }
    away = {"id": "20", "homeAway": "away", "score": "17", "team": {"color": "not-a-color"}}
    return {
        "id": "401",
        "season": {"year": 2026},
        "weather": {"displayValue": "1", "temperature": 69, "conditionId": "Sunny"},
        "competitions": [
            {
                "id": "401",
                "date": "2026-11-01T21:05Z",
                "competitors": [home, away],
                "status": {
                    "period": 4,
                    "displayClock": "9:38",
                    "type": {
                        "name": "STATUS_IN_PROGRESS",
                        "state": "in",
                        "shortDetail": "9:38 - 4th",
                    },
                },
                "venue": {
                    "fullName": "Test Field",
                    "address": {"city": "Testville"},
                    "indoor": False,
                },
                "broadcasts": [{"names": ["Fox"]}],
                "leaders": [
                    {
                        "shortDisplayName": "PASS",
                        "leaders": [
                            {
                                "displayValue": "21/29, 240 YDS",
                                "athlete": {"id": "77", "shortName": "T. Tester"},
                                "team": {"id": "20"},
                            }
                        ],
                    }
                ],
                "situation": {
                    "down": 1,
                    "distance": 10,
                    "yardLine": 80,
                    "possession": "20",
                    "possessionText": "AWY 20",
                    "shortDownDistanceText": "1st & 10",
                    "isRedZone": False,
                    "homeTimeouts": 3,
                    "awayTimeouts": 2,
                    "lastPlay": {
                        "id": "4019",
                        "type": {"text": "Pass Incompletion"},
                        "text": "T.Tester pass incomplete",
                        "statYardage": 0,
                        "team": {"id": "20"},
                        "probability": {"homeWinPercentage": Decimal("0.9765")},
                    },
                },
                **competition,
            }
        ],
    }


def test_live_game_state_is_kept():
    game = normalize_game(event(), 2026)
    situation = game.situation
    assert (situation.down, situation.distance, situation.yard_line) == (1, 10, 80)
    assert situation.possession_team_id == "20"
    assert (situation.home_timeouts, situation.away_timeouts) == (3, 2)
    assert situation.last_play.yards == 0
    assert situation.last_play.home_win == 0.9765
    assert game.status_detail == "9:38 - 4th"


def test_team_lines_venue_weather_and_leaders():
    game = normalize_game(event(), 2026)
    assert game.home_line.record == "3-4"
    assert game.home_line.periods == ("3", "7", "14")
    assert game.home_line.color == "003594"
    assert game.away_line.color is None, "a value that isn't a color never reaches a style"
    assert game.venue.name == "Test Field"
    assert (game.weather.temperature, game.weather.condition) == (69, "Sunny")
    assert game.broadcast == ("Fox",)
    assert game.leaders[0].name == "T. Tester"


def test_espn_unknown_sentinels_stay_unknown():
    raw = event(situation={"down": -1, "distance": -1, "yardLine": -5, "possession": None})
    situation = normalize_game(raw, 2026).situation
    assert (situation.down, situation.distance, situation.yard_line) == (None, None, None)
    assert situation.possession_team_id is None


@pytest.mark.parametrize(
    "broken",
    [
        {"situation": "not an object"},
        {"venue": 7},
        {"broadcasts": "Fox"},
        {"leaders": {"bad": True}},
    ],
)
def test_a_changed_extra_loses_only_that_extra_never_the_score(broken):
    game = normalize_game(event(**broken), 2026)
    assert (game.home_score, game.away_score, game.phase) == ("24", "17", "in_progress")


def test_before_kickoff_there_is_no_situation():
    raw = event()
    del raw["competitions"][0]["situation"]
    assert normalize_game(raw, 2026).situation is None


def test_summary_detail_lines_up_both_teams():
    detail = normalize_summary_detail(
        {
            "boxscore": {
                "teams": [
                    {
                        "homeAway": "away",
                        "statistics": [
                            {"name": "totalYards", "label": "Total Yards", "displayValue": "258"}
                        ],
                    },
                    {
                        "homeAway": "home",
                        "statistics": [
                            {"name": "totalYards", "label": "Total Yards", "displayValue": "301"},
                            {"name": "totalYards", "label": "Total Yards", "displayValue": "999"},
                        ],
                    },
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "12"},
                        "displayResult": "Punt",
                        "offensivePlays": 3,
                        "yards": 4,
                        "isScore": False,
                        "start": {"text": "HOM 35"},
                    }
                ],
                "current": {"team": {"id": "20"}, "offensivePlays": 1},
            },
            "winprobability": [{"homeWinPercentage": Decimal("0.2717"), "playId": "1"}],
        }
    )
    assert detail["team_stats"] == [
        {"key": "totalYards", "label": "Total Yards", "home": "301", "away": "258"}
    ]
    assert [d["current"] for d in detail["drives"]] == [False, True]
    assert detail["win_probability"] == [{"play_id": "1", "home": 0.2717}]


def test_a_finished_drive_is_not_also_listed_as_current():
    finished = {"id": "9", "team": {"id": "12"}, "displayResult": "Touchdown"}
    detail = normalize_summary_detail({"drives": {"previous": [finished], "current": finished}})
    assert [d["current"] for d in detail["drives"]] == [False]


def test_an_empty_placeholder_is_not_a_drive():
    placeholder = {"id": "8", "team": {"id": "12"}, "offensivePlays": 0, "yards": 0}
    assert normalize_summary_detail({"drives": {"previous": [placeholder]}})["drives"] == []


def test_a_broken_summary_part_does_not_lose_the_others():
    detail = normalize_summary_detail({"boxscore": {"teams": "bad"}, "drives": "bad"})
    assert detail == {"drives": [], "win_probability": [], "team_stats": []}
