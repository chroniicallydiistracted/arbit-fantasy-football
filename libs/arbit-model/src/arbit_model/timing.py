"""When each nflverse value counts as known: ADR-007 decision 4 as amended by OWN-066.

These rules stand in for publication times Arbit did not observe: every season before its first
import (2026-10-31), and values first fetched after a capture gap (amendment A1). Whatever Arbit
held at a decision counts first (A5, `point_in_time`). Each rule is conservative where nflverse's
published cadence and Arbit's measured vintages disagree. Every value it times carries the label
`retrospective-rule`, or `source-timestamp` when the row's own timestamp set the time.

A table is readable only through a registered `TableSpec`. It names the rows that travel together
between file versions (a game's plays, a player-week's injury report, a team's depth chart
snapshot) and when they count as known. Placement works on whole columns (polars), because a
season file can hold hundreds of thousands of rows (R-071).
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import polars as pl

Basis = Literal["observed", "source-timestamp", "retrospective-rule"]
BASES: tuple[Basis, ...] = ("observed", "source-timestamp", "retrospective-rule")

EASTERN = ZoneInfo("America/New_York")
ALWAYS = datetime.min.replace(tzinfo=UTC)
NEVER = datetime.max.replace(tzinfo=UTC)
PREFIX = "nflverse/nflverse-data/"

RULE: Basis = "retrospective-rule"
STAMP: Basis = "source-timestamp"

# Placement output: one row per input row, in order.
UNIT, KNOWN, RULE_BASIS = "_unit", "_known", "_rule_basis"
INSTANT = pl.Datetime("us", "UTC")

# Some tables use a franchise's current code for earlier seasons (Next Gen Stats writes LV for
# Oakland and LAC for San Diego); the schedule keeps the code of the season.
TEAM_ALIASES: Mapping[str, tuple[str, ...]] = {"LAR": ("LA",), "LV": ("OAK",), "LAC": ("SD",)}


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


def at_utc(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), UTC)


def next_publication(stamp: datetime, hour: int = 7) -> datetime:
    """nflverse's first daily publication at `hour` UTC strictly after `stamp`."""
    stamp = stamp.astimezone(UTC)
    candidate = at_utc(stamp.date(), hour)
    return candidate if candidate > stamp else candidate + timedelta(days=1)


class Calendar:
    """Games and kickoffs from the schedule (`schedules/games`).

    Kickoff times and matchups locate rows and set decision times; they are not features. The
    calendar is built from the newest schedule file, so a flexed kickoff time is the final one.
    """

    def __init__(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self.games: dict[str, Game] = {}
        aliases: dict[str, str] = {}
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
                aliases[str(row["old_game_id"])] = game.game_id
        self._aliases = {alias: self.games[g] for alias, g in aliases.items()}
        self._weeks: dict[tuple[int, int], list[Game]] = {}
        self._team_week: dict[tuple[int, int, str], Game] = {}
        for game in self.games.values():
            self._weeks.setdefault((game.season, game.week), []).append(game)
            for team in (game.home, game.away):
                self._team_week[(game.season, game.week, team)] = game
        for (season, week, team), game in list(self._team_week.items()):
            for alias, codes in TEAM_ALIASES.items():
                if team in codes:
                    self._team_week.setdefault((season, week, alias), game)
        self._frames(aliases)

    def _frames(self, aliases: Mapping[str, str]) -> None:
        lookup = [(g, g) for g in self.games] + list(aliases.items())
        self.ids = pl.DataFrame(
            {
                "_lookup": [alias for alias, _ in lookup],
                "_gid": [g for _, g in lookup],
                "_gday": [self.games[g].gameday for _, g in lookup],
                "_sched": [self._schedule_known(self.games[g]) for _, g in lookup],
            },
            schema={"_lookup": pl.Utf8, "_gid": pl.Utf8, "_gday": pl.Date, "_sched": INSTANT},
        )
        teams = [(s, w, t, g.game_id, g.gameday) for (s, w, t), g in self._team_week.items()]
        self.teams = pl.DataFrame(
            teams,
            schema={
                "_s": pl.Int32,
                "_w": pl.Int32,
                "_t": pl.Utf8,
                "_gid_t": pl.Utf8,
                "_gday_t": pl.Date,
            },
            orient="row",
        )
        weeks = [
            (s, w, min(g.gameday for g in gs), max(g.gameday for g in gs))
            for (s, w), gs in self._weeks.items()
        ]
        self.weeks = pl.DataFrame(
            weeks,
            schema={"_s": pl.Int32, "_w": pl.Int32, "_first_day": pl.Date, "_last_day": pl.Date},
            orient="row",
        )

    def _schedule_known(self, game: Game) -> datetime | None:
        """A regular-season game's schedule row is known after the schedule release (by 1 June).
        A postseason row is known once the previous round ends, when its matchup is set."""
        if game.game_type == "REG":
            return datetime(game.season, 6, 1, tzinfo=UTC)
        previous = self._weeks.get((game.season, game.week - 1))
        if not previous:
            return None
        return at_utc(max(g.gameday for g in previous) + timedelta(days=1), 12)

    def game(self, game_id: Any) -> Game | None:
        key = str(game_id)
        return self.games.get(key) or self._aliases.get(key)

    def team_game(self, season: Any, week: Any, team: Any) -> Game | None:
        try:
            return self._team_week.get((int(season), int(week), str(team)))
        except (TypeError, ValueError):
            return None

    def week(self, season: Any, week: Any) -> list[Game]:
        try:
            return self._weeks.get((int(season), int(week)), [])
        except (TypeError, ValueError):
            return []


# --- Column helpers -------------------------------------------------------------------------


def _col(frame: pl.DataFrame, name: str | None, dtype: Any) -> pl.Expr:
    """A column cast to `dtype`, or nulls when the version lacks it."""
    if name is None or name not in frame.columns or frame.schema[name] == pl.Null:
        return pl.lit(None, dtype)
    return pl.col(name).cast(dtype, strict=False)


def _day_at(day: pl.Expr, days: int, hour: int) -> pl.Expr:
    instant = day.cast(pl.Datetime("us")).dt.replace_time_zone("UTC")
    return instant + pl.duration(days=days, hours=hour)


def _next_publication(stamp: pl.Expr, hour: int = 7) -> pl.Expr:
    candidate = stamp.dt.truncate("1d") + pl.duration(hours=hour)
    return pl.when(candidate > stamp).then(candidate).otherwise(candidate + pl.duration(days=1))


def _key(*parts: pl.Expr) -> pl.Expr:
    return pl.concat_str([p.cast(pl.Utf8).fill_null("~") for p in parts], separator="|")


def _stamp(frame: pl.DataFrame, name: str) -> pl.Expr:
    """A source timestamp column as UTC instants: ISO text (`2026-11-21T15:12:52Z`) or a
    timestamp; nulls when absent or unreadable."""
    if name not in frame.columns:
        return pl.lit(None, INSTANT)
    dtype = frame.schema[name]
    if dtype == pl.Utf8:
        return pl.col(name).str.to_datetime(
            format="%Y-%m-%dT%H:%M:%SZ", time_zone="UTC", strict=False, time_unit="us"
        )
    if isinstance(dtype, pl.Datetime):
        column = pl.col(name)
        if dtype.time_zone is None:
            column = column.dt.replace_time_zone("UTC")
        else:
            column = column.dt.convert_time_zone("UTC")
        return column.cast(INSTANT)
    if dtype == pl.Date:
        return _day_at(pl.col(name), 0, 0)
    return pl.lit(None, INSTANT)


def _placed(unit: pl.Expr, known: pl.Expr, basis: pl.Expr) -> list[pl.Expr]:
    return [unit.alias(UNIT), known.cast(INSTANT).alias(KNOWN), basis.alias(RULE_BASIS)]


def _with_game(
    frame: pl.DataFrame, cal: Calendar, game_id: str | None, team: str | None
) -> pl.DataFrame:
    """The frame's identifying columns plus `_gid` and `_gday`, the game each row describes."""
    base = frame.select(
        _col(frame, game_id, pl.Utf8).alias("_lookup"),
        _col(frame, "season", pl.Int32).alias("_s"),
        _col(frame, "week", pl.Int32).alias("_w"),
        _col(frame, team, pl.Utf8).alias("_t"),
    )
    ids = cal.ids.select("_lookup", "_gid", "_gday")
    joined = base.join(ids, on="_lookup", how="left", maintain_order="left")
    if team is not None:
        joined = joined.join(cal.teams, on=["_s", "_w", "_t"], how="left", maintain_order="left")
    else:
        joined = joined.with_columns(
            pl.lit(None, pl.Utf8).alias("_gid_t"), pl.lit(None, pl.Date).alias("_gday_t")
        )
    return joined.with_columns(
        pl.coalesce("_gid", "_gid_t").alias("_gid"),
        pl.coalesce("_gday", "_gday_t").alias("_gday"),
    )


# --- Placement rules ------------------------------------------------------------------------

# (version rows, calendar, the season in the file's key or None) -> _unit, _known, _rule_basis
Place = Callable[[pl.DataFrame, Calendar, int | None], pl.DataFrame]


def per_game(
    days: int, hour: int, *, game_id: str | None = "game_id", team: str | None = None
) -> Place:
    """Rows describing one game, known at `hour` UTC `days` after its date (statistics: 1, 12).
    A row whose game the schedule lacks is untimed."""

    def place(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
        located = _with_game(frame, cal, game_id, team)
        missing = _key(
            pl.lit("unlocated"), pl.col("_lookup"), pl.col("_s"), pl.col("_w"), pl.col("_t")
        )
        unit = pl.coalesce(pl.col("_gid"), missing)
        return located.select(_placed(unit, _day_at(pl.col("_gday"), days, hour), pl.lit(RULE)))

    return place


def after_season() -> Place:
    """Season files and aggregates: known after the postseason, from 1 March of the next year."""

    def place(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
        year = pl.coalesce(_col(frame, "season", pl.Int32), pl.lit(season, pl.Int32))
        known = pl.datetime(year + 1, 3, 1, time_zone="UTC")
        return frame.select(_placed(_key(pl.lit("season"), year), known, pl.lit(RULE)))

    return place


def schedule_rows(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
    """A regular-season row from 1 June; a postseason row from the day after the previous round."""
    base = frame.select(_col(frame, "game_id", pl.Utf8).alias("_lookup"))
    joined = base.join(cal.ids, on="_lookup", how="left", maintain_order="left")
    unit = pl.coalesce(pl.col("_gid"), _key(pl.lit("unlocated"), pl.col("_lookup")))
    return joined.select(_placed(unit, pl.col("_sched"), pl.lit(RULE)))


def ngs_rows(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
    """Next Gen Stats: week 0 is a season aggregate; postseason weeks are numbered differently
    from the schedule, so they count as known after the season."""
    weekly = per_game(2, 12, game_id=None, team="team_abbr")(frame, cal, season)
    totals = after_season()(frame, cal, season).rename(
        {UNIT: "_tu", KNOWN: "_tk", RULE_BASIS: "_tb"}
    )
    week = _col(frame, "week", pl.Int32)
    kind = _col(frame, "season_type", pl.Utf8)
    flags = frame.select(
        (week.is_null() | (week == 0) | kind.is_null() | (kind != "REG")).alias("_total"),
        kind.alias("_kind"),
    )
    both = flags.hstack(weekly).hstack(totals)
    total = pl.col("_total")
    return both.select(
        _placed(
            pl.when(total)
            .then(_key(pl.lit("ngs"), pl.col("_tu"), pl.col("_kind")))
            .otherwise(pl.col(UNIT)),
            pl.when(total).then(pl.col("_tk")).otherwise(pl.col(KNOWN)),
            pl.lit(RULE),
        )
    )


def injury_rows(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
    """An injury report row is known at nflverse's first 07:00 UTC publication after its
    `date_modified`. Files from 2025 on have no `date_modified`; their rows hold each week's final
    report, which is out by the day before the game, so they count from 07:00 UTC on game day."""
    located = _with_game(frame, cal, None, "team")
    extra = frame.select(
        _stamp(frame, "date_modified").alias("_stamp"),
        _col(frame, "gsis_id", pl.Utf8).alias("_p"),
    )
    both = located.hstack(extra)
    stamped = pl.col("_stamp").is_not_null()
    return both.select(
        _placed(
            _key(pl.col("_s"), pl.col("_w"), pl.col("_t"), pl.col("_p")),
            pl.when(stamped)
            .then(_next_publication(pl.col("_stamp")))
            .otherwise(_day_at(pl.col("_gday"), 0, 7)),
            pl.when(stamped).then(pl.lit(STAMP)).otherwise(pl.lit(RULE)),
        )
    )


def depth_rows(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
    """Depth charts from 2025 are timestamped snapshots per team (`dt`), known at the next 07:00
    UTC publication. Earlier charts are weekly with no publication time: known from 12:00 UTC on
    the day before the week's first game (ADR-007: before the week's first game)."""
    team = pl.coalesce(_col(frame, "club_code", pl.Utf8), _col(frame, "team", pl.Utf8))
    base = frame.select(
        _stamp(frame, "dt").alias("_stamp"),
        _col(frame, "dt", pl.Utf8).alias("_dt"),
        team.alias("_t"),
        _col(frame, "season", pl.Int32).alias("_s"),
        _col(frame, "week", pl.Int32).alias("_w"),
    )
    joined = base.join(cal.weeks, on=["_s", "_w"], how="left", maintain_order="left")
    stamped = pl.col("_stamp").is_not_null()
    return joined.select(
        _placed(
            pl.when(stamped)
            .then(_key(pl.col("_t"), pl.col("_dt")))
            .otherwise(_key(pl.col("_s"), pl.col("_w"), pl.col("_t"))),
            pl.when(stamped)
            .then(_next_publication(pl.col("_stamp")))
            .otherwise(_day_at(pl.col("_first_day"), -1, 12)),
            pl.when(stamped).then(pl.lit(STAMP)).otherwise(pl.lit(RULE)),
        )
    )


def week_rows(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
    """Weekly roster status, `INA` included, is known only after the week's games: from 12:00 UTC
    the day after the week's last game. Earlier weeks' statuses inform later weeks."""
    base = frame.select(
        _col(frame, "season", pl.Int32).alias("_s"),
        _col(frame, "week", pl.Int32).alias("_w"),
        _col(frame, "team", pl.Utf8).alias("_t"),
    )
    joined = base.join(cal.weeks, on=["_s", "_w"], how="left", maintain_order="left")
    unit = _key(pl.col("_s"), pl.col("_w"), pl.col("_t"))
    return joined.select(_placed(unit, _day_at(pl.col("_last_day"), 1, 12), pl.lit(RULE)))


def trade_rows(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
    """A trade is known from the day after its `trade_date`."""
    unit = _key(pl.lit("trade"), _col(frame, "trade_id", pl.Utf8))
    known = _day_at(_col(frame, "trade_date", pl.Date), 1, 0)
    return frame.select(_placed(unit, known, pl.lit(STAMP)))


def yearly(column: str, month: int, *, years_after: int = 0, unit: tuple[str, ...]) -> Place:
    """Known from the first of `month` in the row's `column` year plus `years_after`: the draft
    (1 May of the draft year) or a contract (the season after it was signed)."""

    def place(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
        year = _col(frame, column, pl.Int32) + years_after
        known = pl.datetime(year, month, 1, time_zone="UTC")
        key = _key(*(_col(frame, c, pl.Utf8) for c in unit))
        return frame.select(_placed(key, known, pl.lit(RULE)))

    return place


def fixed(unit: tuple[str, ...]) -> Place:
    """Facts fixed before a player's first game, and team identity: always known."""

    def place(frame: pl.DataFrame, cal: Calendar, season: int | None = None) -> pl.DataFrame:
        key = _key(*(_col(frame, c, pl.Utf8) for c in unit))
        return frame.select(_placed(key, pl.lit(ALWAYS), pl.lit(RULE)))

    return place


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
    place: Place
    needs: tuple[str, ...]  # columns `place` reads; a column a version lacks reads as null
    after_game: Place | None = None  # history fields in a table whose rows precede the game
    note: str = ""
    _regex: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_regex", re.compile(self.pattern))

    def matches(self, key: str) -> bool:
        return self._regex.fullmatch(key) is not None


def _season_files(stem: str) -> str:
    return stem + r"_(19|20)\d{2}"


GAME_KEYS = ("game_id", "season", "week", "team")
STATISTICS = per_game(1, 12, team="team")
CONTRACT_UNIT = ("otc_id", "team", "year_signed", "years", "value")
COMBINE_UNIT = ("season", "player_name", "pfr_id", "cfb_id")

TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "schedules/games",
        "schedules",
        schedule_rows,
        ("game_id",),
        after_game=per_game(1, 12),
        note="Before the season; scores, weather and referee after the game",
    ),
    TableSpec(_season_files("pbp/play_by_play"), "pbp", per_game(1, 12), ("game_id",)),
    TableSpec(
        _season_files("stats_player/stats_player_week"), "stats_player", STATISTICS, GAME_KEYS
    ),
    TableSpec(_season_files("stats_team/stats_team_week"), "stats_team", STATISTICS, GAME_KEYS),
    TableSpec(
        r"stats_player/stats_player_(reg|post|regpost)_(19|20)\d{2}",
        "stats_player",
        after_season(),
        ("season",),
        note="Season aggregates are rebuilt weekly",
    ),
    TableSpec(
        r"stats_team/stats_team_(reg|post|regpost)_(19|20)\d{2}",
        "stats_team",
        after_season(),
        ("season",),
    ),
    TableSpec(
        _season_files("snap_counts/snap_counts"),
        "snap_counts",
        per_game(2, 12, team="team"),
        GAME_KEYS,
    ),
    TableSpec(
        r"nextgen_stats/ngs_((19|20)\d{2}_)?(passing|receiving|rushing)",
        "nextgen_stats",
        ngs_rows,
        ("season", "week", "season_type", "team_abbr"),
    ),
    TableSpec(
        r"pfr_advstats/advstats_week_(pass|rush|rec|def)_(19|20)\d{2}",
        "pfr_advstats",
        per_game(4, 0, team="team"),
        GAME_KEYS,
    ),
    TableSpec(
        r"pfr_advstats/advstats_season_(pass|rush|rec|def)(_(19|20)\d{2})?",
        "pfr_advstats",
        after_season(),
        ("season",),
    ),
    TableSpec(
        _season_files("ftn_charting/ftn_charting"),
        "ftn_charting",
        per_game(4, 0, game_id="nflverse_game_id"),
        ("nflverse_game_id",),
    ),
    TableSpec(
        _season_files("injuries/injuries"),
        "injuries",
        injury_rows,
        ("season", "week", "team", "gsis_id", "date_modified"),
    ),
    TableSpec(
        _season_files("weekly_rosters/roster_weekly"),
        "weekly_rosters",
        week_rows,
        ("season", "week", "team"),
    ),
    TableSpec(_season_files("rosters/roster"), "rosters", after_season(), ("season",)),
    TableSpec(
        _season_files("depth_charts/depth_charts"),
        "depth_charts",
        depth_rows,
        ("dt", "team", "season", "week", "club_code"),
    ),
    TableSpec("trades/trades", "trades", trade_rows, ("trade_id", "trade_date")),
    TableSpec("players/players", "players", fixed(("gsis_id",)), ("gsis_id",)),
    TableSpec("combine/combine", "combine", yearly("season", 5, unit=COMBINE_UNIT), COMBINE_UNIT),
    TableSpec(
        "draft_picks/draft_picks",
        "draft_picks",
        yearly("season", 5, unit=("season", "round", "pick")),
        ("season", "round", "pick"),
    ),
    TableSpec(
        "contracts/historical_contracts",
        "contracts",
        yearly("year_signed", 6, years_after=1, unit=CONTRACT_UNIT),
        CONTRACT_UNIT,
    ),
    TableSpec("teams/teams_colors_logos", "teams", fixed(("team_abbr",)), ("team_abbr",)),
    TableSpec("officials/officials", "officials", per_game(1, 12), ("game_id",)),
    TableSpec(
        _season_files("pbp_participation/pbp_participation"),
        "pbp_participation",
        after_season(),
        ("season",),
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
