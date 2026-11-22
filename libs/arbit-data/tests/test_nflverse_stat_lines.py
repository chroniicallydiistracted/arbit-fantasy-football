"""FFA stat lines from nflverse weekly statistics and play-by-play, scored by the shared engine.

Every expectation below reproduces a definition settled against ESPN's raw statistics
(docs/research/nflverse-ffa-scoring-2026-11-09.md); the plays are minimal shapes of real ones.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from arbit_core.scoring import MissingStatError, score
from arbit_data.espn.scoring_rules import normalize_scoring
from arbit_data.nflverse.stat_lines import athlete_line, defense_line, game_events

FIXTURE = Path(__file__).resolve().parents[3] / "tests/fixtures/espn/ffa-scoring.observed.json"
RULES = normalize_scoring(json.loads(FIXTURE.read_bytes())["scoringSettings"], 2026)
ATHLETE = {rule.stat for rule in RULES.athlete_rules.rules}
DEFENSE = {rule.stat for rule in RULES.defense_rules.rules}

ZERO_ROW = {
    "player_id": "00-0000001",
    "team": "SEA",
    "passing_yards": 0,
    "passing_tds": 0,
    "passing_2pt_conversions": 0,
    "passing_interceptions": 0,
    "rushing_yards": 0,
    "rushing_tds": 0,
    "rushing_2pt_conversions": 0,
    "receiving_yards": 0,
    "receiving_tds": 0,
    "receiving_2pt_conversions": 0,
    "receptions": 0,
    "fumbles_lost_total": 0,
    "fumble_recovery_tds": 0,
    "fg_made_0_19": 0,
    "fg_made_20_29": 0,
    "fg_made_30_39": 0,
    "fg_made_40_49": 0,
    "fg_made_50_59": 0,
    "fg_made_60_": 0,
    "fg_missed": 0,
    "fg_blocked": 0,
    "pat_made": 0,
}


def play(**fields):
    base = {
        "posteam": "SEA",
        "defteam": "NE",
        "play_type": "pass",
        "touchdown": 0,
        "td_team": None,
        "td_player_id": None,
        "interception": 0,
        "punt_blocked": 0,
        "field_goal_result": None,
        "extra_point_result": None,
        "kickoff_attempt": 0,
        "punt_attempt": 0,
        "extra_point_attempt": 0,
        "two_point_attempt": 0,
        "defensive_two_point_conv": 0,
        "defensive_extra_point_conv": 0,
        "posteam_score": 0,
        "defteam_score": 0,
        "posteam_score_post": 0,
        "defteam_score_post": 0,
    }
    return {**base, **fields}


def values(line):
    return line.line.values


def test_athlete_columns_cover_every_rule_and_score_exactly():
    row = {
        **ZERO_ROW,
        "passing_yards": 250,
        "passing_tds": 2,
        "passing_2pt_conversions": 1,
        "passing_interceptions": 1,
        "rushing_yards": 31,
        "rushing_tds": 1,
        "receptions": 0,
        "fumbles_lost_total": 1,
    }
    line = athlete_line(row, game_events([]), ATHLETE)
    assert set(values(line)) == ATHLETE
    assert values(line)["passing.yards"] == Decimal(250)
    assert values(line)["misc.fumbles_lost"] == Decimal(1)
    # 250*0.04 + 2*4 + 1*2 - 2 + 31*0.1 + 6 - 2
    assert score(line.line, RULES.athlete_rules).total == Decimal("25.10")
    assert line.sources["misc.fumbles_lost"] == "stats_player.fumbles_lost_total"


def test_field_goal_bands_and_misses_count_blocked_kicks_once():
    row = {
        **ZERO_ROW,
        "fg_made_0_19": 1,
        "fg_made_20_29": 1,
        "fg_made_30_39": 1,
        "fg_made_40_49": 1,
        "fg_made_50_59": 1,
        "fg_made_60_": 1,
        "fg_missed": 1,
        "fg_blocked": 1,
        "pat_made": 2,
    }
    v = values(athlete_line(row, game_events([]), ATHLETE))
    assert v["kicking.field_goals_0_39"] == 3
    assert v["kicking.field_goals_50_59"] == 1 and v["kicking.field_goals_60_plus"] == 1
    assert v["kicking.field_goals_missed"] == 2


def test_missing_column_is_unknown_and_the_scorer_refuses_the_line():
    row = {key: value for key, value in ZERO_ROW.items() if key != "fumbles_lost_total"}
    line = athlete_line(row, game_events([]), ATHLETE)
    assert values(line)["misc.fumbles_lost"] is None
    assert line.unknown["misc.fumbles_lost"] == "COLUMN_ABSENT"
    with pytest.raises(MissingStatError):
        score(line.line, RULES.athlete_rules)


def test_null_value_in_present_column_is_unknown_not_zero():
    line = athlete_line({**ZERO_ROW, "receptions": None}, game_events([]), ATHLETE)
    assert values(line)["receiving.receptions"] is None
    assert line.unknown["receiving.receptions"] == "VALUE_NULL"


def test_return_touchdowns_are_split_by_kick_type_from_play_by_play():
    # nflverse gives a kickoff to the receiving team and a punt to the punting team.
    returner = "00-0000001"
    plays = [
        play(
            play_type="kickoff",
            kickoff_attempt=1,
            touchdown=1,
            td_team="SEA",
            td_player_id=returner,
        ),
        play(
            posteam="NE",
            defteam="SEA",
            play_type="punt",
            punt_attempt=1,
            touchdown=1,
            td_team="SEA",
            td_player_id=returner,
        ),
        # A blocked punt returned for a TD is a blocked kick TD, not a punt return TD.
        play(
            posteam="NE",
            defteam="SEA",
            play_type="punt",
            punt_attempt=1,
            punt_blocked=1,
            touchdown=1,
            td_team="SEA",
            td_player_id=returner,
        ),
    ]
    mine = values(athlete_line(ZERO_ROW, game_events(plays), ATHLETE))
    assert mine["returns.kickoff_touchdowns"] == 1
    assert mine["returns.punt_touchdowns"] == 1
    assert mine["returns.blocked_kick_touchdowns"] == 1


def test_kicking_team_touchdowns_on_kicks_follow_espn():
    cover = "00-0000002"
    plays = [
        # Muffed punt recovered by the punting team (SEA) in the end zone: SEA D/ST punt return
        # TD (2026 week 3); the individual credit is unobserved.
        play(play_type="punt", punt_attempt=1, touchdown=1, td_team="SEA", td_player_id=cover),
        # Kickoff recovered by the kicking team (SEA) in the end zone: SEA D/ST fumble return TD,
        # no individual return TD (2025 week 2).
        play(
            posteam="NE",
            defteam="SEA",
            play_type="kickoff",
            kickoff_attempt=1,
            touchdown=1,
            td_team="SEA",
            td_player_id=cover,
        ),
    ]
    events = game_events(plays)
    athlete = athlete_line({**ZERO_ROW, "player_id": cover}, events, ATHLETE)
    assert athlete.unknown["returns.punt_touchdowns"] == "UNVERIFIED_SCORING_EVENT"
    assert values(athlete)["returns.kickoff_touchdowns"] == 0
    assert values(athlete)["returns.fumble_touchdowns"] == 0
    dst = values(defense_line("SEA", TEAM, TEAM, 0, events, DEFENSE))
    assert dst["returns.punt_touchdowns"] == 1 and dst["returns.fumble_touchdowns"] == 1
    # Both count in the other team's points allowed.
    assert (
        values(defense_line("NE", TEAM, TEAM, 14, events, DEFENSE))["defense.points_allowed"] == 14
    )


def test_offense_recovering_the_defenses_fumble_scores_a_fumble_return_td():
    # TEN throws an interception, the ARI defender fumbles, TEN's receiver recovers and scores
    # (2025 week 5): a fumble return TD for him, and ARI's points allowed keep it.
    receiver = "00-0000003"
    events = game_events(
        [
            play(
                posteam="TEN",
                defteam="ARI",
                interception=1,
                fumble=1,
                fumbled_1_team="ARI",
                fumble_recovery_1_team="TEN",
                touchdown=1,
                td_team="TEN",
                td_player_id=receiver,
            )
        ]
    )
    line = values(
        athlete_line(
            {**ZERO_ROW, "player_id": receiver, "team": "TEN", "fumble_recovery_tds": 1},
            events,
            ATHLETE,
        )
    )
    assert line["returns.fumble_touchdowns"] == 1
    assert line["misc.fumble_recovery_touchdowns"] == 0
    assert (
        values(defense_line("ARI", TEAM, TEAM, 7, events, DEFENSE))["defense.points_allowed"] == 7
    )
    # TEN's recovery and touchdown came on offense, so TEN's D/ST is credited with neither.
    ten = defense_line("TEN", {**TEAM, "fumble_recovery_opp": 1}, TEAM, 0, events, DEFENSE)
    assert values(ten)["defense.fumbles_recovered"] == 0
    assert values(ten)["returns.fumble_touchdowns"] == 0


def test_offense_recovering_its_own_fumble_for_a_td_counts_in_points_allowed():
    # DAL's runner fumbles at the goal line and a teammate recovers in the end zone (2026 week 8).
    events = game_events(
        [
            play(
                posteam="DAL",
                defteam="ARI",
                fumble=1,
                fumbled_1_team="DAL",
                fumble_recovery_1_team="DAL",
                touchdown=1,
                td_team="DAL",
                td_player_id="00-0000004",
            )
        ]
    )
    assert (
        values(defense_line("ARI", TEAM, TEAM, 30, events, DEFENSE))["defense.points_allowed"] == 30
    )
    assert (
        values(defense_line("DAL", TEAM, TEAM, 0, events, DEFENSE))["returns.fumble_touchdowns"]
        == 0
    )
    teammate = athlete_line(
        {**ZERO_ROW, "player_id": "00-0000004", "team": "DAL", "fumble_recovery_tds": 1},
        events,
        ATHLETE,
    )
    assert values(teammate)["misc.fumble_recovery_touchdowns"] == 1
    assert values(teammate)["returns.fumble_touchdowns"] == 0


def test_fumble_recoveries_pair_each_fumble_with_its_recovery():
    plays = [
        # PHI throws an interception; the LAC returner fumbles, PHI's QB recovers then fumbles
        # back to LAC (2025 week 14): PHI's offense recovered one opponent fumble.
        play(
            posteam="PHI",
            defteam="LAC",
            interception=1,
            fumble=1,
            fumbled_1_team="LAC",
            fumble_recovery_1_team="PHI",
            fumbled_2_team="PHI",
            fumble_recovery_2_team="LAC",
        ),
        # A blocked PHI field goal that LAC touched and PHI recovered is a special teams recovery.
        play(
            posteam="PHI",
            defteam="LAC",
            play_type="field_goal",
            field_goal_result="blocked",
            fumble=1,
            fumbled_1_team="LAC",
            fumble_recovery_1_team="PHI",
        ),
    ]
    own = {**TEAM, "fumble_recovery_opp": 3}
    line = defense_line("PHI", own, TEAM, 0, game_events(plays), DEFENSE)
    assert values(line)["defense.fumbles_recovered"] == 2


TEAM = {
    "passing_yards": 0,
    "rushing_yards": 0,
    "sack_yards_lost": 0,
    "sacks_suffered": 0,
    "def_interceptions": 0,
    "fumble_recovery_opp": 0,
    "def_fg_blocks": 0,
    "def_punt_blocks": 0,
    "def_pat_blocks": 0,
}


def test_points_allowed_excludes_only_points_scored_against_the_offense():
    plays = [
        # Pick-six against SEA's offense: excluded (the extra point still counts).
        play(interception=1, touchdown=1, td_team="NE", td_player_id="x"),
        # Safety against SEA's offense: excluded.
        play(posteam_score=7, defteam_score=7, posteam_score_post=7, defteam_score_post=9),
        # Punt return TD against SEA's punt team: included.
        play(
            posteam="SEA", defteam="NE", play_type="punt", punt_attempt=1, touchdown=1, td_team="NE"
        ),
        # Safety on a SEA punt counts against the D/ST: included.
        play(
            play_type="punt",
            punt_attempt=1,
            posteam_score=0,
            defteam_score=0,
            posteam_score_post=0,
            defteam_score_post=2,
        ),
        # A NE offensive TD: included.
        play(posteam="NE", defteam="SEA", touchdown=1, td_team="NE"),
    ]
    line = defense_line("SEA", TEAM, TEAM, 33, game_events(plays), DEFENSE)
    assert values(line)["defense.points_allowed"] == Decimal(33 - 6 - 2)


def test_yards_allowed_is_opponent_rushing_plus_net_passing():
    opponent = {**TEAM, "passing_yards": 287, "rushing_yards": 112, "sack_yards_lost": -10}
    line = defense_line("SEA", TEAM, opponent, 10, game_events([]), DEFENSE)
    assert values(line)["defense.yards_allowed"] == Decimal(389)


def test_defense_counting_categories_and_touchdown_kinds():
    own = {**TEAM, "def_interceptions": 2, "fumble_recovery_opp": 1, "def_pat_blocks": 1}
    opponent = {**TEAM, "sacks_suffered": Decimal("3.5")}
    plays = [
        play(posteam="NE", defteam="SEA", interception=1, touchdown=1, td_team="SEA"),
        play(posteam="NE", defteam="SEA", touchdown=1, td_team="SEA"),  # fumble return
        play(play_type="kickoff", kickoff_attempt=1, touchdown=1, td_team="SEA"),
        play(posteam="NE", defteam="SEA", field_goal_result="blocked", touchdown=1, td_team="SEA"),
        # SEA defense safety, then a one-point safety on a NE try.
        play(
            posteam="NE",
            defteam="SEA",
            posteam_score=3,
            defteam_score=0,
            posteam_score_post=3,
            defteam_score_post=2,
        ),
        play(
            posteam="NE",
            defteam="SEA",
            two_point_attempt=1,
            posteam_score=9,
            defteam_score=2,
            posteam_score_post=9,
            defteam_score_post=3,
        ),
        play(posteam="NE", defteam="SEA", defensive_two_point_conv=1),
    ]
    v = values(defense_line("SEA", own, opponent, 9, game_events(plays), DEFENSE))
    assert v["defense.sacks"] == Decimal("3.5")
    assert v["defense.interceptions"] == 2 and v["defense.fumbles_recovered"] == 1
    assert v["defense.blocked_kicks"] == 1
    assert v["returns.interception_touchdowns"] == 1
    assert v["returns.fumble_touchdowns"] == 1
    assert v["returns.kickoff_touchdowns"] == 1
    assert v["returns.blocked_kick_touchdowns"] == 1
    assert v["defense.safeties"] == 1 and v["misc.one_point_safeties"] == 1
    assert v["returns.two_point_returns"] == 1


def test_defense_line_has_no_offensive_statistics_and_scores_every_rule():
    line = defense_line("SEA", TEAM, {**TEAM, "passing_yards": 150}, 10, game_events([]), DEFENSE)
    assert set(values(line)) == DEFENSE
    assert values(line)["passing.yards"] == 0 and values(line)["misc.fumbles_lost"] == 0
    # 10 allowed (+3 band 7-13) and 150 yards (+3 band 100-199).
    assert score(line.line, RULES.defense_rules).total == Decimal("6.00")


def test_unrequested_metric_names_are_refused():
    with pytest.raises(ValueError, match="UNMAPPED_METRIC"):
        athlete_line(ZERO_ROW, game_events([]), {"passing.yards", "rushing.first_downs"})
