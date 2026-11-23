"""When each nflverse value counts as known: ADR-007 decision 4 as amended by OWN-066.

These rules stand in for publication times Arbit did not observe: every season before its first
import (2026-10-31), and values first fetched after a capture gap (amendment A1). Observed
vintages override them (`point_in_time`). Each rule is conservative where nflverse's published
cadence and Arbit's measured vintages disagree, and every value it times carries the label
`retrospective-rule`, or `source-timestamp` when the row's own timestamp set the time.

A table is readable only through a registered `TableSpec`. It names the rows that travel together
between file versions (a game's plays, a player-week's injury report, a team's depth chart
snapshot) and when they count as known.
"""

import re
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

Basis = Literal["observed", "source-timestamp", "retrospective-rule"]
BASES: tuple[Basis, ...] = ("observed", "source-timestamp", "retrospective-rule")

EASTERN = ZoneInfo("America/New_York")
ALWAYS = datetime.min.replace(tzinfo=UTC)
NEVER = datetime.max.replace(tzinfo=UTC)
PREFIX = "nflverse/nflverse-data/"

RULE: Basis = "retrospective-rule"
STAMP: Basis = "source-timestamp"


@dataclass(frozen=True)
class Game:
    game_id: str
    season: int
    week: int
    game_type: str
    home: str
    away: str
    gameday: date  # US Eastern date, as the schedule states it
    kickoff: datetime | None  # UTC; None when the schedule has no time


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _kickoff(day: date, clock: Any) -> datetime | None:
    if not clock:
        return None
    hour, minute = (int(part) for part in str(clock).split(":")[:2])
    return datetime.combine(day, time(hour, minute), EASTERN).astimezone(UTC)


# Some tables use a franchise's current code for earlier seasons (Next Gen Stats writes LV for
# Oakland and LAC for San Diego); the schedule keeps the code of the season.
TEAM_ALIASES: Mapping[str, tuple[str, ...]] = {"LAR": ("LA",), "LV": ("OAK",), "LAC": ("SD",)}


class Calendar:
    """Games and kickoffs from the schedule (`schedules/games`).

    Kickoff times and matchups locate rows and set decision times; they are not features. The
    calendar is built from the newest schedule file, so a flexed kickoff time is the final one.
    """

    def __init__(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self.games: dict[str, Game] = {}
        self._aliases: dict[str, Game] = {}
        self._team_week: dict[tuple[int, int, str], Game] = {}
        self._weeks: dict[tuple[int, int], list[Game]] = {}
        for row in rows:
            day = _date(row.get("gameday"))
            if not row.get("game_id") or day is None:
                continue
            game = Game(
                game_id=str(row["game_id"]),
                season=int(row["season"]),
                week=int(row["week"]),
                game_type=str(row.get("game_type") or "REG"),
                home=str(row["home_team"]),
                away=str(row["away_team"]),
                gameday=day,
                kickoff=_kickoff(day, row.get("gametime")),
            )
            self.games[game.game_id] = game
            if row.get("old_game_id"):
                self._aliases[str(row["old_game_id"])] = game
            for team in (game.home, game.away):
                self._team_week[(game.season, game.week, team)] = game
            self._weeks.setdefault((game.season, game.week), []).append(game)

    def game(self, game_id: Any) -> Game | None:
        key = str(game_id)
        return self.games.get(key) or self._aliases.get(key)

    def team_game(self, season: Any, week: Any, team: Any) -> Game | None:
        try:
            season, week = int(season), int(week)
        except (TypeError, ValueError):
            return None
        for code in (str(team), *TEAM_ALIASES.get(str(team), ())):
            found = self._team_week.get((season, week, code))
            if found is not None:
                return found
        return None

    def week(self, season: Any, week: Any) -> list[Game]:
        try:
            return self._weeks.get((int(season), int(week)), [])
        except (TypeError, ValueError):
            return []


def at_utc(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), UTC)


def next_publication(stamp: datetime, hour: int = 7) -> datetime:
    """nflverse's first daily publication at `hour` UTC strictly after `stamp`."""
    stamp = stamp.astimezone(UTC)
    candidate = at_utc(stamp.date(), hour)
    return candidate if candidate > stamp else candidate + timedelta(days=1)


def _stamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Placement:
    """Where a row belongs and when it counts as known without an observed vintage.

    `unit` groups rows that travel together between file versions. `known` is None when the row
    cannot be timed (its game is not in the schedule); such rows are never admitted by a rule.
    """

    unit: Hashable
    known: datetime | None
    basis: Basis


# (row, calendar, the season in the file's key or None)
Locate = Callable[[Mapping[str, Any], Calendar, int | None], Placement]


def _game_of(
    row: Mapping[str, Any], cal: Calendar, game_id: str | None, team: str | None
) -> Game | None:
    if game_id and row.get(game_id) is not None:
        found = cal.game(row[game_id])
        if found is not None:
            return found
    if team and row.get(team) is not None:
        return cal.team_game(row.get("season"), row.get("week"), row[team])
    return None


def per_game(
    days: int, hour: int, *, game_id: str | None = "game_id", team: str | None = None
) -> Locate:
    """Rows describing one game, known at `hour` UTC `days` after its date (statistics: 1, 12)."""

    def locate(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
        game = _game_of(row, cal, game_id, team)
        if game is None:
            unit = (
                "unlocated",
                row.get(game_id) if game_id else None,
                row.get("season"),
                row.get("week"),
                row.get(team) if team else None,
            )
            return Placement(unit, None, RULE)
        return Placement(game.game_id, at_utc(game.gameday + timedelta(days=days), hour), RULE)

    return locate


def _season_of(row: Mapping[str, Any], key_season: int | None) -> int | None:
    value = row.get("season")
    try:
        return int(value) if value is not None else key_season
    except (TypeError, ValueError):
        return key_season


def after_season() -> Locate:
    """Season files and aggregates: known after the postseason, from 1 March of the next year."""

    def locate(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
        year = _season_of(row, season)
        if year is None:
            return Placement(("season", None), None, RULE)
        return Placement(("season", year), datetime(year + 1, 3, 1, tzinfo=UTC), RULE)

    return locate


def schedule_rows(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
    """A regular-season game's schedule row is known after the schedule release (by 1 June). A
    postseason row is known once the previous round ends, when its matchup is set."""
    game_id = row.get("game_id")
    game = cal.game(game_id) if game_id is not None else None
    if game is None:
        return Placement(("unlocated", game_id), None, RULE)
    if game.game_type == "REG":
        return Placement(game.game_id, datetime(game.season, 6, 1, tzinfo=UTC), RULE)
    previous = cal.week(game.season, game.week - 1)
    if not previous:
        return Placement(game.game_id, None, RULE)
    last = max(g.gameday for g in previous)
    return Placement(game.game_id, at_utc(last + timedelta(days=1), 12), RULE)


def ngs_rows(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
    """Next Gen Stats: week 0 is a season aggregate; postseason weeks are numbered differently
    from the schedule, so they count as known after the season."""
    if row.get("week") in (0, None) or row.get("season_type") != "REG":
        located = after_season()(row, cal, season)
        return Placement(("ngs-season", located.unit, row.get("season_type")), located.known, RULE)
    return per_game(2, 12, game_id=None, team="team_abbr")(row, cal, season)


def injury_rows(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
    """An injury report row is known at nflverse's first 07:00 UTC publication after its
    `date_modified`. Files from 2025 on have no `date_modified`; their rows hold each week's final
    report, which is out by the day before the game, so they count from 07:00 UTC on game day."""
    unit = (row.get("season"), row.get("week"), row.get("team"), row.get("gsis_id"))
    modified = _stamp(row.get("date_modified"))
    if modified is not None:
        return Placement(unit, next_publication(modified), STAMP)
    game = cal.team_game(row.get("season"), row.get("week"), row.get("team"))
    if game is None:
        return Placement(unit, None, RULE)
    return Placement(unit, at_utc(game.gameday, 7), RULE)


def depth_rows(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
    """Depth charts from 2025 are timestamped snapshots per team (`dt`), known at the next 07:00
    UTC publication. Earlier charts are weekly with no publication time: known from 12:00 UTC on
    the day before the week's first game (ADR-007: before the week's first game)."""
    stamp = _stamp(row.get("dt"))
    if stamp is not None:
        return Placement((row.get("team"), str(row.get("dt"))), next_publication(stamp), STAMP)
    team = row.get("club_code") or row.get("team")
    unit = (row.get("season"), row.get("week"), team)
    games = cal.week(row.get("season"), row.get("week"))
    if not games:
        return Placement(unit, None, RULE)
    first = min(g.gameday for g in games)
    return Placement(unit, at_utc(first - timedelta(days=1), 12), RULE)


def week_rows(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
    """Weekly roster status, `INA` included, is known only after the week's games: from 12:00 UTC
    the day after the week's last game. Earlier weeks' statuses inform later weeks."""
    unit = (row.get("season"), row.get("week"), row.get("team"))
    games = cal.week(row.get("season"), row.get("week"))
    if not games:
        return Placement(unit, None, RULE)
    last = max(g.gameday for g in games)
    return Placement(unit, at_utc(last + timedelta(days=1), 12), RULE)


def trade_rows(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
    """A trade is known from the day after its `trade_date`."""
    day = _date(row.get("trade_date"))
    unit = ("trade", row.get("trade_id"))
    if day is None:
        return Placement(unit, None, STAMP)
    return Placement(unit, at_utc(day + timedelta(days=1), 0), STAMP)


def yearly(column: str, month: int, *, years_after: int = 0, unit: tuple[str, ...]) -> Locate:
    """Known from the first of `month` in the row's `column` year plus `years_after`: the draft
    (1 May of the draft year) or a contract (the season after it was signed)."""

    def locate(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
        key = tuple(row.get(c) for c in unit)
        try:
            year = int(row[column]) + years_after
        except (KeyError, TypeError, ValueError):
            return Placement(key, None, RULE)
        return Placement(key, datetime(year, month, 1, tzinfo=UTC), RULE)

    return locate


def fixed(unit: tuple[str, ...]) -> Locate:
    """Facts fixed before a player's first game, and team identity: always known."""

    def locate(row: Mapping[str, Any], cal: Calendar, season: int | None = None) -> Placement:
        return Placement(tuple(row.get(c) for c in unit), ALWAYS, RULE)

    return locate


ColumnTiming = Literal["as_imported", "after_game"]

# Fields timed later than their row beyond what their catalog use says: they apply only from an
# observed import, or only after the game they describe. (`history` fields in a table whose rows
# precede the game, and `as_imported` fields, are timed by their use.)
RULE_TIMING: Mapping[str, ColumnTiming] = {
    "betting-lines": "as_imported",  # read only through the OWN-067 gate; Q-014 sets any rule
    "expected-quarterbacks": "as_imported",  # ADR-007: observed vintages only
    "referee": "after_game",  # ADR-007: the current game's crew is not used
}


@dataclass(frozen=True)
class TableSpec:
    pattern: str  # full match on the key without the nflverse prefix
    family: str  # field catalog family
    locate: Locate
    after_game: Locate | None = None  # history fields in a table whose rows precede the game
    note: str = ""
    _regex: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_regex", re.compile(self.pattern))

    def matches(self, key: str) -> bool:
        return self._regex.fullmatch(key) is not None


def _season_files(stem: str) -> str:
    return stem + r"_(19|20)\d{2}"


STATISTICS = per_game(1, 12, team="team")

TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "schedules/games",
        "schedules",
        schedule_rows,
        after_game=per_game(1, 12),
        note="Before the season; scores, weather and referee after the game",
    ),
    TableSpec(
        _season_files("pbp/play_by_play"),
        "pbp",
        per_game(1, 12),
        note="12:00 UTC the day after the game",
    ),
    TableSpec(_season_files("stats_player/stats_player_week"), "stats_player", STATISTICS),
    TableSpec(_season_files("stats_team/stats_team_week"), "stats_team", STATISTICS),
    TableSpec(
        r"stats_player/stats_player_(reg|post|regpost)_(19|20)\d{2}",
        "stats_player",
        after_season(),
        note="Season aggregates are rebuilt weekly",
    ),
    TableSpec(
        r"stats_team/stats_team_(reg|post|regpost)_(19|20)\d{2}", "stats_team", after_season()
    ),
    TableSpec(
        _season_files("snap_counts/snap_counts"),
        "snap_counts",
        per_game(2, 12, team="team"),
        note="12:00 UTC two days after the game",
    ),
    TableSpec(
        r"nextgen_stats/ngs_((19|20)\d{2}_)?(passing|receiving|rushing)", "nextgen_stats", ngs_rows
    ),
    TableSpec(
        r"pfr_advstats/advstats_week_(pass|rush|rec|def)_(19|20)\d{2}",
        "pfr_advstats",
        per_game(4, 0, team="team"),
        note="00:00 UTC four days after the game",
    ),
    TableSpec(
        r"pfr_advstats/advstats_season_(pass|rush|rec|def)(_(19|20)\d{2})?",
        "pfr_advstats",
        after_season(),
    ),
    TableSpec(
        _season_files("ftn_charting/ftn_charting"),
        "ftn_charting",
        per_game(4, 0, game_id="nflverse_game_id"),
    ),
    TableSpec(_season_files("injuries/injuries"), "injuries", injury_rows),
    TableSpec(_season_files("weekly_rosters/roster_weekly"), "weekly_rosters", week_rows),
    TableSpec(_season_files("rosters/roster"), "rosters", after_season()),
    TableSpec(_season_files("depth_charts/depth_charts"), "depth_charts", depth_rows),
    TableSpec("trades/trades", "trades", trade_rows),
    TableSpec("players/players", "players", fixed(("gsis_id",))),
    TableSpec(
        "combine/combine",
        "combine",
        yearly("season", 5, unit=("season", "player_name", "pfr_id", "cfb_id")),
    ),
    TableSpec(
        "draft_picks/draft_picks",
        "draft_picks",
        yearly("season", 5, unit=("season", "round", "pick")),
    ),
    TableSpec(
        "contracts/historical_contracts",
        "contracts",
        yearly(
            "year_signed",
            6,
            years_after=1,
            unit=("otc_id", "team", "year_signed", "years", "value"),
        ),
    ),
    TableSpec("teams/teams_colors_logos", "teams", fixed(("team_abbr",))),
    TableSpec("officials/officials", "officials", per_game(1, 12)),
    TableSpec(
        _season_files("pbp_participation/pbp_participation"), "pbp_participation", after_season()
    ),
)


def short_key(key: str) -> str:
    return key[len(PREFIX) :] if key.startswith(PREFIX) else key


def spec_for(key: str) -> TableSpec:
    short = short_key(key)
    for spec in TABLES:
        if spec.matches(short):
            return spec
    raise LookupError(f"NO_TIMING_RULE: {short}")


def key_season(key: str) -> int | None:
    """The season a per-season file's name carries (`injuries/injuries_2025`), else None."""
    found = re.findall(r"(?<![0-9])((?:19|20)[0-9]{2})(?![0-9])", short_key(key))
    return int(found[-1]) if found else None
