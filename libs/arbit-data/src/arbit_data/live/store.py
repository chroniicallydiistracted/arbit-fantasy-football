"""Current NFL state and append-only play revisions, with events in the same transaction.

A poll that changes nothing writes only its freshness. A missing play is never a deletion: only
an explicit source cancellation removes a play's effect. No fantasy arithmetic happens here.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from arbit_core.identity import ProviderRef, require_aware
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.events import emit
from arbit_data.identities import resolve_native
from arbit_data.league import content_hash
from arbit_data.live.cadence import GamePhase
from arbit_data.live.contracts import LivePlay
from arbit_data.schema import (
    entity_alias,
    nfl_game,
    nfl_play_revision,
    nfl_schedule_game,
    nfl_team,
)


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _sequence(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


@dataclass(frozen=True)
class BoardChange:
    changed: tuple[str, ...]
    finished: tuple[str, ...]


def publish_scoreboard(
    uow: UnitOfWork, board: dict[str, Any], observed_at: datetime
) -> BoardChange:
    """Store one validated scoreboard. A late worker cannot overwrite newer state."""
    require_aware(observed_at)
    games = board["games"]
    changed: list[str] = []
    finished: list[str] = []
    with uow.engine.begin() as c:
        c.execute(select(func.pg_advisory_xact_lock(1729878439, -6)))
        existing = {
            row.event_id: row
            for row in c.execute(
                select(nfl_game).where(nfl_game.c.event_id.in_([g["event_id"] for g in games]))
            ).all()
        }
        for game in games:
            event_id = game["event_id"]
            state_hash = content_hash(game)
            row = existing.get(event_id)
            is_final = game["phase"] == "final"
            if row is None:
                c.execute(
                    insert(nfl_game).values(
                        event_id=event_id,
                        season=board["season"],
                        season_type=board["season_type"],
                        week=board["week"],
                        phase=game["phase"],
                        state_hash=state_hash,
                        payload=game,
                        observed_at=observed_at,
                        changed_at=observed_at,
                        final_at=observed_at if is_final else None,
                        final_checks=0,
                    )
                )
                changed.append(event_id)
                if is_final:
                    finished.append(event_id)
                continue
            if observed_at < row.observed_at:
                continue
            values: dict[str, Any] = {"observed_at": observed_at}
            if row.state_hash != state_hash:
                values.update(
                    phase=game["phase"],
                    state_hash=state_hash,
                    payload=game,
                    changed_at=observed_at,
                    week=board["week"],
                    season_type=board["season_type"],
                )
                changed.append(event_id)
                if is_final and row.final_at is None:
                    values["final_at"] = observed_at
                    finished.append(event_id)
            c.execute(update(nfl_game).where(nfl_game.c.event_id == event_id).values(**values))
        if changed:
            emit(c, "games.updated", {"week": board["week"], "events": changed[:32]})
    return BoardChange(tuple(changed), tuple(finished))


@dataclass(frozen=True)
class PlayChange:
    introduced: tuple[str, ...] = ()
    revised: tuple[str, ...] = ()
    cancelled: tuple[str, ...] = ()

    @property
    def any(self) -> bool:
        return bool(self.introduced or self.revised or self.cancelled)


def publish_plays(
    uow: UnitOfWork,
    event_id: str,
    plays: tuple[LivePlay, ...],
    observed_at: datetime,
    *,
    body_hash: str,
) -> PlayChange:
    """Append changed plays as revisions. Same content twice produces nothing new."""
    require_aware(observed_at)
    introduced: list[str] = []
    revised: list[str] = []
    cancelled: list[str] = []
    with uow.engine.begin() as c:
        game = c.execute(
            select(nfl_game.c.event_id, nfl_game.c.plays_observed_at)
            .where(nfl_game.c.event_id == event_id)
            .with_for_update()
        ).first()
        if game is None:
            raise ValueError("UNKNOWN_GAME")
        if game.plays_observed_at is not None and observed_at < game.plays_observed_at:
            return PlayChange()
        current = {
            row.play_id: row
            for row in c.execute(
                select(
                    nfl_play_revision.c.play_id,
                    nfl_play_revision.c.revision_hash,
                    nfl_play_revision.c.modified_at,
                ).where(nfl_play_revision.c.event_id == event_id, nfl_play_revision.c.is_current)
            ).all()
        }
        for play in plays:
            if play.event_id != event_id:
                raise ValueError("PLAY_EVENT_MISMATCH")
            payload = play.model_dump(mode="json")
            revision = content_hash(payload)
            previous = current.get(play.provider_id)
            if previous is not None and previous.revision_hash == revision:
                continue
            modified = _timestamp(play.modified_at)
            if (
                previous is not None
                and previous.modified_at is not None
                and modified is not None
                and modified < previous.modified_at
            ):
                continue  # An older provider revision arriving late cannot undo a newer one.
            if previous is not None:
                c.execute(
                    update(nfl_play_revision)
                    .where(
                        nfl_play_revision.c.event_id == event_id,
                        nfl_play_revision.c.play_id == play.provider_id,
                        nfl_play_revision.c.is_current,
                    )
                    .values(is_current=False)
                )
            c.execute(
                insert(nfl_play_revision)
                .values(
                    event_id=event_id,
                    play_id=play.provider_id,
                    revision_hash=revision,
                    sequence=_sequence(play.sequence),
                    modified_at=modified,
                    cancelled=play.cancelled,
                    first_observed_at=observed_at,
                    last_observed_at=observed_at,
                    is_current=True,
                    payload=payload,
                )
                # A play can return to an earlier revision; history keeps one row per content.
                .on_conflict_do_update(
                    index_elements=[
                        nfl_play_revision.c.event_id,
                        nfl_play_revision.c.play_id,
                        nfl_play_revision.c.revision_hash,
                    ],
                    set_={"is_current": True, "last_observed_at": observed_at},
                )
            )
            if play.cancelled:
                cancelled.append(play.provider_id)
            elif previous is None:
                introduced.append(play.provider_id)
            else:
                revised.append(play.provider_id)
        c.execute(
            update(nfl_game)
            .where(nfl_game.c.event_id == event_id)
            .values(plays_observed_at=observed_at, plays_body_hash=body_hash)
        )
        if introduced or revised or cancelled:
            emit(
                c,
                "game.corrected" if revised or cancelled else "game.plays",
                {
                    "event": event_id,
                    "introduced": len(introduced),
                    "revised": len(revised),
                    "cancelled": len(cancelled),
                },
            )
    return PlayChange(tuple(introduced), tuple(revised), tuple(cancelled))


def plays_unchanged(uow: UnitOfWork, event_id: str, body_hash: str, observed_at: datetime) -> bool:
    """Record a read whose bytes match the last one. True means there is nothing to process."""
    with uow.engine.begin() as c:
        return bool(
            c.execute(
                update(nfl_game)
                .where(nfl_game.c.event_id == event_id, nfl_game.c.plays_body_hash == body_hash)
                .values(plays_observed_at=observed_at)
            ).rowcount
        )


def publish_summary(
    uow: UnitOfWork, event_id: str, boxscore: dict[str, Any], observed_at: datetime
) -> None:
    with uow.engine.begin() as c:
        c.execute(
            update(nfl_game)
            .where(nfl_game.c.event_id == event_id)
            .values(boxscore=boxscore, summary_observed_at=observed_at)
        )


def mark_final_check(uow: UnitOfWork, event_id: str) -> None:
    with uow.engine.begin() as c:
        c.execute(
            update(nfl_game)
            .where(nfl_game.c.event_id == event_id)
            .values(final_checks=nfl_game.c.final_checks + 1)
        )


@dataclass(frozen=True)
class GameTiming:
    event_id: str
    season: int
    phase: str
    kickoff: datetime | None
    plays_observed_at: datetime | None
    summary_observed_at: datetime | None
    final_at: datetime | None
    final_checks: int


def game_timings(uow: UnitOfWork, season: int) -> list[GameTiming]:
    """Games of the most recently observed week, which the worker schedules from."""
    with uow.engine.connect() as c:
        scope = c.execute(
            select(nfl_game.c.season_type, nfl_game.c.week)
            .where(nfl_game.c.season == season)
            .order_by(nfl_game.c.observed_at.desc())
            .limit(1)
        ).first()
        if scope is None:
            return []
        rows = c.execute(
            select(nfl_game).where(
                nfl_game.c.season == season,
                nfl_game.c.season_type == scope.season_type,
                nfl_game.c.week == scope.week,
            )
        ).all()
    return [
        GameTiming(
            r.event_id,
            r.season,
            r.phase,
            _timestamp(r.payload.get("date")),
            r.plays_observed_at,
            r.summary_observed_at,
            r.final_at,
            r.final_checks,
        )
        for r in rows
    ]


def slate(timings: list[GameTiming]) -> list[GamePhase]:
    return [GamePhase(t.phase, t.kickoff) for t in timings]


@dataclass(frozen=True)
class TeamEntry:
    espn_id: str
    abbreviation: str
    location: str
    name: str
    bye_week: int | None


@dataclass(frozen=True)
class ScheduleEntry:
    event_id: str
    scoring_period: int
    home_espn_id: str
    away_espn_id: str
    kickoff: datetime | None
    start_tbd: bool | None
    stats_official: bool | None


@dataclass(frozen=True)
class Directory:
    teams: tuple[TeamEntry, ...]
    games: tuple[ScheduleEntry, ...] = field(default=())


def normalize_directory(payload: Any, season: int) -> Directory:
    """ESPN's pro-team directory: real team IDs, names, byes and the season's schedule."""
    settings = payload.get("settings") if isinstance(payload, dict) else None
    rows = settings.get("proTeams") if isinstance(settings, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("DIRECTORY_SHAPE_CHANGED")
    teams: list[TeamEntry] = []
    games: dict[str, ScheduleEntry] = {}
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) is not int:
            raise ValueError("DIRECTORY_SHAPE_CHANGED")
        if row["id"] <= 0:
            continue  # The directory's free-agent placeholder row is not an NFL team.
        abbreviation, location, name = row.get("abbrev"), row.get("location"), row.get("name")
        if not all(isinstance(v, str) and v for v in (abbreviation, location, name)):
            raise ValueError("DIRECTORY_SHAPE_CHANGED")
        bye = row.get("byeWeek")
        teams.append(
            TeamEntry(
                str(row["id"]),
                str(abbreviation),
                str(location),
                str(name),
                bye if type(bye) is int and bye > 0 else None,
            )
        )
        by_period = row.get("proGamesByScoringPeriod") or {}
        if not isinstance(by_period, dict):
            raise ValueError("DIRECTORY_SHAPE_CHANGED")
        for period, listed in by_period.items():
            if not isinstance(listed, list):
                raise ValueError("DIRECTORY_SHAPE_CHANGED")
            for game in listed:
                if not isinstance(game, dict) or type(game.get("id")) is not int:
                    raise ValueError("DIRECTORY_SHAPE_CHANGED")
                kickoff_ms = game.get("date")
                kickoff = (
                    datetime.fromtimestamp(kickoff_ms / 1000, tz=UTC)
                    if type(kickoff_ms) is int
                    else None
                )
                games[str(game["id"])] = ScheduleEntry(
                    str(game["id"]),
                    int(period),
                    str(game.get("homeProTeamId")),
                    str(game.get("awayProTeamId")),
                    kickoff,
                    game.get("startTimeTBD") if type(game.get("startTimeTBD")) is bool else None,
                    game.get("statsOfficial") if type(game.get("statsOfficial")) is bool else None,
                )
    known = {t.espn_id for t in teams}
    if len(known) != len(teams) or any(
        g.home_espn_id not in known or g.away_espn_id not in known for g in games.values()
    ):
        raise ValueError("DIRECTORY_INCONSISTENT")
    return Directory(tuple(teams), tuple(games.values()))


def publish_directory(
    uow: UnitOfWork, directory: Directory, season: int, observed_at: datetime, manifest_hash: str
) -> bool:
    """Upsert the directory. Team rows join FFA players through the exact ESPN team alias."""
    require_aware(observed_at)
    changed = False
    with uow.engine.begin() as c:
        refs = {
            t.espn_id: ProviderRef(
                provider="espn", entity_kind="nfl_team", external_id=t.espn_id, scope="global"
            )
            for t in directory.teams
        }
        ids = resolve_native(c, refs.values(), observed_at, manifest_hash)
        existing_teams = {r.espn_id: r for r in c.execute(select(nfl_team)).all()}
        for team in directory.teams:
            values = {
                "entity_id": ids[refs[team.espn_id]],
                "abbreviation": team.abbreviation,
                "location": team.location,
                "name": team.name,
                "bye_week": team.bye_week,
            }
            row = existing_teams.get(team.espn_id)
            if row is None or any(getattr(row, k) != v for k, v in values.items()):
                changed = True
            c.execute(
                insert(nfl_team)
                .values(espn_id=team.espn_id, observed_at=observed_at, **values)
                .on_conflict_do_update(
                    index_elements=[nfl_team.c.espn_id],
                    set_={**values, "observed_at": observed_at},
                )
            )
        existing_games = {
            r.event_id: r
            for r in c.execute(
                select(nfl_schedule_game).where(nfl_schedule_game.c.season == season)
            ).all()
        }
        for game in directory.games:
            values = {
                "season": season,
                "scoring_period": game.scoring_period,
                "home_espn_id": game.home_espn_id,
                "away_espn_id": game.away_espn_id,
                "kickoff": game.kickoff,
                "start_tbd": game.start_tbd,
                "stats_official": game.stats_official,
            }
            row = existing_games.get(game.event_id)
            if row is None or any(getattr(row, k) != v for k, v in values.items()):
                changed = True
            c.execute(
                insert(nfl_schedule_game)
                .values(event_id=game.event_id, observed_at=observed_at, **values)
                .on_conflict_do_update(
                    index_elements=[nfl_schedule_game.c.event_id],
                    set_={**values, "observed_at": observed_at},
                )
            )
        if changed:
            emit(c, "schedule.updated", {"season": season})
    return changed


def read_directory(uow: UnitOfWork) -> dict[UUID, Any]:
    with uow.engine.connect() as c:
        return {r.entity_id: r for r in c.execute(select(nfl_team)).all()}


def read_period_games(uow: UnitOfWork, season: int, scoring_period: int) -> dict[str, Any]:
    """Each team's scheduled game for a scoring period, by ESPN team ID."""
    with uow.engine.connect() as c:
        rows = c.execute(
            select(nfl_schedule_game).where(
                nfl_schedule_game.c.season == season,
                nfl_schedule_game.c.scoring_period == scoring_period,
            )
        ).all()
    result: dict[str, Any] = {}
    for row in rows:
        result[row.home_espn_id] = row
        result[row.away_espn_id] = row
    return result


def read_games(uow: UnitOfWork, season: int) -> dict[str, Any] | None:
    """The most recently observed week's games with their state and team directory."""
    with uow.engine.connect() as c:
        scope = c.execute(
            select(nfl_game.c.season_type, nfl_game.c.week)
            .where(nfl_game.c.season == season)
            .order_by(nfl_game.c.observed_at.desc())
            .limit(1)
        ).first()
        if scope is None:
            return None
        rows = c.execute(
            select(
                nfl_game.c.event_id,
                nfl_game.c.payload,
                nfl_game.c.observed_at,
                nfl_game.c.changed_at,
            ).where(
                nfl_game.c.season == season,
                nfl_game.c.season_type == scope.season_type,
                nfl_game.c.week == scope.week,
            )
        ).all()
        teams = {r.espn_id: r for r in c.execute(select(nfl_team)).all()}
    return {
        "season_type": scope.season_type,
        "week": scope.week,
        "games": [
            {
                **r.payload,
                "observed_at": r.observed_at,
                "changed_at": r.changed_at,
            }
            for r in rows
        ],
        "teams": teams,
    }


def read_game(uow: UnitOfWork, event_id: str) -> dict[str, Any] | None:
    with uow.engine.connect() as c:
        row = c.execute(
            select(
                nfl_game.c.payload,
                nfl_game.c.observed_at,
                nfl_game.c.plays_observed_at,
            ).where(nfl_game.c.event_id == event_id)
        ).first()
    if row is None:
        return None
    return {
        **row.payload,
        "observed_at": row.observed_at,
        "plays_observed_at": row.plays_observed_at,
    }


def read_plays(
    uow: UnitOfWork, event_id: str, *, limit: int = 200, espn_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    """Newest first. Cancelled plays stay in history and are labeled by their payload."""
    with uow.engine.connect() as c:
        rows = (
            c.execute(
                select(
                    nfl_play_revision.c.payload,
                    nfl_play_revision.c.first_observed_at,
                    nfl_play_revision.c.play_id,
                )
                .where(nfl_play_revision.c.event_id == event_id, nfl_play_revision.c.is_current)
                .order_by(
                    nfl_play_revision.c.sequence.desc().nulls_last(),
                    nfl_play_revision.c.play_id.desc(),
                )
            )
        ).all()
        corrected: set[str] = set(
            c.scalars(
                select(nfl_play_revision.c.play_id)
                .where(nfl_play_revision.c.event_id == event_id)
                .group_by(nfl_play_revision.c.play_id)
                .having(func.count() > 1)
            )
        )
    plays = []
    for row in rows:
        ids = {p["espn_id"] for p in row.payload.get("participants", [])}
        if espn_ids is not None and not ids & espn_ids:
            continue
        plays.append({**row.payload, "corrected": row.play_id in corrected})
        if len(plays) >= limit:
            break
    return plays


def athlete_espn_ids(uow: UnitOfWork, entity_ids: set[UUID], as_of: datetime) -> dict[str, UUID]:
    """Exact active ESPN aliases for canonical athletes. Names never establish this."""
    if not entity_ids:
        return {}
    with uow.engine.connect() as c:
        rows = c.execute(
            select(entity_alias.c.external_id, entity_alias.c.entity_id).where(
                and_(
                    entity_alias.c.provider == "espn",
                    entity_alias.c.kind == "athlete",
                    entity_alias.c.scope == "global",
                    entity_alias.c.entity_id.in_(entity_ids),
                    entity_alias.c.valid_from <= as_of,
                    or_(entity_alias.c.valid_to.is_(None), entity_alias.c.valid_to > as_of),
                )
            )
        ).all()
    return {str(r.external_id): r.entity_id for r in rows}
