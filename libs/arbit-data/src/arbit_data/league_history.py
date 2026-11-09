"""FFA history the current-state league document doesn't keep: weekly lineups and transactions.

Lineups: one ESPN read of a finished scoring period, reconciled with the shared FFA scoring proof
(`reconcile_period`), is stored only when every team's lineup reproduces ESPN's official total.
Captures are append-only, so a stat correction adds a capture and the earlier one stays.

Transactions: ESPN's league transactions per scoring period, keyed by ESPN's transaction ID, with
canonical team and player identities. Who proposed a transaction is not read.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import Connection, and_, desc, func, select
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.client import EspnClient
from arbit_data.espn.contracts import Transaction, TransactionPage
from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.normalize import POSITIONS, native_ref, slot_name
from arbit_data.espn.scoring_audit import _context
from arbit_data.espn.scoring_lineups import reconcile_period
from arbit_data.espn.scoring_stats import ScoringDataError
from arbit_data.events import emit
from arbit_data.identities import resolve_native
from arbit_data.league import LeagueDocument
from arbit_data.schema import (
    fantasy_lineup_capture,
    fantasy_lineup_entry,
    fantasy_transaction,
    fantasy_transaction_read,
)

LINEUP_VIEWS = ("mSettings", "mStatus", "mRoster", "mBoxscore", "mMatchupScore")
NOT_STARTING = ("BENCH", "IR")
# Executed moves members see. Proposals, declines, vetoes, lineup moves and the draft are stored only.
HIDDEN_TYPES = frozenset(
    {
        "ROSTER",
        "FUTURE_ROSTER",
        "RETRO_ROSTER",
        "DRAFT",
        "TRADE_PROPOSAL",
        "TRADE_DECLINE",
        "TRADE_VETO",
    }
)
SHOWN_ITEMS = frozenset({"ADD", "DROP", "TRADE"})


class HistoryError(SourceError):
    """A safe, coded reason a period or transaction read wasn't stored."""


def _cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _kind(espn_player_id: int) -> Literal["athlete", "defense_unit"]:
    # ESPN's D/ST IDs are negative; the league normalizer enforces the same rule.
    return "defense_unit" if espn_player_id < 0 else "athlete"


# --- Weekly lineups -------------------------------------------------------------------------


@dataclass(frozen=True)
class LineupEntry:
    team_id: UUID
    player_id: UUID
    slot: str
    official_points: Decimal | None
    display_name: str
    position: str
    # ESPN's team for the player when the week was read; not verified as that week's team.
    nfl_team_espn_id: int | None


@dataclass(frozen=True)
class PeriodLineup:
    capture_id: UUID
    scoring_period: int
    matchup_period: int
    captured_at: datetime
    entries: tuple[LineupEntry, ...]


def _period_points(player: dict[str, Any], season: int, period: int) -> Decimal | None:
    blocks = [
        b
        for b in player.get("stats") or []
        if isinstance(b, dict)
        and b.get("seasonId") == season
        and b.get("scoringPeriodId") == period
        and b.get("statSourceId") == 0
        and b.get("statSplitTypeId") == 1
    ]
    if len(blocks) > 1:
        raise HistoryError("AMBIGUOUS_ACTUAL_POINTS")
    value = blocks[0].get("appliedTotal") if blocks else None
    return None if value is None else _cents(Decimal(str(value)))


def _lineup_rows(
    payload: dict[str, Any], season: int, scoring_period: int, matchup_period: int
) -> list[dict[str, Any]]:
    rows = []
    for game in payload.get("schedule") or []:
        if not isinstance(game, dict) or game.get("matchupPeriodId") != matchup_period:
            continue
        for side in (game.get("home"), game.get("away")):
            if side is None:
                continue
            for entry in side["rosterForCurrentScoringPeriod"]["entries"]:
                player = entry["playerPoolEntry"]["player"]
                position = POSITIONS.get(player.get("defaultPositionId"))
                if position is None or not isinstance(player.get("fullName"), str):
                    raise HistoryError("UNRESOLVED_LINEUP_PLAYER")
                pro_team = player.get("proTeamId")
                rows.append(
                    {
                        "team": side["teamId"],
                        "player": entry["playerId"],
                        "slot": slot_name(entry["lineupSlotId"]),
                        "points": _period_points(player, season, scoring_period),
                        "name": player["fullName"],
                        "position": position,
                        "pro_team": pro_team if type(pro_team) is int and pro_team > 0 else None,
                    }
                )
    return sorted(rows, key=lambda r: (r["team"], r["player"]))


def capture_lineups(
    uow: UnitOfWork,
    client: EspnClient,
    season: int,
    scoring_period: int,
    matchup_period: int,
    *,
    now: datetime | None = None,
) -> Literal["stored", "unchanged"]:
    """Read, reconcile and store one finished period. Raises HistoryError if it doesn't reconcile."""
    response = client.fetch(
        Endpoint.LEAGUE,
        EndpointOptions(
            season=season,
            views=LINEUP_VIEWS,
            scoring_period=scoring_period,
            matchup_period=matchup_period,
        ),
    )
    payload = response.payload
    if response.capability != "available" or not isinstance(payload, dict):
        raise HistoryError("LINEUPS_UNAVAILABLE")
    try:
        context = _context(payload, season)
        if context.mapping.get(matchup_period) != (scoring_period,):
            raise HistoryError("MULTIWEEK_MATCHUPS_UNSUPPORTED")
        report = reconcile_period(
            payload, scoring_period, matchup_period, context.normalized, context.slots, context.size
        )
    except ScoringDataError as error:
        raise HistoryError(error.code) from None
    if (
        report["errors"]
        or report["mismatches"]
        or (report["lineupsMatched"] != report["lineupsChecked"])
    ):
        issues = report.get("issues") or [{}]
        raise HistoryError(str(issues[0].get("code") or "LINEUP_NOT_RECONCILED"))
    try:
        rows = _lineup_rows(payload, season, scoring_period, matchup_period)
    except (KeyError, TypeError) as error:
        raise HistoryError("LINEUP_SCHEMA_DRIFT") from error
    digest = _hash(rows)
    observed = now or datetime.now(UTC)
    with uow.engine.begin() as c:
        latest = c.scalar(
            select(fantasy_lineup_capture.c.content_hash)
            .where(
                fantasy_lineup_capture.c.season == season,
                fantasy_lineup_capture.c.scoring_period == scoring_period,
            )
            .order_by(desc(fantasy_lineup_capture.c.captured_at))
            .limit(1)
        )
        if latest == digest:
            return "unchanged"
        refs = {native_ref("fantasy_team", r["team"], season) for r in rows} | {
            native_ref(_kind(r["player"]), r["player"], season) for r in rows
        }
        ids = resolve_native(c, refs, observed, response.receipt.sha256)
        capture_id = uuid4()
        c.execute(
            insert(fantasy_lineup_capture).values(
                id=capture_id,
                season=season,
                scoring_period=scoring_period,
                matchup_period=matchup_period,
                content_hash=digest,
                receipt_sha256=response.receipt.sha256,
                captured_at=observed,
                verification={
                    key: report[key]
                    for key in ("lineupsChecked", "lineupsMatched", "verifiedPlayerGames")
                },
            )
        )
        c.execute(
            insert(fantasy_lineup_entry),
            [
                {
                    "capture_id": capture_id,
                    "player_id": ids[native_ref(_kind(r["player"]), r["player"], season)],
                    "team_id": ids[native_ref("fantasy_team", r["team"], season)],
                    "slot": r["slot"],
                    "official_points": r["points"],
                    "display_name": r["name"],
                    "position": r["position"],
                    "nfl_team_espn_id": r["pro_team"],
                }
                for r in rows
            ],
        )
        emit(c, "league.updated", {"lineups": scoring_period})
    return "stored"


def _latest_capture(c: Connection, season: int, scoring_period: int) -> Any:
    return c.execute(
        select(fantasy_lineup_capture)
        .where(
            fantasy_lineup_capture.c.season == season,
            fantasy_lineup_capture.c.scoring_period == scoring_period,
        )
        .order_by(desc(fantasy_lineup_capture.c.captured_at))
        .limit(1)
    ).first()


def read_lineup(uow: UnitOfWork, season: int, scoring_period: int) -> PeriodLineup | None:
    with uow.engine.connect() as c:
        capture = _latest_capture(c, season, scoring_period)
        if capture is None:
            return None
        rows = c.execute(
            select(fantasy_lineup_entry).where(fantasy_lineup_entry.c.capture_id == capture.id)
        ).all()
    return PeriodLineup(
        capture_id=capture.id,
        scoring_period=capture.scoring_period,
        matchup_period=capture.matchup_period,
        captured_at=capture.captured_at,
        entries=tuple(
            LineupEntry(
                team_id=r.team_id,
                player_id=r.player_id,
                slot=r.slot,
                official_points=None
                if r.official_points is None
                else _cents(Decimal(r.official_points)),
                display_name=r.display_name,
                position=r.position,
                nfl_team_espn_id=r.nfl_team_espn_id,
            )
            for r in rows
        ),
    )


def starter_totals(lineup: PeriodLineup) -> dict[UUID, Decimal]:
    totals: dict[UUID, Decimal] = {}
    for entry in lineup.entries:
        totals.setdefault(entry.team_id, Decimal(0))
        if entry.slot not in NOT_STARTING and entry.official_points is not None:
            totals[entry.team_id] += entry.official_points
    return {team: _cents(total) for team, total in totals.items()}


def due_lineup_periods(uow: UnitOfWork, document: LeagueDocument) -> list[tuple[int, int]]:
    """Finished one-week matchup periods with no capture, or whose official totals have moved."""
    by_period: dict[int, list[Any]] = {}
    for matchup in document.matchups:
        by_period.setdefault(matchup.matchup_period, []).append(matchup)
    due = []
    for period, matchups in sorted(by_period.items()):
        scoring = {s for m in matchups for s in m.scoring_periods}
        if len(scoring) != 1 or any(m.winner is None for m in matchups):
            continue
        scoring_period = scoring.pop()
        lineup = read_lineup(uow, document.season, scoring_period)
        if lineup is None:
            due.append((scoring_period, period))
            continue
        totals = starter_totals(lineup)
        official = {
            side.team_id: _cents(side.official_points)
            for m in matchups
            for side in (m.home, m.away)
            if side is not None and side.official_points is not None
        }
        if any(totals.get(team) != points for team, points in official.items()):
            due.append((scoring_period, period))
    return due


# --- Transactions ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Move:
    espn_id: str
    type: str
    team_id: UUID | None
    at: datetime | None
    items: tuple[dict[str, Any], ...]


def _when(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value / 1000, UTC) if type(value) is int and value > 0 else None


def _items(transaction: Transaction, ids: dict[Any, UUID], season: int) -> list[dict[str, Any]]:
    def team(value: int) -> str | None:
        return str(ids[native_ref("fantasy_team", value, season)]) if value > 0 else None

    def slot(value: int) -> str | None:
        return slot_name(value) if value >= 0 else None

    return [
        {
            "type": item.type,
            "player_id": str(ids[native_ref(_kind(item.player_id), item.player_id, season)]),
            "from_team_id": team(item.from_team_id),
            "to_team_id": team(item.to_team_id),
            "from_slot": slot(item.from_lineup_slot_id),
            "to_slot": slot(item.to_lineup_slot_id),
        }
        for item in transaction.items
        if item.player_id != 0
    ]


def fetch_transactions(
    client: EspnClient, season: int, scoring_period: int
) -> tuple[TransactionPage, str]:
    """One period's transactions and the read's SHA-256 for identity evidence."""
    response = client.fetch(
        Endpoint.LEAGUE,
        EndpointOptions(season=season, views=("mTransactions2",), scoring_period=scoring_period),
    )
    try:
        page = TransactionPage.model_validate(response.payload)
    except ValidationError:
        raise HistoryError("SCHEMA_DRIFT") from None
    if page.season_id != season or page.scoring_period_id != scoring_period:
        raise HistoryError("SCOPE_MISMATCH")
    # Entries keep their own period: a page also carries next week's lineup moves.
    if len({t.id for t in page.transactions}) != len(page.transactions):
        raise HistoryError("INCONSISTENT_DATA")
    return page, response.receipt.sha256


def store_transactions(
    uow: UnitOfWork,
    season: int,
    page: TransactionPage,
    *,
    receipt_sha256: str,
    now: datetime | None = None,
) -> int:
    """Insert new and changed transactions; returns how many changed."""
    observed = now or datetime.now(UTC)
    changed = 0
    with uow.engine.begin() as c:
        refs = set()
        for t in page.transactions:
            if t.team_id > 0:
                refs.add(native_ref("fantasy_team", t.team_id, season))
            for item in t.items:
                if item.player_id != 0:
                    refs.add(native_ref(_kind(item.player_id), item.player_id, season))
                for team in (item.from_team_id, item.to_team_id):
                    if team > 0:
                        refs.add(native_ref("fantasy_team", team, season))
        ids = resolve_native(c, refs, observed, receipt_sha256)
        existing: dict[str, str] = dict(
            c.execute(
                select(fantasy_transaction.c.espn_id, fantasy_transaction.c.content_hash).where(
                    fantasy_transaction.c.season == season,
                    fantasy_transaction.c.espn_id.in_([t.id for t in page.transactions]),
                )
            ).all()
        )
        for t in page.transactions:
            values = {
                "scoring_period": t.scoring_period_id,
                "type": t.type,
                "status": t.status,
                "team_id": ids[native_ref("fantasy_team", t.team_id, season)]
                if t.team_id > 0
                else None,
                "proposed_at": _when(t.proposed_date),
                "processed_at": _when(t.process_date),
                "related_espn_id": t.related_transaction_id,
                "items": _items(t, ids, season),
            }
            digest = _hash(values)
            if existing.get(t.id) == digest:
                continue
            changed += 1
            row = {**values, "content_hash": digest, "last_changed_at": observed}
            c.execute(
                insert(fantasy_transaction)
                .values(season=season, espn_id=t.id, first_observed_at=observed, **row)
                .on_conflict_do_update(
                    index_elements=[fantasy_transaction.c.season, fantasy_transaction.c.espn_id],
                    set_=row,
                )
            )
        read = {"last_read_at": observed, "transaction_count": len(page.transactions)}
        c.execute(
            insert(fantasy_transaction_read)
            .values(season=season, scoring_period=page.scoring_period_id, **read)
            .on_conflict_do_update(
                index_elements=[
                    fantasy_transaction_read.c.season,
                    fantasy_transaction_read.c.scoring_period,
                ],
                set_=read,
            )
        )
        if changed:
            emit(c, "league.updated", {"transactions": changed})
    return changed


def due_transaction_periods(
    uow: UnitOfWork, season: int, current_period: int, now: datetime, interval_seconds: int
) -> list[int]:
    """Every period once, oldest first; then the current and previous periods each interval."""
    with uow.engine.connect() as c:
        read: dict[int, datetime] = dict(
            c.execute(
                select(
                    fantasy_transaction_read.c.scoring_period,
                    fantasy_transaction_read.c.last_read_at,
                ).where(fantasy_transaction_read.c.season == season)
            ).all()
        )
    unread = [p for p in range(1, current_period + 1) if p not in read]
    if unread:
        return unread[:1]
    cutoff = now - timedelta(seconds=interval_seconds)
    return [p for p in (current_period, current_period - 1) if p >= 1 and read[p] <= cutoff]


def recent_moves(uow: UnitOfWork, season: int, *, limit: int = 8) -> list[Move]:
    """Executed adds, drops and trades, newest first."""
    when = func.coalesce(fantasy_transaction.c.processed_at, fantasy_transaction.c.proposed_at)
    with uow.engine.connect() as c:
        rows = c.execute(
            select(fantasy_transaction)
            .where(
                and_(
                    fantasy_transaction.c.season == season,
                    fantasy_transaction.c.status == "EXECUTED",
                    fantasy_transaction.c.type.not_in(HIDDEN_TYPES),
                )
            )
            .order_by(desc(when), fantasy_transaction.c.espn_id)
            .limit(limit * 4)
        ).all()
    moves = []
    for r in rows:
        items = tuple(i for i in r.items if i.get("type") in SHOWN_ITEMS)
        if items:
            moves.append(Move(r.espn_id, r.type, r.team_id, r.processed_at or r.proposed_at, items))
    return moves[:limit]


def lineup_names(uow: UnitOfWork, player_ids: set[UUID]) -> dict[UUID, str]:
    """Names as last stored in a weekly lineup, for players no longer in the league document."""
    if not player_ids:
        return {}
    with uow.engine.connect() as c:
        rows = c.execute(
            select(fantasy_lineup_entry.c.player_id, fantasy_lineup_entry.c.display_name)
            .join(
                fantasy_lineup_capture,
                fantasy_lineup_capture.c.id == fantasy_lineup_entry.c.capture_id,
            )
            .where(fantasy_lineup_entry.c.player_id.in_(player_ids))
            .order_by(fantasy_lineup_capture.c.captured_at)
        ).all()
    return {row.player_id: row.display_name for row in rows}
