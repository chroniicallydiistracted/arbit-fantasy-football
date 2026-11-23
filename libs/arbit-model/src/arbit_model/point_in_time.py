"""Point-in-time reads of nflverse tables: only what was known before a decision time.

ADR-007 as amended by the owner (OWN-066). For a decision time T and one file:

- **Held:** rows of the version Arbit held just before T. Arbit had them, so they count.
- **Fetched after a gap:** when T falls in a capture gap (or before Arbit's first read), a unit
  of rows first held by the version read after T counts if its known-from time is before T.
- **Known-from** for a unit first held by a version observed at t1, with Arbit's previous read
  at p: t1 when p is within the stale window (decision 3, basis `observed`). Otherwise the
  earlier of t1 and the later of the unit's source time or family rule and p (A1, basis
  `source-timestamp` or `retrospective-rule`). p is None before the first read.

Units are the rows that travel together between versions (`timing.TableSpec`), so a game's plays
or a player-week's report always come from one version. Every returned row carries
`_known_from` and `_basis`, and every reading a lineage record: the versions used, the gap it
fell in and counts by basis. Fields the catalog excludes by policy are refused unless their gate
is named (OWN-067 lines for the Q-014 study). Tables without a timing rule are refused.
"""

from collections import Counter
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore

from arbit_model.fields import load_catalog
from arbit_model.timing import (
    ALWAYS,
    NEVER,
    RULE_TIMING,
    Basis,
    Calendar,
    ColumnTiming,
    Placement,
    TableSpec,
    key_season,
    short_key,
    spec_for,
)
from arbit_model.vintages import KeyHistory, StoredVintages, Version, VintageSource

KNOWN_FROM = "_known_from"
BASIS = "_basis"
CALENDAR_COLUMNS = (
    "game_id",
    "old_game_id",
    "season",
    "week",
    "game_type",
    "home_team",
    "away_team",
    "gameday",
    "gametime",
)
TICK = timedelta(microseconds=1)

# Columns each table's rule needs to place a row; a column a version lacks reads as None.
PLACEMENT_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "schedules": ("game_id",),
    "pbp": ("game_id",),
    "stats_player": ("game_id", "season", "week", "team"),
    "stats_team": ("game_id", "season", "week", "team"),
    "snap_counts": ("game_id", "season", "week", "team"),
    "nextgen_stats": ("season", "week", "season_type", "team_abbr"),
    "pfr_advstats": ("game_id", "season", "week", "team"),
    "ftn_charting": ("nflverse_game_id",),
    "injuries": ("season", "week", "team", "gsis_id", "date_modified"),
    "weekly_rosters": ("season", "week", "team"),
    "rosters": ("season",),
    "depth_charts": ("dt", "team", "season", "week", "club_code"),
    "trades": ("trade_id", "trade_date"),
    "players": ("gsis_id",),
    "combine": ("season", "player_name", "pfr_id", "cfb_id"),
    "draft_picks": ("season", "round", "pick"),
    "contracts": ("otc_id", "team", "year_signed", "years", "value"),
    "teams": ("team_abbr",),
    "officials": ("game_id",),
    "pbp_participation": ("season",),
}


class PolicyRefused(ValueError):
    """A field the catalog keeps from the Model by policy, read without its gate."""


@dataclass(frozen=True)
class Reading:
    key: str
    at: datetime
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    lineage: Mapping[str, Any]


@dataclass(frozen=True)
class _Unit:
    rows: tuple[int, ...]  # indices into the version's rows
    known: datetime | None  # latest rule time of its rows; None if any row is untimed
    basis: Basis
    after_game: datetime | None  # latest after-game time, when the table has one


def _later(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None or b is None:
        return None
    return max(a, b)


class PointInTime:
    def __init__(
        self,
        source: VintageSource,
        calendar: Calendar,
        *,
        catalog: Mapping[str, Any] | None = None,
        gates: Iterable[str] = (),
    ) -> None:
        self.source, self.calendar = source, calendar
        self.catalog = catalog if catalog is not None else load_catalog()
        self.gates = frozenset(gates)
        self._units: dict[tuple[str, str], dict[Hashable, _Unit]] = {}
        self._first: dict[str, dict[Hashable, int]] = {}
        self._scanned: dict[str, int] = {}

    @classmethod
    def from_store(
        cls, uow: UnitOfWork, store: ObjectStore, *, gates: Iterable[str] = ()
    ) -> "PointInTime":
        source = StoredVintages(uow, store)
        return cls(source, schedule_calendar(source), gates=gates)

    def read(self, key: str, columns: Sequence[str], at: datetime) -> Reading:
        if at.tzinfo is None:
            raise ValueError("DECISION_TIME_NEEDS_TIMEZONE")
        at = at.astimezone(UTC)
        short = short_key(key)
        spec = spec_for(short)
        columns = tuple(dict.fromkeys(columns))
        timings = self._timings(spec, columns)
        history = self.source.history(short)
        held = history.current(at)
        after_read = history.read_from(at)
        fetched = history.current(after_read + TICK) if after_read is not None else None
        out: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        bounded = untimed = admitted = 0
        held_units = self._version_units(short, spec, history, held) if held is not None else {}

        def emit(index: int, unit: _Unit, known: datetime, basis: Basis) -> None:
            rows = self.source.table(history.versions[index], columns)
            for position in unit.rows:
                row = {c: rows[position][c] for c in columns}
                row[KNOWN_FROM], row[BASIS] = known, basis
                out.append(row)
            counts[basis] += 1

        if held is not None:
            for name, unit in held_units.items():
                known, basis, was_bounded = self._known(short, spec, history, name, timings, held)
                emit(held, unit, known, basis)
                bounded += was_bounded
        if fetched is not None and fetched != held:
            first = self._first_index(short, spec, history, fetched)
            for name, unit in self._version_units(short, spec, history, fetched).items():
                if name in held_units or first[name] != fetched:
                    continue  # held at the decision time, or dropped before it
                known, basis, was_bounded = self._known(
                    short, spec, history, name, timings, fetched
                )
                if known >= at:
                    untimed += unit.known is None
                    continue
                emit(fetched, unit, known, basis)
                admitted += 1
                bounded += was_bounded
        previous = history.read_before(at)
        lineage = {
            "key": short,
            "at": at.isoformat(),
            "columns": list(columns),
            "held": history.versions[held].manifest if held is not None else None,
            "fetchedAfter": (
                history.versions[fetched].manifest if fetched is not None and admitted else None
            ),
            "readBefore": previous.isoformat() if previous else None,
            "readAfter": after_read.isoformat() if after_read else None,
            "inGap": previous is None
            or (after_read is not None and after_read - previous > history.stale),
            "rows": len(out),
            "units": counts.total(),
            "unitsByBasis": {b: counts[b] for b in sorted(counts)},
            "boundedByGapStart": bounded,
            "untimedNotAdmitted": untimed,
        }
        return Reading(short, at, columns, tuple(out), lineage)

    def _timings(self, spec: TableSpec, columns: Sequence[str]) -> dict[str, ColumnTiming | None]:
        fields = self.catalog["fields"].get(spec.family, {})
        timings: dict[str, ColumnTiming | None] = {}
        for column in columns:
            entry = fields.get(column)
            if entry is None:
                raise LookupError(f"UNCATALOGUED_FIELD: {spec.family}.{column}")
            rule, use = entry["rule"], entry["use"]
            if use == "excluded":
                decision = self.catalog["rules"][rule].get("decision")
                if decision is None or decision not in self.gates:
                    raise PolicyRefused(f"EXCLUDED_FIELD: {spec.family}.{column} ({rule})")
            timing = RULE_TIMING.get(rule)
            if timing is None and use == "as_imported":
                timing = "as_imported"
            if timing is None and use == "history" and spec.after_game is not None:
                timing = "after_game"
            if timing == "after_game" and spec.after_game is None:
                timing = None
            timings[column] = timing
        return timings

    def _version_units(
        self, key: str, spec: TableSpec, history: KeyHistory, index: int
    ) -> dict[Hashable, _Unit]:
        version = history.versions[index]
        cached = self._units.get((key, version.parquet))
        if cached is not None:
            return cached
        needs = PLACEMENT_COLUMNS[spec.family]
        rows = self.source.table(version, needs)
        season = key_season(key)
        grouped: dict[Hashable, list[tuple[int, Placement, Placement | None]]] = {}
        for position, row in enumerate(rows):
            placed = spec.locate(row, self.calendar, season)
            after = spec.after_game(row, self.calendar, season) if spec.after_game else None
            grouped.setdefault(placed.unit, []).append((position, placed, after))
        units: dict[Hashable, _Unit] = {}
        for name, members in grouped.items():
            known: datetime | None = ALWAYS
            after_game: datetime | None = ALWAYS if spec.after_game else None
            for _, placed, after in members:
                known = _later(known, placed.known)
                if after is not None:
                    after_game = _later(after_game, after.known)
            units[name] = _Unit(
                rows=tuple(position for position, _, _ in members),
                known=known,
                basis=members[0][1].basis,
                after_game=after_game,
            )
        self._units[(key, version.parquet)] = units
        return units

    def _first_index(
        self, key: str, spec: TableSpec, history: KeyHistory, through: int
    ) -> dict[Hashable, int]:
        """The first version holding each unit, scanning versions up to `through`. Later versions
        never change a unit already found, so a decision never depends on them."""
        first = self._first.setdefault(key, {})
        start = self._scanned.get(key, 0)
        for index in range(start, through + 1):
            for name in self._version_units(key, spec, history, index):
                first.setdefault(name, index)
        self._scanned[key] = max(start, through + 1)
        return first

    def _known(
        self,
        key: str,
        spec: TableSpec,
        history: KeyHistory,
        name: Hashable,
        timings: Mapping[str, ColumnTiming | None],
        holder: int,
    ) -> tuple[datetime, Basis, bool]:
        """Known-from time and basis of a unit held by version `holder`, and whether the gap's
        start bound it."""
        first = self._first_index(key, spec, history, holder)[name]
        version: Version = history.versions[first]
        observed = version.observed_at
        previous = history.read_before(observed)
        if previous is not None and observed - previous <= history.stale:
            return observed, "observed", False
        unit = self._version_units(key, spec, history, first)[name]
        rule: datetime | None = unit.known
        for timing in set(timings.values()):
            if timing == "as_imported":
                rule = NEVER
            elif timing == "after_game":
                rule = _later(rule, unit.after_game)
        if rule is None or rule >= observed:
            return observed, "observed", False
        floor = previous if previous is not None else ALWAYS
        if floor >= observed:
            return observed, "observed", False
        if rule < floor:
            return floor, unit.basis, True
        return rule, unit.basis, False


def schedule_calendar(source: VintageSource) -> Calendar:
    """The calendar from the newest schedule file Arbit holds."""
    history = source.history("schedules/games")
    if not history.versions:
        raise LookupError("DATASET_UNAVAILABLE: schedules/games")
    return Calendar(source.table(history.versions[-1], CALENDAR_COLUMNS))
