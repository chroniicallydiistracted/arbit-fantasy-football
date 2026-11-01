"""Reads the NFL scoreboard and active games on the cadence policy, within the host budget."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from arbit_data import freshness
from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.gate import DatabaseGate
from arbit_data.live import cadence, store
from arbit_data.live.normalize import _dict, _integer
from arbit_data.live.reader import (
    collect_play_pages,
    normalize_collection,
    normalize_scoreboard,
    normalize_summary,
)
from arbit_data.public_sources.requests import SourceRequest, build_source_request
from arbit_data.public_sources.transport import PublicResponse


class Transport(Protocol):
    def fetch(self, request: SourceRequest) -> PublicResponse: ...


def normalize_current_scoreboard(payload: Any, season: int) -> dict[str, Any]:
    """Validate the provider's own week against the configured season. Never infer a season."""
    raw = _dict(payload)
    year = _dict(raw.get("season")).get("year")
    week = _dict(raw.get("week")).get("number")
    season_type = _integer(_dict(raw.get("season")).get("type"), 4)
    if year != season:
        raise ValueError("SCOREBOARD_SEASON_MISMATCH")
    if type(week) is not int or season_type not in (1, 2, 3):
        raise ValueError("SCOREBOARD_SCOPE_MISSING")
    return normalize_scoreboard(raw, season, week, season_type)


@dataclass
class FeedResult:
    mode: cadence.Mode
    wait_seconds: float


class LiveFeed:
    def __init__(
        self,
        uow: UnitOfWork,
        transport: Transport,
        season: int,
        *,
        gate: Any | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.uow, self.transport, self.season, self.clock = uow, transport, season, clock
        self.gate = gate or DatabaseGate(uow, provider="espn_nfl")
        self.board_due: datetime | None = None
        self.mode: cadence.Mode = "idle"

    def _fetch(self, request: SourceRequest) -> PublicResponse:
        with self.gate.request():
            return self.transport.fetch(request)

    def read_board(self) -> store.BoardChange:
        response = self._fetch(build_source_request("espn.scoreboard.current", season=self.season))
        now = self.clock()
        change = store.publish_scoreboard(
            self.uow, normalize_current_scoreboard(response.payload, self.season), now
        )
        return change

    def read_plays(self, event_id: str) -> store.PlayChange:
        """Read a game's complete play collection. Pages must agree or nothing is stored."""
        first = self._fetch(
            build_source_request("espn.plays", event_id=event_id, season=self.season, page=1)
        )
        now = self.clock()
        digest = hashlib.sha256(first.body).hexdigest()
        page = normalize_collection(first.payload, event_id, self.season, 1)
        if page["page_count"] == 1 and store.plays_unchanged(self.uow, event_id, digest, now):
            return store.PlayChange()
        pages = [page]
        for number in range(2, page["page_count"] + 1):
            more = self._fetch(
                build_source_request(
                    "espn.plays", event_id=event_id, season=self.season, page=number
                )
            )
            digest = hashlib.sha256(
                (digest + hashlib.sha256(more.body).hexdigest()).encode()
            ).hexdigest()
            pages.append(normalize_collection(more.payload, event_id, self.season, number))
        plays = collect_play_pages(pages, event_id, self.season)
        return store.publish_plays(self.uow, event_id, plays, now, body_hash=digest)

    def read_summary(self, event_id: str, season_type: int = 2) -> None:
        response = self._fetch(
            build_source_request("espn.summary", event_id=event_id, season=self.season)
        )
        summary = normalize_summary(response.payload, event_id, self.season, season_type)
        store.publish_summary(
            self.uow, event_id, summary["boxscore"], self.clock(), summary["detail"]
        )

    def _board_step(self, now: datetime) -> None:
        if self.board_due is not None and now < self.board_due:
            return
        previous = self.mode
        seconds = cadence.scoreboard_seconds(previous)
        try:
            change = self.read_board()
        except (SourceError, ValueError, OSError) as error:
            code = error.code if isinstance(error, SourceError) else _safe_code(error)
            freshness.record_failure(
                self.uow,
                freshness.SCOREBOARD,
                code,
                now=self.clock(),
                cadence_seconds=seconds,
                stale_after_seconds=cadence.scoreboard_stale_seconds(previous),
            )
            failures = freshness.failures_of(self.uow, freshness.SCOREBOARD)
            retry = error.retry_after_seconds if isinstance(error, SourceError) else None
            self.board_due = self.clock() + timedelta(
                seconds=max(retry or 0, cadence.backoff_seconds(seconds, failures))
            )
            return
        timings = store.game_timings(self.uow, self.season)
        self.mode = cadence.live_mode(store.slate(timings), self.clock())
        seconds = cadence.scoreboard_seconds(self.mode)
        freshness.record_success(
            self.uow,
            freshness.SCOREBOARD,
            now=self.clock(),
            cadence_seconds=seconds,
            stale_after_seconds=cadence.scoreboard_stale_seconds(self.mode),
            changed=bool(change.changed),
        )
        self.board_due = self.clock() + timedelta(seconds=seconds)

    def _games_step(self, now: datetime) -> None:
        timings = store.game_timings(self.uow, self.season)
        active = [t for t in timings if t.phase in cadence.ACTIVE_PHASES]
        interval = cadence.play_seconds(len(active)) if active else None
        stale_after = cadence.PLAY_STALE_SECONDS if active else None
        for game in timings:
            final_due = (
                game.final_at is not None
                and game.phase == "final"
                and cadence.final_check_due(game.final_at, game.final_checks, now)
            )
            plays_due = final_due or (
                game.phase in cadence.ACTIVE_PHASES
                and interval is not None
                and (
                    game.plays_observed_at is None
                    or now - game.plays_observed_at >= timedelta(seconds=interval)
                )
            )
            summary_due = final_due or (
                game.phase in cadence.ACTIVE_PHASES
                and (
                    game.summary_observed_at is None
                    or now - game.summary_observed_at >= timedelta(seconds=cadence.SUMMARY_SECONDS)
                )
            )
            if not plays_due and not summary_due:
                continue
            try:
                change = None
                if plays_due:
                    change = self.read_plays(game.event_id)
                if summary_due:
                    self.read_summary(game.event_id)
                if final_due:
                    store.mark_final_check(self.uow, game.event_id)
                freshness.record_success(
                    self.uow,
                    freshness.PLAYS,
                    now=self.clock(),
                    cadence_seconds=interval,
                    stale_after_seconds=stale_after,
                    changed=bool(change and change.any),
                )
            except (SourceError, ValueError, OSError) as error:
                code = error.code if isinstance(error, SourceError) else _safe_code(error)
                freshness.record_failure(
                    self.uow,
                    freshness.PLAYS,
                    code,
                    now=self.clock(),
                    cadence_seconds=interval,
                    stale_after_seconds=stale_after,
                )
                # One bad game cannot hold up the others, but a cooldown applies to all of them.
                if code in ("SOURCE_COOLDOWN", "RATE_LIMITED"):
                    return

    def step(self) -> FeedResult:
        """One pass over everything due. Returns how long the caller may sleep."""
        self._board_step(self.clock())
        self._games_step(self.clock())
        wait = 1.0
        if self.board_due is not None and self.mode != "active":
            wait = min(5.0, max(1.0, (self.board_due - self.clock()).total_seconds()))
        return FeedResult(self.mode, wait)


def _safe_code(error: Exception) -> str:
    text = str(error)
    if text and text.isascii() and text.upper() == text and len(text) <= 64 and " " not in text:
        return text
    return "VALIDATION_FAILED"
