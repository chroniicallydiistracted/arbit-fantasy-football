"""Each player's availability at a decision time, in the owner's order (OWN-073).

The owner's words: "We should have a better route for more up to date injuries, however game day
decisions should be the final say." For one week and decision time T:

1. **Game day, final.** On the player's game day, ESPN's fantasy injury status (OWN-064) is final
   when Arbit read ESPN within 15 minutes before T. ESPN marks inactives `OUT` 62–86 minutes
   before kickoff (SRC-33), so this is where game-day decisions arrive.
2. **The freshest copy of NFL's injury report.** NFL's report, game status and practice, reaches
   Arbit two ways: Arbit's own capture at 12:00 and 19:15 Eastern (OWN-063), and nflverse's daily
   republication of the same report, read through the point-in-time reader. For each player the
   copy Arbit had more recently wins (the capture on a tie).
3. **Unknown.** A player no source lists has no report. On game day without a current ESPN read,
   game-day status is unknown, never assumed active (R-066); the lineage says so.

Every row carries its source, `_known_from` and `_basis`. Status codes are upper case (`OUT`,
`DOUBTFUL`, `QUESTIONABLE`, ESPN's `ACTIVE` or `INJURY_RESERVE`); practice is `FULL`, `LIMITED`
or `DNP`. ESPN's fantasy status is status only; no projection field is read.
"""

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import polars as pl
from arbit_data.availability.espn_status import StatusAsOf, status_as_of
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import entity_alias
from sqlalchemy import select

from arbit_model.point_in_time import BASIS, KNOWN_FROM, PointInTime
from arbit_model.timing import EASTERN, INSTANT, Game

Source = Literal["espn-game-day", "nfl-report", "nflverse-report"]
COLUMNS = ("gsis_id", "status", "practice", "source", KNOWN_FROM, BASIS, "final")
SCHEMA = pl.Schema(
    [
        ("gsis_id", pl.String()),
        ("status", pl.String()),
        ("practice", pl.String()),
        ("source", pl.String()),
        (KNOWN_FROM, INSTANT),
        (BASIS, pl.String()),
        ("final", pl.Boolean()),
    ]
)
PRACTICE: Mapping[str, str] = {
    "FULL": "FULL",
    "LIMITED": "LIMITED",
    "DIDNOT": "DNP",
    "FULL PARTICIPATION IN PRACTICE": "FULL",
    "LIMITED PARTICIPATION IN PRACTICE": "LIMITED",
    "DID NOT PARTICIPATE IN PRACTICE": "DNP",
}
NFLVERSE_COLUMNS = ("week", "gsis_id", "report_status", "practice_status")


@dataclass(frozen=True)
class CaptureRef:
    observed_at: datetime  # when the capture's reads finished: when the Model may use it
    manifest: str
    week: tuple[int, str, int] | None
    errors: tuple[str, ...]


class AvailabilitySource(Protocol):
    def captures(self) -> Sequence[CaptureRef]: ...

    def report(self, capture: CaptureRef) -> pl.DataFrame:
        """The capture's game status table: season, week, gsis_id, game_status, practice_status."""
        ...

    def espn(self, season: int, at: datetime) -> StatusAsOf: ...

    def gsis_by_entity(self) -> Mapping[str, str]: ...


@dataclass(frozen=True)
class AvailabilityReading:
    season: int
    week: int
    at: datetime
    game_day: bool
    frame: pl.DataFrame  # one row per GSIS ID, COLUMNS
    lineage: Mapping[str, Any]

    @property
    def rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.frame.to_dicts())


def is_game_day(game: Game, at: datetime) -> bool:
    """`at` falls on the game's date in US Eastern time, no later than its kickoff."""
    if at.tzinfo is None:
        raise ValueError("DECISION_TIME_NEEDS_TIMEZONE")
    if at.astimezone(EASTERN).date() != game.gameday:
        return False
    return game.kickoff is None or at <= game.kickoff


def _practice(column: pl.Expr) -> pl.Expr:
    return column.str.to_uppercase().replace_strict(PRACTICE, default=None)


def _report_rows(frame: pl.DataFrame, source: Source, status: str, practice: str) -> pl.DataFrame:
    return frame.select(
        pl.col("gsis_id").cast(pl.String),
        pl.col(status).cast(pl.String).str.to_uppercase().alias("status"),
        _practice(pl.col(practice).cast(pl.String)).alias("practice"),
        pl.lit(source).alias("source"),
        pl.col(KNOWN_FROM).cast(INSTANT),
        pl.col(BASIS).cast(pl.String),
        pl.lit(False).alias("final"),
    ).filter(pl.col("gsis_id").is_not_null())


def availability(
    source: AvailabilitySource,
    pit: PointInTime,
    *,
    season: int,
    week: int,
    at: datetime,
    game_day: bool,
) -> AvailabilityReading:
    """Availability for every player a source lists for `season`/`week`, as known before `at`."""
    if at.tzinfo is None:
        raise ValueError("DECISION_TIME_NEEDS_TIMEZONE")
    at = at.astimezone(UTC)
    nflverse = pit.read(f"injuries/injuries_{season}", NFLVERSE_COLUMNS, at)
    republished = _report_rows(
        nflverse.frame.filter(pl.col("week") == week),
        "nflverse-report",
        "report_status",
        "practice_status",
    )
    capture = next(
        (
            c
            for c in sorted(source.captures(), key=lambda c: c.observed_at, reverse=True)
            if c.observed_at < at and "nfl.injuries" not in c.errors
        ),
        None,
    )
    captured = pl.DataFrame(schema=SCHEMA)
    if capture is not None:
        table = source.report(capture).filter(
            (pl.col("season") == season) & (pl.col("week") == week)
        )
        captured = _report_rows(
            table.with_columns(
                pl.lit(capture.observed_at, INSTANT).alias(KNOWN_FROM),
                pl.lit("observed").alias(BASIS),
            ),
            "nfl-report",
            "game_status",
            "practice_status",
        )
    report = (
        pl.concat([captured, republished])
        .with_columns((pl.col("source") == "nfl-report").alias("_capture"))
        .sort([KNOWN_FROM, "_capture"], descending=True)
        .unique("gsis_id", keep="first", maintain_order=True)
        .drop("_capture")
    )
    espn_lineage: dict[str, Any] | None = None
    frame = report
    if game_day:
        status = source.espn(season, at)
        espn_lineage = {
            "current": status.current,
            "lastReadAt": status.last_read_at.isoformat() if status.last_read_at else None,
            "documentPublishedAt": (
                status.document_published_at.isoformat() if status.document_published_at else None
            ),
        }
        if status.current and status.document_published_at is not None:
            gsis = source.gsis_by_entity()
            mapped = [
                (gsis[entity], player.code)
                for entity, player in status.players.items()
                if entity in gsis
            ]
            espn_lineage["players"] = len(status.players)
            espn_lineage["unmapped"] = len(status.players) - len(mapped)
            game_day_rows = pl.DataFrame(
                {
                    "gsis_id": [g for g, _ in mapped],
                    "status": [code for _, code in mapped],
                    "practice": [None] * len(mapped),
                    "source": ["espn-game-day"] * len(mapped),
                    KNOWN_FROM: [status.document_published_at] * len(mapped),
                    BASIS: ["observed"] * len(mapped),
                    "final": [True] * len(mapped),
                },
                schema=SCHEMA,
            ).unique("gsis_id", keep="first", maintain_order=True)
            frame = pl.concat(
                [
                    game_day_rows,
                    report.join(game_day_rows.select("gsis_id"), on="gsis_id", how="anti"),
                ]
            )
    by_source = (
        dict(frame["source"].value_counts().sort("source").iter_rows()) if frame.height else {}
    )
    lineage = {
        "season": season,
        "week": week,
        "at": at.isoformat(),
        "gameDay": game_day,
        "gameDayUnknown": game_day and not (espn_lineage or {}).get("current", False),
        "espn": espn_lineage,
        "nflCapture": (
            {
                "observedAt": capture.observed_at.isoformat(),
                "manifest": capture.manifest,
                "rows": captured.height,
            }
            if capture is not None
            else None
        ),
        "nflverse": {k: nflverse.lineage[k] for k in ("held", "inGap", "unitsByBasis")},
        "players": frame.height,
        "bySource": by_source,
    }
    return AvailabilityReading(season, week, at, game_day, frame.select(COLUMNS), lineage)


class StoredAvailability:
    """NFL captures from the availability store and ESPN status from the database. Read only."""

    def __init__(self, uow: UnitOfWork, root: Path | None = None) -> None:
        self.uow = uow
        self.root = root or Path(os.environ.get("ARBIT_AVAILABILITY_PATH", "data/availability"))
        self.store = ObjectStore(self.root / "objects")
        self._gsis: dict[str, str] | None = None

    def captures(self) -> list[CaptureRef]:
        index = self.root / "captures.jsonl"
        if not index.exists():
            return []
        refs = []
        for line in index.read_text().splitlines():
            entry = json.loads(line)
            week = entry.get("week")
            refs.append(
                CaptureRef(
                    observed_at=datetime.fromisoformat(entry["observedAt"]),
                    manifest=entry["manifest"],
                    week=(int(week[0]), str(week[1]), int(week[2])) if week else None,
                    errors=tuple(entry.get("errors") or ()),
                )
            )
        return refs

    def report(self, capture: CaptureRef) -> pl.DataFrame:
        manifest = json.loads(self.store.read(capture.manifest))
        digest = manifest["tables"]["gameStatus"]["parquet"]
        return pl.read_parquet(self.store.verify(digest).path)

    def espn(self, season: int, at: datetime) -> StatusAsOf:
        return status_as_of(self.uow, season, at)

    def gsis_by_entity(self) -> Mapping[str, str]:
        if self._gsis is None:
            with self.uow.engine.connect() as c:
                rows = c.execute(
                    select(entity_alias.c.entity_id, entity_alias.c.external_id).where(
                        entity_alias.c.provider == "gsis",
                        entity_alias.c.kind == "athlete",
                        entity_alias.c.valid_to.is_(None),
                    )
                ).all()
            self._gsis = {str(entity): str(gsis) for entity, gsis in rows}
        return self._gsis
