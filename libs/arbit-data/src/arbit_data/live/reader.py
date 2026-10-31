"""Scoped game acquisition and bounded complete core-play collection reads."""

from dataclasses import dataclass
from functools import partial
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import or_, select

from arbit_data.db import UnitOfWork
from arbit_data.live.contracts import LiveGame, LivePlay
from arbit_data.live.normalize import _dict, _integer, _list, normalize_game, normalize_play
from arbit_data.live.replay import PlaySnapshot
from arbit_data.public_sources.repository import json_ready
from arbit_data.public_sources.requests import build_source_request
from arbit_data.public_sources.service import SourceService
from arbit_data.schema import entity_alias


def normalize_scoreboard(payload: Any, season: int, week: int) -> dict[str, Any]:
    raw = _dict(payload)
    if (
        _dict(raw.get("season")).get("year") != season
        or _dict(raw.get("week")).get("number") != week
    ):
        raise ValueError("SCOREBOARD_SCOPE_MISMATCH")
    events = [
        normalize_game(_dict(e), season).model_dump(mode="json")
        for e in _list(raw.get("events"), 32)
    ]
    if len({e["event_id"] for e in events}) != len(events):
        raise ValueError("DUPLICATE_EVENT")
    return {"season": season, "week": week, "games": events, "recommendations_enabled": False}


def normalize_summary(payload: Any, event_id: str, season: int) -> dict[str, Any]:
    raw = _dict(payload)
    header = _dict(raw.get("header"))
    if str(header.get("id")) != event_id:
        raise ValueError("SUMMARY_SCOPE_MISMATCH")
    game = normalize_game(header, season)
    drives = _dict(raw.get("drives"))
    previous = _list(drives.get("previous"), 100)
    if drives.get("current") is not None:
        previous = previous + [drives["current"]]
    plays = [_dict(p) for d in previous for p in _list(_dict(d).get("plays"), 6000)]
    return {
        "game": game.model_dump(mode="json"),
        "boxscore": json_ready(_dict(raw.get("boxscore"))),
        "summary_play_count": len({str(p.get("id")) for p in plays}),
        "summary_plays_with_athlete_ids": sum(bool(p.get("participants")) for p in plays),
        "recommendations_enabled": False,
    }


def normalize_collection(payload: Any, event_id: str, season: int, page: int) -> dict[str, Any]:
    raw = _dict(payload)
    if "$ref" in raw:
        u = urlsplit(raw["$ref"])
        if (
            u.scheme not in ("http", "https")
            or u.netloc != "sports.core.api.espn.com"
            or u.path
            != f"/v2/sports/football/leagues/nfl/events/{event_id}/competitions/{event_id}/plays"
        ):
            raise ValueError("COLLECTION_SCOPE_MISMATCH")
    count = _integer(raw.get("count"), 6000)
    index = _integer(raw.get("pageIndex"), 20)
    pages = _integer(raw.get("pageCount"), 20)
    if count is None or index != page or pages is None or pages < 1:
        raise ValueError("INVALID_PLAY_PAGE")
    items = _list(raw.get("items"), 300)
    return {
        "event_id": event_id,
        "count": count,
        "page_index": index,
        "page_count": pages,
        "page_size": _integer(raw.get("pageSize"), 300),
        "plays": [
            normalize_play(_dict(p), event_id, season).model_dump(mode="json") for p in items
        ],
    }


def collect_play_pages(
    pages: list[dict[str, Any]], event_id: str, season: int
) -> tuple[LivePlay, ...]:
    if not pages or len(pages) > 20:
        raise ValueError("INVALID_PAGE_SET")
    count = pages[0]["count"]
    total = pages[0]["page_count"]
    if total != len(pages):
        raise ValueError("INCOMPLETE_PLAY_COLLECTION")
    unique: dict[str, LivePlay] = {}
    for index, page in enumerate(pages, 1):
        if (
            page["event_id"] != event_id
            or page["count"] != count
            or page["page_count"] != total
            or page["page_index"] != index
        ):
            raise ValueError("PLAY_PAGE_DRIFT")
        for raw in page["plays"]:
            play = LivePlay.model_validate(raw)
            if play.event_id != event_id:
                raise ValueError("PLAY_EVENT_MISMATCH")
            if play.provider_id in unique and unique[play.provider_id] != play:
                raise ValueError("CONFLICTING_PLAY_PAGES")
            unique[play.provider_id] = play
    if len(unique) != count:
        raise ValueError("INCOMPLETE_PLAY_COLLECTION")
    return tuple(unique.values())


@dataclass(frozen=True)
class GameRead:
    game: LiveGame
    snapshot: PlaySnapshot
    manifests: tuple[str, ...]
    play_status: str
    stale: bool


class LiveReader:
    def __init__(self, service: SourceService):
        self.service = service

    def scoreboard(self, season: int, week: int) -> Any:
        req = build_source_request("espn.scoreboard", season=season, week=week)
        return self.service.acquire(req, lambda p: normalize_scoreboard(p, season, week))

    def game(self, event_id: str, season: int) -> GameRead:
        summary = self.service.acquire(
            build_source_request("espn.summary", event_id=event_id, season=season),
            lambda p: normalize_summary(p, event_id, season),
        )
        game = LiveGame.model_validate(summary.payload["game"])
        if game.phase in ("scheduled", "postponed", "cancelled"):
            return GameRead(
                game,
                PlaySnapshot(event_id, summary.observed_at, ()),
                (summary.hash,),
                "not_requested_before_kickoff_or_cancelled",
                summary.stale,
            )
        pages = []
        refs = [summary.hash]
        observed = summary.observed_at
        stale = summary.stale
        index = 1
        total = 1
        while index <= total:
            req = build_source_request("espn.plays", event_id=event_id, season=season, page=index)
            result = self.service.acquire(
                req, partial(normalize_collection, event_id=event_id, season=season, page=index)
            )
            pages.append(result.payload)
            refs.append(result.hash)
            total = result.payload["page_count"]
            observed = max(observed, result.observed_at)
            stale |= result.stale
            index += 1
        plays = collect_play_pages(pages, event_id, season)
        return GameRead(
            game,
            PlaySnapshot(event_id, observed, plays),
            tuple(refs),
            "complete_observed_collection",
            stale,
        )


def resolve_participants(uow: UnitOfWork, snapshot: PlaySnapshot) -> dict[str, str | None]:
    wanted = {p.espn_id for play in snapshot.plays for p in play.participants}
    if not wanted:
        return {}
    with uow.engine.connect() as c:
        rows = c.execute(
            select(entity_alias.c.external_id, entity_alias.c.entity_id).where(
                entity_alias.c.provider == "espn",
                entity_alias.c.kind == "athlete",
                entity_alias.c.scope == "global",
                entity_alias.c.external_id.in_(wanted),
                entity_alias.c.valid_from <= snapshot.observed_at,
                or_(
                    entity_alias.c.valid_to.is_(None),
                    entity_alias.c.valid_to > snapshot.observed_at,
                ),
            )
        ).all()
    found: dict[str, set[str]] = {key: set() for key in wanted}
    for external, entity in rows:
        found[str(external)].add(str(entity))
    return {key: next(iter(ids)) if len(ids) == 1 else None for key, ids in found.items()}
