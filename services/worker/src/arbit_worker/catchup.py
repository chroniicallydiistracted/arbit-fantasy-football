"""Catch-up after downtime (ENG-052): read what was missed while the PC was off or asleep.

The owner, 2026-11-22: "create a retroactive data ingestion script that can pull all outstanding
data when/if my local machine has been down for some time".

Most lanes recover by themselves as soon as the worker runs again:
- the FFA league reads its current state, then every finished week without a stored lineup and
  every period's transactions (`league_history`);
- the statistics lane imports the current revision of every changed nflverse file;
- the availability lane reads NFL's injury report for the whole season on every capture.

Games are the exception. The ESPN and NFL live lanes follow only the current week, so a week that
started and ended while nothing ran would never be read. This module finds finished games without
a complete record and reads each once: ESPN's scoreboard, summary and plays, and the NFL API's full
game record, which owns the plays when it passes the usual final checks.

Some things are not served again and stay unknown for a gap (ADR-007 A4): ESPN's fantasy injury
status at the time, live play timing and replaced nflverse revisions. Every run appends a receipt
to a private, append-only file: which sources were behind when it started, and for every game when
it kicked off and when Arbit read it. Model readers then apply ADR-007 A1, where a value counts
from the source's own time, never from the late read.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from arbit_data import freshness
from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.live.feed import LiveFeed
from arbit_data.live.nfl_feed import FINAL as NFL_FINAL
from arbit_data.live.nfl_feed import NflFeed
from arbit_data.schema import nfl_api_game, nfl_game, nfl_schedule_game
from sqlalchemy import Connection, func, select

# Kickoff to a settled final, overtime and delays included. Younger games belong to the live lanes.
GAME_LENGTH = timedelta(hours=5)
# ESPN's regular season. Postseason catch-up waits until a playoff week's shapes are observed
# (R-059); the live lanes still follow a current postseason week.
REGULAR_SEASON = 2
NFL_REGULAR_SEASON = "REG"
# ESPN's pro schedule numbers playoff games as scoring periods after the 18 regular-season weeks.
REGULAR_SEASON_WEEKS = 18
RECEIPTS = "receipts.jsonl"
FORMAT = "arbit-catchup-v1"
STOP_CODES = frozenset({"RATE_LIMITED", "SOURCE_COOLDOWN"})


def catchup_root() -> Path:
    return Path(os.environ.get("ARBIT_CATCHUP_PATH", "data/catchup"))


@dataclass(frozen=True)
class MissingGame:
    """A scheduled game that should be over but has no complete stored record."""

    event_id: str
    period: int
    kickoff: datetime
    stored: bool  # ESPN's scoreboard row exists
    final: bool  # and it says the game is final
    summary: bool
    plays: bool  # ESPN's plays are stored
    nfl_record: bool  # the NFL API's final record is stored and owns the plays


def _scalar_int(c: Connection, statement: Any) -> int | None:
    value = c.scalar(statement)
    return int(value) if value is not None else None


def first_captured_period(c: Connection, season: int) -> int | None:
    """The first regular-season week Arbit stored any game for: where capture began."""
    return _scalar_int(
        c,
        select(func.min(nfl_game.c.week)).where(
            nfl_game.c.season == season, nfl_game.c.season_type == REGULAR_SEASON
        ),
    )


def first_nfl_period(c: Connection, season: int) -> int | None:
    """The first regular-season week the NFL lane read a game record for. Earlier weeks keep the
    ESPN record they were reviewed with; catch-up adds NFL records only from here."""
    return _scalar_int(
        c,
        select(func.min(nfl_api_game.c.week)).where(
            nfl_api_game.c.season == season,
            nfl_api_game.c.season_type == NFL_REGULAR_SEASON,
            nfl_api_game.c.details_observed_at.is_not(None),
        ),
    )


def current_week(c: Connection, season: int) -> tuple[int, int] | None:
    """The live lanes' week: the season's latest stored week (`store.game_timings`)."""
    row = c.execute(
        select(nfl_game.c.season_type, nfl_game.c.week)
        .where(nfl_game.c.season == season)
        .order_by(nfl_game.c.season_type.desc(), nfl_game.c.week.desc())
        .limit(1)
    ).first()
    return (int(row.season_type), int(row.week)) if row is not None else None


def outstanding_games(
    uow: UnitOfWork, season: int, now: datetime, *, from_period: int | None = None
) -> list[MissingGame]:
    """Regular-season games that should be over, outside the live lanes' week, with no complete
    record: not stored, stored before they finished, or missing a summary or plays. By default
    only weeks from the first captured one; `from_period` reaches further back."""
    with uow.engine.connect() as c:
        start = from_period if from_period is not None else first_captured_period(c, season)
        if start is None:
            return []
        current = current_week(c, season)
        rows = c.execute(
            select(
                nfl_schedule_game.c.event_id,
                nfl_schedule_game.c.scoring_period,
                nfl_schedule_game.c.kickoff,
                nfl_game.c.event_id.label("stored"),
                nfl_game.c.phase,
                nfl_game.c.summary_observed_at,
                nfl_game.c.plays_observed_at,
                nfl_api_game.c.details_phase,
            )
            .select_from(
                nfl_schedule_game.outerjoin(
                    nfl_game, nfl_game.c.event_id == nfl_schedule_game.c.event_id
                ).outerjoin(nfl_api_game, nfl_api_game.c.event_id == nfl_schedule_game.c.event_id)
            )
            .where(
                nfl_schedule_game.c.season == season,
                nfl_schedule_game.c.scoring_period >= start,
                nfl_schedule_game.c.scoring_period <= REGULAR_SEASON_WEEKS,
                nfl_schedule_game.c.kickoff.is_not(None),
                nfl_schedule_game.c.kickoff <= now - GAME_LENGTH,
            )
            .order_by(nfl_schedule_game.c.scoring_period, nfl_schedule_game.c.kickoff)
        ).all()
    missing = []
    for r in rows:
        if current is not None and (REGULAR_SEASON, r.scoring_period) >= current:
            continue  # the live lanes read this week's finals themselves
        game = MissingGame(
            event_id=r.event_id,
            period=r.scoring_period,
            kickoff=r.kickoff,
            stored=r.stored is not None,
            final=r.phase == "final",
            summary=r.summary_observed_at is not None,
            plays=r.plays_observed_at is not None,
            nfl_record=r.details_phase in NFL_FINAL,
        )
        if not (game.final and game.summary and (game.plays or game.nfl_record)):
            missing.append(game)
    return missing


def source_gaps(uow: UnitOfWork, season: int, now: datetime) -> list[dict[str, Any]]:
    """Sources past their stale window, as source health records them (ADR-007 A3)."""
    return [
        {
            "source": status.source,
            "state": status.state,
            "lastSuccessAt": status.last_success_at.isoformat() if status.last_success_at else None,
        }
        for status in freshness.read_sources(uow, season, now)
        if status.state in ("behind", "down")
    ]


def _game_state(uow: UnitOfWork, event_id: str) -> str | None:
    with uow.engine.connect() as c:
        phase: str | None = c.scalar(
            select(nfl_game.c.phase).where(nfl_game.c.event_id == event_id)
        )
        return phase


def recover_week(
    uow: UnitOfWork,
    period: int,
    games: list[MissingGame],
    *,
    live: LiveFeed,
    nfl: NflFeed | None,
    nfl_from: int | None,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Read one past week's missing games. The NFL record goes first so it owns the plays where
    it can; ESPN's summary always, and ESPN's plays where the NFL record doesn't exist. Raises
    only when a source asks Arbit to stop."""
    result: dict[str, Any] = {"period": period, "games": []}
    if any(not g.stored or not g.final for g in games):
        try:
            change = live.read_week_board(period, REGULAR_SEASON)
            result["board"] = {"changed": len(change.changed), "finished": len(change.finished)}
        except SourceError as error:
            if error.code in STOP_CODES:
                raise
            result["board"] = {"error": error.code}
        except ValueError:
            result["board"] = {"error": "VALIDATION_FAILED"}
    if nfl is not None and nfl_from is not None and period >= nfl_from:
        try:
            result["nfl"] = nfl.recover_week(NFL_REGULAR_SEASON, period, clock())
        except SourceError as error:
            if error.code in STOP_CODES:
                raise
            result["nfl"] = {"error": error.code}
    for game in games:
        entry: dict[str, Any] = {
            "eventId": game.event_id,
            "kickoff": game.kickoff.astimezone(UTC).isoformat(),
        }
        phase = _game_state(uow, game.event_id)
        if phase != "final":
            entry["outcome"] = "not_listed" if phase is None else "not_final"
        else:
            try:
                espn_plays = live.recover_game(game.event_id, REGULAR_SEASON)
                entry.update(outcome="recovered", plays="espn" if espn_plays else "nfl")
            except SourceError as error:
                if error.code in STOP_CODES:
                    raise
                entry.update(outcome="failed", code=error.code)
            except ValueError:
                entry.update(outcome="failed", code="VALIDATION_FAILED")
        entry["readAt"] = clock().astimezone(UTC).isoformat()
        result["games"].append(entry)
    return result


def append_receipt(root: Path, receipt: dict[str, Any]) -> None:
    """Add-only and private: one JSON line per run, synced before returning. Counts, codes, public
    game IDs and times only, never response bodies or paths."""
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    line = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    descriptor = os.open(root / RECEIPTS, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class Outcome:
    weeks: int
    recovered: int
    failed: int
    remaining_periods: tuple[int, ...]
    stopped: str | None


def run(
    uow: UnitOfWork,
    season: int,
    *,
    live: LiveFeed,
    nfl: NflFeed | None,
    trigger: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    periods: list[int] | None = None,
    from_period: int | None = None,
    gaps: list[dict[str, Any]] | None = None,
    root: Path | None = None,
) -> Outcome:
    """Recover the outstanding games of the given weeks (all outstanding weeks by default), oldest
    first, and append one receipt. A source that asks Arbit to stop ends the run early."""
    started = clock()
    plan = outstanding_games(uow, season, started, from_period=from_period)
    weeks = sorted({g.period for g in plan} & set(periods) if periods else {g.period for g in plan})
    with uow.engine.connect() as c:
        nfl_from = first_nfl_period(c, season)
    results: list[dict[str, Any]] = []
    stopped: str | None = None
    for period in weeks:
        try:
            results.append(
                recover_week(
                    uow,
                    period,
                    [g for g in plan if g.period == period],
                    live=live,
                    nfl=nfl,
                    nfl_from=nfl_from,
                    clock=clock,
                )
            )
        except SourceError as error:
            stopped = error.code
            results.append({"period": period, "stopped": error.code})
            break
    games = [g for week in results for g in week.get("games", [])]
    recovered = sum(g.get("outcome") == "recovered" for g in games)
    failed = sum(g.get("outcome") == "failed" for g in games)
    receipt = {
        "format": FORMAT,
        "trigger": trigger,
        "startedAt": started.astimezone(UTC).isoformat(),
        "finishedAt": clock().astimezone(UTC).isoformat(),
        "season": season,
        "sourcesBehindAtStart": gaps,
        "weeks": results,
        "stopped": stopped,
        "notRecoverable": [
            "ESPN fantasy injury status during the gap (ADR-007 A4)",
            "live play timing during the gap",
            "nflverse revisions replaced during the gap",
        ],
    }
    if results or gaps:
        append_receipt(root or catchup_root(), receipt)
    remaining = outstanding_games(uow, season, clock(), from_period=from_period)
    return Outcome(
        weeks=len(results),
        recovered=recovered,
        failed=failed,
        remaining_periods=tuple(sorted({g.period for g in remaining})),
        stopped=stopped,
    )


def plan_summary(
    uow: UnitOfWork, season: int, now: datetime, *, from_period: int | None = None
) -> dict[str, Any]:
    """What a run would read, for `--dry-run` and the lane's log. Counts and periods only."""
    plan = outstanding_games(uow, season, now, from_period=from_period)
    by_period: dict[int, int] = {}
    for game in plan:
        by_period[game.period] = by_period.get(game.period, 0) + 1
    with uow.engine.connect() as c:
        first = first_captured_period(c, season)
        nfl_from = first_nfl_period(c, season)
        current = current_week(c, season)
    return {
        "firstCapturedPeriod": first,
        "fromPeriod": from_period if from_period is not None else first,
        "firstNflRecordPeriod": nfl_from,
        "liveWeek": list(current) if current else None,
        "outstandingGames": len(plan),
        "outstandingByPeriod": {str(k): v for k, v in sorted(by_period.items())},
        "unstored": sum(not g.stored for g in plan),
        "notFinalWhenStored": sum(g.stored and not g.final for g in plan),
        "selfRecovering": [
            "FFA league, lineups and transactions (league lane)",
            "nflverse statistics (statistics lane)",
            "NFL injury reports, whole season per read (availability lane)",
        ],
    }
