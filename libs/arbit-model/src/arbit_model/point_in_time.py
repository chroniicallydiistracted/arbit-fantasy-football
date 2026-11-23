"""Point-in-time reads of nflverse tables: only what was known before a decision time.

ADR-007 as amended and clarified by the owner (OWN-066, OWN-072). For a decision time T and one
file, in order of precedence (A5):

1. **Held:** whatever Arbit held just before T counts, all of it, as soon as Arbit has it.
2. **Fetched after a gap:** when T falls in a capture gap (or before Arbit's first read), a unit
   of rows first held by the version read after T counts if its known-from time is before T.
3. **Known-from** for a unit first held by a version observed at t1, with Arbit's previous read
   at p: t1 when p is within the stale window (decision 3, basis `observed`). Otherwise the
   earlier of t1 and the later of the unit's source timestamp or family rule and p (A1, basis
   `source-timestamp` or `retrospective-rule`). p is None before the first read.

Units are the rows that travel together between versions (`timing.TableSpec`), so a game's plays
or a player-week's report always come from one version. Every returned row carries
`_known_from` and `_basis`, and every reading a lineage record: the versions used, the gap it
fell in and counts by basis. Fields the catalog excludes by policy are refused unless their gate
is named (OWN-067 lines for the Q-014 study). Tables without a timing rule are refused.

Placement and filtering work on whole columns (polars); a reading returns a frame (R-071).
"""

from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore

from arbit_model.fields import load_catalog
from arbit_model.timing import (
    ALWAYS,
    INSTANT,
    KNOWN,
    NEVER,
    RULE_BASIS,
    RULE_TIMING,
    UNIT,
    Calendar,
    ColumnTiming,
    TableSpec,
    key_season,
    short_key,
    spec_for,
)
from arbit_model.vintages import KeyHistory, StoredVintages, VintageSource

KNOWN_FROM = "_known_from"
BASIS = "_basis"
MANIFEST = "_manifest"  # the version a row came from
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
FIRST_SCHEMA = pl.Schema(
    [
        (UNIT, pl.String()),
        ("_rule", INSTANT),
        ("_rbasis", pl.String()),
        ("_after", INSTANT),
        ("_first", pl.Int32()),
    ]
)


class PolicyRefused(ValueError):
    """A field the catalog keeps from the Model by policy, read without its gate."""


@dataclass(frozen=True)
class Reading:
    key: str
    at: datetime
    columns: tuple[str, ...]
    frame: pl.DataFrame  # the requested columns, `_known_from`, `_basis` and `_manifest`
    lineage: Mapping[str, Any]

    @property
    def rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.frame.to_dicts())


class PointInTime:
    def __init__(
        self,
        source: VintageSource,
        calendar: Calendar,
        *,
        catalog: Mapping[str, Any] | None = None,
        gates: Iterable[str] = (),
        cached_placements: int = 8,
        cached_parts: int = 16,
    ) -> None:
        self.source, self.calendar = source, calendar
        self.catalog = catalog if catalog is not None else load_catalog()
        self.gates = frozenset(gates)
        self.cached_placements, self.cached_parts = cached_placements, cached_parts
        self._units: dict[tuple[str, str], pl.DataFrame] = {}
        self._rows: OrderedDict[tuple[str, str], pl.Series] = OrderedDict()
        self._first: dict[str, pl.DataFrame] = {}
        self._scanned: dict[str, int] = {}
        self._versions: dict[str, pl.DataFrame] = {}
        self._parts: OrderedDict[tuple[Any, ...], tuple[pl.DataFrame, pl.DataFrame]] = OrderedDict()

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
        parts: list[pl.DataFrame] = []
        labels: list[pl.DataFrame] = []
        untimed = admitted = 0
        if held is not None:
            rows, known = self._part(short, spec, history, held, None, columns, timings)
            parts.append(rows)
            labels.append(known)
        if fetched is not None and fetched != held:
            rows, known = self._part(short, spec, history, fetched, held, columns, timings)
            early = pl.col(KNOWN_FROM) < at
            untimed = known.filter(~early & pl.col("_untimed")).height
            known = known.filter(early)
            admitted = known.height
            if admitted:
                parts.append(rows.filter(early))
                labels.append(known)
        frame = (
            pl.concat(parts, how="diagonal_relaxed")
            if len(parts) > 1
            else parts[0]
            if parts
            else pl.DataFrame(
                schema={
                    **{c: pl.Null for c in columns},
                    KNOWN_FROM: INSTANT,
                    BASIS: pl.Utf8,
                    MANIFEST: pl.Utf8,
                }
            )
        )
        units = pl.concat(labels, how="diagonal_relaxed") if labels else None
        counts = (
            dict(units[BASIS].value_counts().sort(BASIS).iter_rows())
            if units is not None and units.height
            else {}
        )
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
            "rows": frame.height,
            "units": units.height if units is not None else 0,
            "unitsByBasis": counts,
            "boundedByGapStart": int(units["_bounded"].sum()) if units is not None else 0,
            "untimedNotAdmitted": untimed,
        }
        return Reading(short, at, columns, frame, lineage)

    def _part(
        self,
        key: str,
        spec: TableSpec,
        history: KeyHistory,
        index: int,
        held: int | None,
        columns: tuple[str, ...],
        timings: set[ColumnTiming],
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Rows and unit labels a version contributes, whatever the decision time within its
        span: every unit when it is the version held, or, read after a gap, the units first held
        by it and not held before (`held` names the version held). Cached."""
        name = (key, index, held, columns, frozenset(timings))
        cached = self._parts.get(name)
        if cached is not None:
            self._parts.move_to_end(name)
            return cached
        units = self._version_units(key, spec, history, index)
        if held is not None:
            first = self._first_frame(key, spec, history, index)
            units = (
                units.join(
                    self._version_units(key, spec, history, held).select(UNIT), on=UNIT, how="anti"
                )
                .join(first.select(UNIT, "_first"), on=UNIT, how="left")
                .filter(pl.col("_first") == index)  # never held before; not dropped and back
                .drop("_first")
            )
        known = self._known(key, spec, history, units, index, timings)
        part = (self._labeled(key, spec, history, index, columns, known), known)
        self._parts[name] = part
        while len(self._parts) > self.cached_parts:
            self._parts.popitem(last=False)
        return part

    def _timings(self, spec: TableSpec, columns: Sequence[str]) -> set[ColumnTiming]:
        fields = self.catalog["fields"].get(spec.family, {})
        timings: set[ColumnTiming] = set()
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
            if timing is not None:
                timings.add(timing)
        return timings

    def _placement(
        self, key: str, spec: TableSpec, history: KeyHistory, index: int
    ) -> pl.DataFrame:
        """Each row's unit, rule time, rule basis and after-game time in one version."""
        frame = self.source.table(history.versions[index], spec.needs)
        season = key_season(key)
        placed = spec.place(frame, self.calendar, season)
        after = (
            spec.after_game(frame, self.calendar, season).select(pl.col(KNOWN).alias("_after"))
            if spec.after_game is not None
            else pl.DataFrame({"_after": pl.Series([None] * frame.height, dtype=INSTANT)})
        )
        return placed.hstack(after)

    def _row_units(self, key: str, spec: TableSpec, history: KeyHistory, index: int) -> pl.Series:
        """Each row's unit in one version, in file order (recent versions cached)."""
        name = (key, history.versions[index].parquet)
        cached = self._rows.get(name)
        if cached is None:
            cached = self._placement(key, spec, history, index)[UNIT]
            self._rows[name] = cached
            while len(self._rows) > self.cached_placements:
                self._rows.popitem(last=False)
        self._rows.move_to_end(name)
        return cached

    def _version_units(
        self, key: str, spec: TableSpec, history: KeyHistory, index: int
    ) -> pl.DataFrame:
        """One row per unit of a version: its latest rule time (null if any row is untimed), its
        basis and its latest after-game time (null likewise)."""
        name = (key, history.versions[index].parquet)
        cached = self._units.get(name)
        if cached is not None:
            return cached
        placed = self._placement(key, spec, history, index)
        units = (
            placed.group_by(UNIT, maintain_order=True)
            .agg(
                pl.col(KNOWN).max().alias("_rule"),
                pl.col(KNOWN).null_count().alias("_rule_nulls"),
                pl.col(RULE_BASIS).first().alias("_rbasis"),
                pl.col("_after").max().alias("_after"),
                pl.col("_after").null_count().alias("_after_nulls"),
            )
            .select(
                UNIT,
                pl.when(pl.col("_rule_nulls") > 0)
                .then(None)
                .otherwise(pl.col("_rule"))
                .alias("_rule"),
                "_rbasis",
                pl.when(pl.col("_after_nulls") > 0)
                .then(None)
                .otherwise(pl.col("_after"))
                .alias("_after"),
            )
        )
        self._units[name] = units
        return units

    def _first_frame(
        self, key: str, spec: TableSpec, history: KeyHistory, through: int
    ) -> pl.DataFrame:
        """Each unit's first holding version, with its rule times there, scanning versions up to
        `through`. Later versions never change a unit already found, so a decision never depends
        on them."""
        first = self._first.get(key, pl.DataFrame(schema=FIRST_SCHEMA))
        start = self._scanned.get(key, 0)
        for index in range(start, through + 1):
            new = (
                self._version_units(key, spec, history, index)
                .join(first.select(UNIT), on=UNIT, how="anti")
                .with_columns(pl.lit(index, pl.Int32).alias("_first"))
                .select(list(FIRST_SCHEMA))
            )
            first = pl.concat([first, new.cast(FIRST_SCHEMA)])
        self._first[key] = first
        self._scanned[key] = max(start, through + 1)
        return first

    def _version_facts(self, key: str, history: KeyHistory) -> pl.DataFrame:
        """For each version: when Arbit observed it and Arbit's previous read."""
        cached = self._versions.get(key)
        if cached is not None:
            return cached
        rows = [
            (index, version.observed_at, history.read_before(version.observed_at))
            for index, version in enumerate(history.versions)
        ]
        facts = pl.DataFrame(
            rows, schema={"_first": pl.Int32, "_obs": INSTANT, "_prev": INSTANT}, orient="row"
        )
        self._versions[key] = facts
        return facts

    def _known(
        self,
        key: str,
        spec: TableSpec,
        history: KeyHistory,
        units: pl.DataFrame,
        holder: int,
        timings: set[ColumnTiming],
    ) -> pl.DataFrame:
        """Known-from time and basis of each unit held by version `holder`, whether the gap's
        start bound it, and whether its rule could not time it."""
        first = self._first_frame(key, spec, history, holder)
        facts = (
            units.select(UNIT)
            .join(first, on=UNIT, how="left", maintain_order="left")
            .join(self._version_facts(key, history), on="_first", how="left", maintain_order="left")
        )
        rule = pl.col("_rule")
        if "after_game" in timings:
            rule = (
                pl.when(rule.is_null() | pl.col("_after").is_null())
                .then(None)
                .otherwise(pl.max_horizontal(rule, pl.col("_after")))
            )
        if "as_imported" in timings:
            rule = pl.lit(NEVER, INSTANT)
        observed, previous = pl.col("_obs"), pl.col("_prev")
        gap = previous.is_null() | ((observed - previous) > pl.lit(history.stale))
        floor = pl.coalesce(previous, pl.lit(ALWAYS, INSTANT))
        held_as_read = ~gap | rule.is_null() | (rule >= observed) | (floor >= observed)
        bounded = ~held_as_read & (rule < floor)
        return facts.select(
            UNIT,
            pl.when(held_as_read)
            .then(observed)
            .when(bounded)
            .then(floor)
            .otherwise(rule)
            .alias(KNOWN_FROM),
            pl.when(held_as_read)
            .then(pl.lit("observed"))
            .otherwise(pl.col("_rbasis"))
            .alias(BASIS),
            bounded.alias("_bounded"),
            rule.is_null().alias("_untimed"),
        )

    def _labeled(
        self,
        key: str,
        spec: TableSpec,
        history: KeyHistory,
        index: int,
        columns: Sequence[str],
        known: pl.DataFrame,
    ) -> pl.DataFrame:
        """The version's rows of the units in `known`, in file order, with their labels."""
        rows = self.source.table(history.versions[index], columns)
        units = self._row_units(key, spec, history, index)
        return (
            rows.with_columns(units.alias(UNIT))
            .join(
                known.select(UNIT, KNOWN_FROM, BASIS),
                on=UNIT,
                how="inner",
                maintain_order="left",
            )
            .drop(UNIT)
            .with_columns(pl.lit(history.versions[index].manifest).alias(MANIFEST))
        )


def schedule_calendar(source: VintageSource) -> Calendar:
    """The calendar from the newest schedule file Arbit holds."""
    history = source.history("schedules/games")
    if not history.versions:
        raise LookupError("DATASET_UNAVAILABLE: schedules/games")
    return Calendar(source.table(history.versions[-1], CALENDAR_COLUMNS).to_dicts())
