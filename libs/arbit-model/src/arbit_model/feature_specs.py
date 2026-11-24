"""Every team feature's definition, unit, window, cutoff, sources and shrinkage (slice 3 gate).

`team_features` produces exactly these columns besides its keys; a test holds the two together.
Shrinkage constants are games for half signal, measured with one method (split halves of each
team-season, Spearman-Brown): team rates in the signal study, defense against the position in its
own study. A shrunk value is (n·x + k·m) / (n + k) after n games, toward the league mean m, or
n / (n + k) of an adjusted value, toward zero.
"""

from collections.abc import Mapping
from dataclasses import dataclass

# The 2026-11-09 signal study rerun with R-072 repaired (all 320 team-seasons, its pinned inputs).
SIGNAL_STUDY = "docs/research/ffa-signal-study-2026-11-23-r072.json"
# M3-3 v0, measured before the R-072 repair. The DvP research (OWN-074) replaces these only
# through its Phase B decision.
POSITION_STUDY = "docs/research/defense-position-study-2026-11-23.json"
CUTOFF = (
    "The decision time (the game's kickoff unless given). Only rows the point-in-time reader "
    "returns before it count (ADR-007 with A1-A5)"
)
TO_DATE = "The team's completed games this season known before the decision"
LAST_SEASON = "The team's completed games last season"
PRE_GAME = "This game's schedule row, pre-game fields only"
TEAM_ROWS = ("stats_team_week", "schedules.home_score/away_score")
POSITION_ROWS = ("stats_player_week", "pbp (scoring events)", "FFA rules (shared scorer)")

# Games for half signal, with the receipt and measure each comes from.
SHRINKAGE: Mapping[str, tuple[float, str, str]] = {
    "off_plays_pg": (13.3, SIGNAL_STUDY, "TEAM/offensive_plays_per_game"),
    "off_dropback_rate": (6.4, SIGNAL_STUDY, "TEAM/dropback_rate"),
    "off_epa_per_play": (5.7, SIGNAL_STUDY, "TEAM/offensive_epa_per_play"),
    "off_points_pg": (7.5, SIGNAL_STUDY, "TEAM/points_scored_per_game"),
    "def_epa_per_play": (19.7, SIGNAL_STUDY, "TEAM/defensive_epa_per_play_allowed"),
    "def_points_allowed_pg": (22.0, SIGNAL_STUDY, "TEAM/points_allowed_per_game"),
    "def_sack_rate": (21.4, SIGNAL_STUDY, "TEAM/sack_rate_forced"),
    "def_takeaways_pg": (62.6, SIGNAL_STUDY, "TEAM/takeaways_per_game"),
    "dvp_QB": (30.6, POSITION_STUDY, "QB_raw"),
    "dvp_RB": (18.7, POSITION_STUDY, "RB_raw"),
    "dvp_WR": (44.1, POSITION_STUDY, "WR_raw"),
    "dvp_TE": (37.6, POSITION_STUDY, "TE_raw"),
    "dvp_K": (49.4, POSITION_STUDY, "K_raw"),
    "dvp_QB_adj": (22.2, POSITION_STUDY, "QB_adjusted"),
    "dvp_RB_adj": (20.0, POSITION_STUDY, "RB_adjusted"),
    "dvp_WR_adj": (42.0, POSITION_STUDY, "WR_adjusted"),
    "dvp_TE_adj": (40.1, POSITION_STUDY, "TE_adjusted"),
    "dvp_K_adj": (55.3, POSITION_STUDY, "K_adjusted"),
    "dst_allowed": (9.2, POSITION_STUDY, "DST_raw"),
    "dst_allowed_adj": (9.1, POSITION_STUDY, "DST_adjusted"),
}


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    definition: str
    unit: str
    window: str
    sources: tuple[str, ...]
    shrinkage: str | None = None  # a SHRINKAGE key
    cutoff: str = CUTOFF


def _team(name: str, definition: str, unit: str) -> list[FeatureSpec]:
    """A season-to-date team rate, its shrunk value and last season's value."""
    return [
        FeatureSpec(name, definition, unit, TO_DATE, TEAM_ROWS),
        FeatureSpec(
            name + "_shrunk",
            definition + ", shrunk toward the league mean",
            unit,
            TO_DATE,
            TEAM_ROWS,
            shrinkage=name,
        ),
        FeatureSpec("prev_" + name, definition + " last season", unit, LAST_SEASON, TEAM_ROWS),
    ]


TEAM_RATES = (
    ("off_plays_pg", "Offensive plays (pass attempts, sacks and carries) per game", "plays/game"),
    ("off_dropback_rate", "Dropbacks (pass attempts and sacks) per offensive play", "share"),
    ("off_epa_per_play", "Offensive EPA (passing and rushing) per play", "EPA/play"),
    ("off_points_pg", "Points scored per game", "points/game"),
    ("def_epa_per_play", "Opponents' offensive EPA per play against this defense", "EPA/play"),
    ("def_points_allowed_pg", "Points allowed per game", "points/game"),
    ("def_sack_rate", "Sacks per opponent dropback", "share"),
    ("def_takeaways_pg", "Opponent interceptions and lost fumbles per game", "takeaways/game"),
)
OPPONENT_DEFENSE = (
    "def_epa_per_play",
    "def_points_allowed_pg",
    "def_sack_rate",
    "def_takeaways_pg",
)
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def _specs() -> dict[str, FeatureSpec]:
    specs: list[FeatureSpec] = [
        FeatureSpec("is_home", "Whether the team is at home", "flag", PRE_GAME, ("schedules",)),
        FeatureSpec(
            "rest_days",
            "Days since the team's previous game",
            "days",
            PRE_GAME,
            ("schedules.home_rest/away_rest",),
        ),
        FeatureSpec(
            "opp_rest_days",
            "Days since the opponent's previous game",
            "days",
            PRE_GAME,
            ("schedules.home_rest/away_rest",),
        ),
        FeatureSpec(
            "roof",
            "Stadium roof: outdoors, dome, open or closed",
            "category",
            PRE_GAME,
            ("schedules.roof",),
        ),
        FeatureSpec("surface", "Playing surface", "category", PRE_GAME, ("schedules.surface",)),
        FeatureSpec(
            "div_game", "Whether it is a division game", "flag", PRE_GAME, ("schedules.div_game",)
        ),
        FeatureSpec(
            "games_played", "Completed games known before the decision", "games", TO_DATE, TEAM_ROWS
        ),
        FeatureSpec(
            "opp_games_played",
            "The opponent's completed games known before the decision",
            "games",
            TO_DATE,
            TEAM_ROWS,
        ),
    ]
    for name, definition, unit in TEAM_RATES:
        specs += _team(name, definition, unit)
    for name in OPPONENT_DEFENSE:
        base = next(s for s in specs if s.name == name + "_shrunk")
        specs.append(
            FeatureSpec(
                "opp_" + name + "_shrunk",
                "The opponent's " + base.definition[0].lower() + base.definition[1:],
                base.unit,
                TO_DATE,
                TEAM_ROWS,
                shrinkage=name,
            )
        )
    for pos in POSITIONS:
        what = f"FFA points the opponent's defense allowed to {pos}s"
        specs += [
            FeatureSpec(
                f"opp_dvp_{pos}_pg", what + " per game", "FFA points/game", TO_DATE, POSITION_ROWS
            ),
            FeatureSpec(
                f"opp_dvp_{pos}_pg_shrunk",
                what + " per game, shrunk toward the league mean",
                "FFA points/game",
                TO_DATE,
                POSITION_ROWS,
                shrinkage=f"dvp_{pos}",
            ),
            FeatureSpec(
                f"opp_dvp_{pos}_adj",
                what + " per game beyond what each offense it "
                f"faced scores at {pos} in its other games",
                "FFA points/game",
                TO_DATE,
                POSITION_ROWS,
            ),
            FeatureSpec(
                f"opp_dvp_{pos}_adj_shrunk",
                what + ", adjusted for the offenses faced and shrunk toward zero",
                "FFA points/game",
                TO_DATE,
                POSITION_ROWS,
                shrinkage=f"dvp_{pos}_adj",
            ),
            FeatureSpec(
                f"opp_dvp_{pos}_opps_pg",
                f"Opportunities the opponent's defense allowed "
                f"to {pos}s per game (QB: attempts and carries; RB: carries and targets; "
                "WR, TE: targets; K: field goal and extra point attempts)",
                "opportunities/game",
                TO_DATE,
                ("stats_player_week",),
            ),
        ]
    what = "FFA points opposing D/STs scored against the opponent's offense"
    specs += [
        FeatureSpec(
            "opp_off_dst_allowed_pg", what + " per game", "FFA points/game", TO_DATE, POSITION_ROWS
        ),
        FeatureSpec(
            "opp_off_dst_allowed_pg_shrunk",
            what + " per game, shrunk toward the league mean",
            "FFA points/game",
            TO_DATE,
            POSITION_ROWS,
            shrinkage="dst_allowed",
        ),
        FeatureSpec(
            "opp_off_dst_allowed_adj",
            what + " per game beyond each D/ST's average in its other games",
            "FFA points/game",
            TO_DATE,
            POSITION_ROWS,
        ),
        FeatureSpec(
            "opp_off_dst_allowed_adj_shrunk",
            what + ", adjusted for the D/STs faced and shrunk toward zero",
            "FFA points/game",
            TO_DATE,
            POSITION_ROWS,
            shrinkage="dst_allowed_adj",
        ),
    ]
    return {spec.name: spec for spec in specs}


FEATURES: Mapping[str, FeatureSpec] = _specs()
