"""A game's plays as animations for the browser's live field (OWN-042).

For every current play revision, in game order: its facts (`play_facts`), its script
(`choreography`, with kicks, fumbles and penalties, and the try after a touchdown), and the stadium
board at it (`board`). Players line up by their depth chart positions as of kickoff (OWN-036),
each team's center, long snapper and quarterback come from the same charts and the game so far
(OWN-037), and names come from the roster. Scripts are cached by play revision, so a new play costs
one script, not the game's.
"""

import threading
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import select

from arbit_data.db import UnitOfWork
from arbit_data.league import content_hash
from arbit_data.live import context
from arbit_data.live.board import GameBoard, PlayBoard
from arbit_data.live.choreography import PlayScript, choreograph
from arbit_data.live.contracts import LivePlay
from arbit_data.live.kicking import choreograph_try
from arbit_data.live.pacing import pace
from arbit_data.live.play_facts import GameTeams, interpret, text_codes
from arbit_data.schema import nfl_game, nfl_play_revision, nfl_team

_CACHE: dict[tuple[str, str, str], tuple[PlayScript | None, PlayScript | None]] = {}
_LOCK = threading.Lock()
_CONTEXT: dict[str, Any] = {}


def real_seconds(play: LivePlay) -> float | None:
    """The play's snap-to-whistle time from the NFL record, when it has both."""
    if not play.snap_at or not play.whistle_at:
        return None
    start = datetime.fromisoformat(play.snap_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(play.whistle_at.replace("Z", "+00:00"))
    seconds = (end - start).total_seconds()
    return seconds if 0 < seconds < 60 else None


def current_plays(uow: UnitOfWork, event_id: str) -> list[LivePlay]:
    with uow.engine.connect() as c:
        rows = c.execute(
            select(nfl_play_revision.c.payload)
            .where(nfl_play_revision.c.event_id == event_id, nfl_play_revision.c.is_current)
            .order_by(nfl_play_revision.c.sequence.asc().nulls_last(), nfl_play_revision.c.play_id)
        ).all()
    return [LivePlay.model_validate(row.payload) for row in rows]


def _game(uow: UnitOfWork, event_id: str) -> dict[str, Any] | None:
    with uow.engine.connect() as c:
        payload = c.scalar(select(nfl_game.c.payload).where(nfl_game.c.event_id == event_id))
        teams = {r.espn_id: r for r in c.execute(select(nfl_team))}
    if not payload:
        return None
    home, away = str(payload["home_team_id"]), str(payload["away_team_id"])
    if home not in teams or away not in teams:
        return None
    return {
        "home": home,
        "away": away,
        "home_code": teams[home].abbreviation,
        "away_code": teams[away].abbreviation,
        "kickoff": payload.get("date"),
        "names": {
            team: [teams[team].location, f"{teams[team].location} {teams[team].name}"]
            for team in (home, away)
        },
    }


def _shared(
    kickoff: str | None,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]], dict[str, Any]]:
    """Roster names, depth chart positions and units as of kickoff; loaded once per kickoff."""
    with _LOCK:
        key = kickoff or ""
        if key not in _CONTEXT:
            _CONTEXT.clear()
            _CONTEXT[key] = (
                context.roster_names(),
                context.load(before=kickoff),
                context.units(before=kickoff),
            )
        found: tuple[dict[str, str], dict[str, tuple[str, ...]], dict[str, Any]] = _CONTEXT[key]
        return found


def build(uow: UnitOfWork, event_id: str) -> dict[str, Any] | None:
    """Every play's animation entry in game order, or None for an unknown game."""
    game = _game(uow, event_id)
    if game is None:
        return None
    plays = current_plays(uow, event_id)
    teams = GameTeams.build(
        game["home"],
        game["away"],
        game["home_code"],
        game["away_code"],
        seen=text_codes(p.text for p in plays),
    )
    try:
        names, positions, units_all = _shared(game["kickoff"])
    except (OSError, KeyError, StopIteration, ValueError):
        names, positions, units_all = {}, {}, {}  # without the nflverse files: plain placement
    units = context.GameUnits(
        units_all, (game["home"], game["away"], game["home_code"], game["away_code"])
    )
    board = GameBoard(teams, game["home_code"], game["away_code"], game["names"])
    entries: list[dict[str, Any]] = []
    for play in plays:
        facts = interpret(play, teams)
        revision = content_hash(play.model_dump(mode="json"))
        now = units.now()
        units.saw(facts)
        boards: Iterable[PlayBoard] = board.boards(play, facts)
        key = (event_id, play.provider_id, revision + content_hash(now))
        with _LOCK:
            cached = _CACHE.get(key)
        if cached is None:
            seed = f"{play.provider_id}:{revision}"
            script = (
                None
                if facts.shape in ("timeout", "other")
                else choreograph(facts, seed, names, positions, now)
            )
            if script is not None:
                script = pace(
                    script, real_seconds(play)
                )  # the NFL's snap-to-whistle time (OWN-041)
            tried = (
                choreograph_try(facts, seed, names, positions, now)
                if facts.point_after and facts.touchdown
                else None
            )
            cached = (script, tried)
            with _LOCK:
                _CACHE[key] = cached
        script, tried = cached
        made = list(boards)
        common = {
            "play_id": play.provider_id,
            "period": play.period,
            "clock": play.clock,
            "kind": play.kind,
            "text": play.text,
            "cancelled": play.cancelled,
            "source": play.source or "espn",
            "snap_at": play.snap_at,
            "whistle_at": play.whistle_at,
        }
        entries.append(
            {**common, "part": "play", "script": script, "board": made[0] if made else None}
        )
        if tried is not None and len(made) > 1:
            entries.append({**common, "part": "try", "script": tried, "board": made[1]})
    return {
        "event_id": event_id,
        "home": game["home"],
        "away": game["away"],
        "home_code": game["home_code"],
        "away_code": game["away_code"],
        "entries": entries,
    }
