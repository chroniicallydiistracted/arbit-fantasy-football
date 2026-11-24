"""One code per franchise across nflverse tables (R-072).

nflverse's tables disagree about team codes. The schedule and snap counts keep the code a team had
that season (OAK 2012-2019, SD 2012-2016, STL 2012-2015), while play-by-play and player and team
statistics use the franchise's current code (LV, LAC, LA) for every season. The 2012-2015 weekly
rosters use their own codes for five teams (ARZ, BLT, CLV, HST, SL). Comparing codes across
tables without mapping them names a team as its own opponent and drops games, so every table's
codes become the statistics tables' franchise codes before any join.

The map holds only codes observed in the stored nflverse files. Callers check that each mapped
code is one of its game's two teams, so a code that appears later fails loudly instead of
joining wrongly.
"""

from collections.abc import Mapping
from typing import Any

import polars as pl

FRANCHISE: Mapping[str, str] = {
    # Relocations: the schedule and snap counts use the code of the day.
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LA",
    # 2012-2015 weekly rosters.
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "SL": "LA",
}

# Columns that hold a team code in the tables the Model reads.
TEAM_FIELDS = frozenset(
    {
        "team",
        "opponent",
        "opponent_team",
        "recent_team",
        "home_team",
        "away_team",
        "posteam",
        "defteam",
        "td_team",
        "fumbled_1_team",
        "fumbled_2_team",
        "fumble_recovery_1_team",
        "fumble_recovery_2_team",
    }
)


class TeamCodeError(ValueError):
    """A row's team is not one of its game's two teams, even after mapping franchise codes."""


def franchise(code: str) -> str:
    return FRANCHISE.get(code, code)


def franchise_expr(column: pl.Expr) -> pl.Expr:
    return column.replace(dict(FRANCHISE))


def franchise_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """The row with every team field mapped; the same object when nothing changes."""
    changed = {
        key: FRANCHISE[value]
        for key, value in row.items()
        if key in TEAM_FIELDS and isinstance(value, str) and value in FRANCHISE
    }
    return {**row, **changed} if changed else row


def franchise_columns(frame: pl.DataFrame) -> pl.DataFrame:
    """The frame with every string team column mapped."""
    columns = [
        name for name, dtype in frame.schema.items() if name in TEAM_FIELDS and dtype == pl.String
    ]
    return frame.with_columns(franchise_expr(pl.col(c)).alias(c) for c in columns)
