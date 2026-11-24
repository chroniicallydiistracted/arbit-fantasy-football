"""Historical FFA targets and participation labels (M3 slice 2).

One synthetic game, Seattle 24 New England 10, carries every case: a scored statistics line, a
player who played without a statistics row, a New England defensive two-point return no play
names a scorer for (R-061), and each participation label.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from arbit_data.espn.scoring_rules import normalize_scoring
from arbit_model.storage import default_sources, participation_table, target_table
from arbit_model.targets import (
    NO_STATISTICS_SOURCE,
    STAT_COLUMNS,
    SeasonRows,
    participation,
    rule_metrics,
    targets,
)
from arbit_model.teams import TeamCodeError

FIXTURE = Path(__file__).resolve().parents[3] / "tests/fixtures/espn/ffa-scoring.observed.json"
SCORING = normalize_scoring(json.loads(FIXTURE.read_bytes())["scoringSettings"], 2026)
RULES = {"athlete": SCORING.athlete_rules, "defense": SCORING.defense_rules}
GAME = "2025_01_NE_SEA"

GAMES = [
    {
        "game_id": GAME,
        "season": 2025,
        "week": 1,
        "game_type": "REG",
        "home_team": "SEA",
        "away_team": "NE",
        "home_score": 24,
        "away_score": 10,
    },
    # Scheduled but not played: no targets, no labels.
    {
        "game_id": "2025_02_SEA_LA",
        "season": 2025,
        "week": 2,
        "game_type": "REG",
        "home_team": "LA",
        "away_team": "SEA",
        "home_score": None,
        "away_score": None,
    },
]


def play(**fields):
    base = {
        "game_id": GAME,
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
    return base | fields


PLAYS = [
    play(),
    # New England returns a Seattle two-point try; play-by-play names no scorer.
    play(
        play_type="pass",
        two_point_attempt=1,
        defensive_two_point_conv=1,
        posteam_score=6,
        posteam_score_post=6,
        defteam_score=0,
        defteam_score_post=2,
    ),
]


def stat_row(player_id, team, opponent, position, **values):
    return (
        {
            "player_id": player_id,
            "team": team,
            "opponent_team": opponent,
            "position": position,
            "game_id": GAME,
            "season_type": "REG",
            "week": 1,
        }
        | dict.fromkeys(STAT_COLUMNS, 0)
        | values
    )


PLAYERS = [
    stat_row("SEA-WR", "SEA", "NE", "WR", receptions=5, receiving_yards=80, receiving_tds=1),
    stat_row("NE-WR", "NE", "SEA", "WR", receptions=3, receiving_yards=30),
    stat_row("NE-CB", "NE", "SEA", "CB"),
    stat_row("NE-RB", "NE", "SEA", "RB", rushing_yards=12),
    stat_row("NE-KR", "NE", "SEA", "WR", receptions=1, receiving_yards=8),
]


def team_row(team, **values):
    base = {
        "team": team,
        "game_id": GAME,
        "passing_yards": 200,
        "rushing_yards": 100,
        "sack_yards_lost": 10,
        "sacks_suffered": 2,
        "def_interceptions": 1,
        "fumble_recovery_opp": 0,
        "def_fg_blocks": 0,
        "def_punt_blocks": 0,
        "def_pat_blocks": 0,
    }
    return base | values


def snap(pfr, team, opponent, position, offense=0.0, defense=0.0, special=0.0):
    return {
        "game_id": GAME,
        "pfr_player_id": pfr,
        "team": team,
        "opponent": opponent,
        "position": position,
        "offense_snaps": offense,
        "defense_snaps": defense,
        "st_snaps": special,
    }


SNAPS = [
    snap("p-sea-wr", "SEA", "NE", "WR", offense=60),
    snap("p-sea-te", "SEA", "NE", "TE", offense=20),  # played, no statistics row
    snap("p-sea-lb", "SEA", "NE", "LB", defense=50),  # played without a statistic
    snap("p-ne-wr", "NE", "SEA", "WR", offense=55),  # ruled out of the two-point return
    snap("p-ne-cb", "NE", "SEA", "CB", defense=60, special=5),  # could have returned it
    snap("p-ne-kr", "NE", "SEA", "WR", offense=10, special=15),  # on the field for the kick team
]
PFR = {
    "p-sea-wr": "SEA-WR",
    "p-sea-te": "SEA-TE",
    "p-sea-lb": "SEA-LB",
    "p-ne-wr": "NE-WR",
    "p-ne-cb": "NE-CB",
    "p-ne-kr": "NE-KR",
    "p-sea-rb": "SEA-RB",
    "p-sea-qb2": "SEA-QB2",
}


def roster(gsis, team, status, position="WR"):
    return {"gsis_id": gsis, "team": team, "week": 1, "status": status, "position": position}


ROSTERS = [
    roster("SEA-WR", "SEA", "ACT"),
    roster("SEA-TE", "SEA", "ACT", "TE"),
    roster("SEA-RB", "SEA", "INA", "RB"),
    roster("SEA-QB2", "SEA", "ACT", "QB"),  # active, no snap, no statistic
    roster("SEA-K2", "SEA", "ACT", "K"),  # no PFR ID: snaps cannot be checked
    roster("SEA-PS", "SEA", "DEV", "WR"),
    roster("NE-WR", "NE", "ACT"),
    roster("NE-CB", "NE", "ACT", "CB"),
]


def season(**changes):
    rows = {
        "season": 2025,
        "games": GAMES,
        "plays": PLAYS,
        "players": PLAYERS,
        "teams": [team_row("SEA"), team_row("NE")],
        "snaps": SNAPS,
        "rosters": ROSTERS,
        "pfr_to_gsis": PFR,
    }
    return SeasonRows(**(rows | changes))


def by_player(found):
    return {(t.role, t.player_id or t.team): t for t in found}


def test_participation_labels_separate_played_inactive_and_unknown():
    labels = {p.player_id: p for p in participation(season())}

    assert labels["SEA-WR"].label == "played"
    assert labels["SEA-WR"].evidence == "snap_counts"
    assert labels["SEA-TE"].label == "played"
    assert labels["SEA-RB"].label == "inactive"
    assert labels["SEA-QB2"].label == "active_no_snaps"
    assert labels["SEA-K2"].label == "unknown"
    assert labels["SEA-PS"].label == "not_active_roster"
    # Played without a roster row: snaps alone, or a statistic alone.
    assert labels["SEA-LB"].label == "played"
    assert labels["SEA-LB"].roster_status is None
    assert (labels["NE-RB"].label, labels["NE-RB"].evidence) == ("played", "statistics")
    # The unplayed week-2 game produces nothing.
    assert {p.game_id for p in labels.values()} == {GAME}


def test_without_inactive_status_no_snap_players_are_not_called_active():
    rosters = [r | {"status": "ACT"} if r["status"] == "INA" else r for r in ROSTERS]
    labels = {p.player_id: p for p in participation(season(rosters=rosters))}

    assert labels["SEA-QB2"].label == "rostered_no_snaps"
    assert labels["SEA-RB"].label == "rostered_no_snaps"


def test_without_snap_counts_no_snap_players_are_unknown():
    labels = {p.player_id: p for p in participation(season(snaps=[]))}

    assert labels["SEA-QB2"].label == "unknown"
    assert labels["SEA-WR"].label == "played"
    assert labels["SEA-WR"].evidence == "statistics"


def test_statistics_lines_are_scored_by_the_shared_engine():
    found = by_player(targets(season(), RULES, participation(season())))

    seattle = found[("athlete", "SEA-WR")]
    # 5 receptions, 80 yards, one touchdown under FFA's full PPR.
    assert seattle.points == Decimal("19")
    assert seattle.basis == "statistics"
    assert seattle.opponent == "NE"
    assert {stat for _, stat, _ in seattle.contributions} >= {"receiving.receptions"}


def test_played_without_statistics_row_is_an_explicit_zero_line():
    found = by_player(targets(season(), RULES, participation(season())))

    tight_end = found[("athlete", "SEA-TE")]
    assert tight_end.basis == "snaps_without_statistics"
    assert tight_end.points == Decimal(0)
    assert tight_end.game_position == "TE"
    assert tight_end.line.sources["receiving.receptions"] == NO_STATISTICS_SOURCE
    # Any listed position gets a line: a game's snap position is not his FFA position.
    assert found[("athlete", "SEA-LB")].points == Decimal(0)
    # A player who did not play gets none.
    assert ("athlete", "SEA-QB2") not in found
    assert ("athlete", "SEA-RB") not in found


def test_r061_rules_out_only_players_whose_snaps_show_no_defense_or_special_teams():
    found = by_player(targets(season(), RULES, participation(season())))

    receiver = found[("athlete", "NE-WR")]
    assert receiver.line.line.values["returns.two_point_returns"] == Decimal(0)
    assert "R-061" in receiver.line.sources["returns.two_point_returns"]
    assert receiver.points == Decimal("6")

    corner = found[("athlete", "NE-CB")]
    assert corner.line.unknown["returns.two_point_returns"] == "UNATTRIBUTED_TEAM_EVENT"
    assert corner.points is None
    assert corner.refusal is not None and corner.refusal.startswith("MissingStatError")

    # A special-teams snap keeps a receiver in the field-goal block unit's pool.
    returner = found[("athlete", "NE-KR")]
    assert returner.line.unknown["returns.two_point_returns"] == "UNATTRIBUTED_TEAM_EVENT"
    assert returner.points is None

    # No snap row at all: the value stays unknown.
    back = found[("athlete", "NE-RB")]
    assert back.points is None

    # Seattle had no two-point return, so its players are known zero.
    assert found[("athlete", "SEA-WR")].line.unknown == {}


def test_each_team_gets_a_dst_line_and_games_without_play_by_play_get_no_targets():
    found = by_player(targets(season(), RULES, participation(season())))

    assert found[("defense", "NE")].points is not None
    assert found[("defense", "NE")].line.line.values["returns.two_point_returns"] == 1
    assert found[("defense", "SEA")].line.line.values["defense.points_allowed"] == 10

    assert targets(season(plays=[]), RULES, participation(season())) == []


def test_rule_metrics_are_unique_even_when_bands_repeat_a_metric():
    defense = rule_metrics(RULES["defense"])
    assert len(defense) == len(set(defense))
    assert "defense.points_allowed" in defense


def test_tables_keep_unknowns_null_with_reasons_and_only_differing_sources():
    labels = participation(season())
    found = [t for t in targets(season(), RULES, labels) if t.role == "athlete"]
    sources = default_sources(found)
    table = target_table(
        found,
        rule_metrics(RULES["athlete"]),
        {(p.game_id, p.player_id): p.label for p in labels},
        sources,
    )
    rows = {row["player_id"]: row for row in table.to_pylist()}

    corner = rows["NE-CB"]
    assert corner["returns.two_point_returns"] is None
    assert corner["points"] is None
    assert {"metric": "returns.two_point_returns", "value": "UNATTRIBUTED_TEAM_EVENT"} in corner[
        "unknown"
    ]
    assert rows["SEA-WR"]["source_overrides"] == []
    assert rows["SEA-TE"]["participation"] == "played"
    assert any(o["value"] == NO_STATISTICS_SOURCE for o in rows["SEA-TE"]["source_overrides"])
    assert participation_table(labels).num_rows == len(labels)


# R-072: nflverse's schedule, snap counts and rosters keep a relocated team's code of the day
# (OAK) while play-by-play and statistics use the franchise code (LV), and the 2012-2015 rosters
# have codes of their own (BLT for Baltimore).
TEAM_COLUMNS = ("home_team", "away_team", "team", "opponent", "opponent_team")
PLAY_TEAMS = ("posteam", "defteam", "td_team")


def recode(rows, codes, columns=TEAM_COLUMNS):
    return [row | {c: codes.get(row[c], row[c]) for c in columns if c in row} for row in rows]


def relocated_season():
    """The fixture with Seattle as a relocated franchise (OAK in the schedule, snap counts and
    rosters, LV in play-by-play and statistics) and New England as Baltimore, whose 2012-2015
    roster code is BLT."""
    day = {"SEA": "OAK", "NE": "BAL"}
    franchise = {"SEA": "LV", "NE": "BAL"}
    return season(
        games=recode(GAMES, day),
        snaps=recode(SNAPS, day),
        rosters=recode(ROSTERS, {"SEA": "OAK", "NE": "BLT"}),
        players=recode(PLAYERS, franchise),
        teams=recode([team_row("SEA"), team_row("NE")], franchise),
        plays=recode(PLAYS, franchise, PLAY_TEAMS),
    )


def comparable(found):
    """Targets with team codes replaced by which side of the game they name."""
    side = {"SEA": "home", "LV": "home", "NE": "away", "BAL": "away"}
    return sorted(
        (t.role, str(t.player_id), side[t.team], side[t.opponent], t.points, t.basis) for t in found
    )


def test_r072_a_relocated_franchise_scores_exactly_like_a_consistently_coded_one():
    consistent = targets(season(), RULES, participation(season()))
    rows = relocated_season()
    relocated = targets(rows, RULES, participation(rows))

    assert comparable(relocated) == comparable(consistent)
    # Every row uses the franchise code, and no team is its own opponent.
    assert {t.team for t in relocated} == {"LV", "BAL"}
    assert all(t.team != t.opponent for t in relocated)
    # Both D/ST lines exist (the scorer used to skip a game whose team row it couldn't find).
    assert {t.team for t in relocated if t.role == "defense"} == {"LV", "BAL"}


def test_r072_roster_codes_map_to_franchises_so_roster_labels_survive():
    labels = {p.player_id: p for p in participation(relocated_season())}
    consistent = {p.player_id: p.label for p in participation(season())}

    assert {k: p.label for k, p in labels.items()} == consistent
    assert labels["SEA-RB"].label == "inactive"  # known only from the OAK roster row
    assert labels["SEA-RB"].team == "LV"
    assert labels["NE-WR"].team == "BAL"  # the roster said BLT


def test_a_row_whose_team_did_not_play_in_its_game_is_refused():
    stray = [*PLAYERS, stat_row("KC-WR", "KC", "SEA", "WR", receptions=1)]
    with pytest.raises(TeamCodeError, match="stats_player_week.team KC"):
        targets(season(players=stray), RULES, [])
    with pytest.raises(TeamCodeError, match="weekly_rosters.team ZZZ"):
        participation(season(rosters=[*ROSTERS, roster("ZZ-WR", "ZZZ", "ACT")]))
