"""A game's plays as animations for the browser's live field (OWN-042).

For every current play revision, in game order: its facts (`play_facts`), its script
(`choreography`, with kicks, fumbles and penalties, and the try after a touchdown), and the stadium
board at it (`board`). Players line up by their depth chart positions as of kickoff (OWN-036),
each team's center, long snapper and quarterback come from the same charts and the game so far
(OWN-037), and names come from the roster. Scripts are cached by play revision, so a new play costs
one script, not the game's.
"""

import threading
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select

from arbit_data.db import UnitOfWork
from arbit_data.league import content_hash
from arbit_data.live import context, motion
from arbit_data.live.actions import elapsed_seconds as real_seconds
from arbit_data.live.actions import sequence
from arbit_data.live.board import GameBoard, PlayBoard
from arbit_data.live.choreography import PlayScript, choreograph
from arbit_data.live.contracts import LivePlay
from arbit_data.live.kicking import choreograph_try
from arbit_data.live.nfl_api import attached_try, with_motion_evidence
from arbit_data.live.nfl_feed import gsis_to_espn
from arbit_data.live.pacing import pace
from arbit_data.live.play_facts import GameTeams, interpret, text_codes
from arbit_data.schema import nfl_game, nfl_play_revision, nfl_team

_CACHE_LIMIT = 4096
_CACHE: OrderedDict[
    tuple[str, str, str, int],
    tuple[PlayScript | motion.PlayScriptV2 | None, PlayScript | None],
] = OrderedDict()
_LOCK = threading.Lock()
_CONTEXT: dict[str, Any] = {}


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


def build(uow: UnitOfWork, event_id: str, *, script_version: int = 1) -> dict[str, Any] | None:
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
    needs_evidence = any(p.source == "nfl" and p.nfl and p.motion_evidence is None for p in plays)
    ids = gsis_to_espn(uow) if needs_evidence else {}
    for play in plays:
        revision = content_hash(play.model_dump(mode="json"))
        if needs_evidence and play.source == "nfl":
            play = with_motion_evidence(play, ids)
        facts = interpret(play, teams)
        now = units.now()
        units.saw(facts)
        attempt = attached_try(play)
        boards: Iterable[PlayBoard] = board.boards(play, facts, attempt=attempt)
        key = (event_id, play.provider_id, revision + content_hash(now), script_version)
        with _LOCK:
            cached = _CACHE.get(key)
            if cached is not None:
                _CACHE.move_to_end(key)
        if cached is None:
            seed = f"{play.provider_id}:{revision}"
            script: PlayScript | motion.PlayScriptV2 | None = None
            if script_version == 2 and facts.shape in motion.PREVIEW_SHAPES:
                script = motion.plan(
                    sequence(play, facts), motion.MotionContext(facts, names, positions, now)
                )
            if script is None and facts.shape not in ("timeout", "other"):
                elapsed = real_seconds(play)
                legacy = choreograph(facts, seed, names, positions, now, elapsed)
                script = (
                    pace(legacy, elapsed) if legacy is not None and legacy.note is None else legacy
                )
            tried = None
            if facts.point_after and facts.touchdown:
                try_facts = facts
                if attempt is not None:
                    try_facts = facts.model_copy(
                        update={
                            "text": attempt.text,
                            "clock": attempt.clock,
                            "period": attempt.period,
                        }
                    )
                tried = choreograph_try(
                    try_facts,
                    seed,
                    names,
                    positions,
                    now,
                    real_seconds(attempt) if attempt is not None else None,
                )
                if tried is not None and attempt is not None:
                    tried = pace(tried, real_seconds(attempt))
            cached = (script, tried)
            with _LOCK:
                _CACHE[key] = cached
                _CACHE.move_to_end(key)
                if len(_CACHE) > _CACHE_LIMIT:
                    _CACHE.popitem(last=False)
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
        if len(made) > 1:
            metadata = (
                {
                    "period": attempt.period,
                    "clock": attempt.clock,
                    "text": attempt.text,
                    "snap_at": attempt.snap_at,
                    "whistle_at": attempt.whistle_at,
                    "cancelled": attempt.cancelled,
                }
                if attempt is not None
                else {"snap_at": None, "whistle_at": None}
            )
            entries.append({**common, **metadata, "part": "try", "script": tried, "board": made[1]})
    return {
        "event_id": event_id,
        "home": game["home"],
        "away": game["away"],
        "home_code": game["home_code"],
        "away_code": game["away_code"],
        "entries": entries,
    }
