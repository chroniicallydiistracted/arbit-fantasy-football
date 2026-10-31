"""Factual FFL category identities; rates always come from the fetched league.

Provenance: cwendt94/espn-api constant.py at 700e15ddbb91124f031473d2411c8a6285944274,
blob 81834cda9e5dac613ebcfac9ad29a1619ba46c28; checked against FFA raw/applied pairs.
No upstream scoring implementation is copied. Range counters are per game.
"""

from dataclasses import dataclass

MAPPING_VERSION = "espn-ffl-ffa-categories-v1"
MAPPING_SOURCE = "https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/football/constant.py"


@dataclass(frozen=True)
class Category:
    stat: str
    raw: str
    lower: int | None = None
    upper: int | None = None


LINEAR = {
    3: "passing.yards",
    4: "passing.touchdowns",
    19: "passing.two_point_conversions",
    20: "passing.interceptions",
    24: "rushing.yards",
    25: "rushing.touchdowns",
    26: "rushing.two_point_conversions",
    42: "receiving.yards",
    43: "receiving.touchdowns",
    44: "receiving.two_point_conversions",
    53: "receiving.receptions",
    63: "misc.fumble_recovery_touchdowns",
    72: "misc.fumbles_lost",
    77: "kicking.field_goals_40_49",
    80: "kicking.field_goals_0_39",
    85: "kicking.field_goals_missed",
    86: "kicking.extra_points_made",
    93: "returns.blocked_kick_touchdowns",
    95: "defense.interceptions",
    96: "defense.fumbles_recovered",
    97: "defense.blocked_kicks",
    98: "defense.safeties",
    99: "defense.sacks",
    101: "returns.kickoff_touchdowns",
    102: "returns.punt_touchdowns",
    103: "returns.interception_touchdowns",
    104: "returns.fumble_touchdowns",
    198: "kicking.field_goals_50_59",
    201: "kicking.field_goals_60_plus",
    206: "returns.two_point_returns",
    209: "misc.one_point_safeties",
}
CATEGORIES = {key: Category(stat, str(key)) for key, stat in LINEAR.items()}
for key, lower, upper in [
    (89, 0, 1),
    (90, 1, 7),
    (91, 7, 14),
    (92, 14, 18),
    (123, 28, 35),
    (124, 35, 46),
    (125, 46, None),
]:
    CATEGORIES[key] = Category("defense.points_allowed", "120", lower, upper)
for key, lower, upper in [
    (128, 0, 100),
    (129, 100, 200),
    (130, 200, 300),
    (132, 350, 400),
    (133, 400, 450),
    (134, 450, 500),
    (135, 500, 550),
    (136, 550, None),
]:
    CATEGORIES[key] = Category("defense.yards_allowed", "127", lower, upper)
