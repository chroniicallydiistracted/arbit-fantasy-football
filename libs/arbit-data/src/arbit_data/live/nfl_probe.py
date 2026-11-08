"""Probe the NFL API's other routes during live games, to confirm the fastest consistent sync.

The `nfl` lane reads v2 details on each active round with a fresh cache key. This lane uses its own
sign-in and keeps ordinary cache keys so its observations can be compared with the primary lane.
It polls these routes for each selected game, with receipts from `nfl_log`.

| Route | Every |
| --- | --- |
| v2 game record, read directly (`/experience/v2/gamedetails/{id}`) | 2 s |
| v1 game record (`/experience/v1/gamedetails/{id}`) | 4 s |
| by-slug record (`/experience/v1/gamedetailsbyslug/{slug}`) | 4 s |
| player statistics (`/football/v2/stats/live/player-statistics/{id}`) | 4 s |
| the week's records (`/football/v2/experience/weekly-game-details`) | 10 s |
| an event-stream request on the v2 record, read for at most 4 kB | 60 s |

The owner found no public push stream outside live play (OWN-041 follow-up); the last row checks
whether one switches on during it. At most `MAX_GAMES` live games are probed, to stay polite.
Turn it off with `ARBIT_NFL_PROBE=0`.
"""

import os
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.live import nfl_log
from arbit_data.live.nfl_feed import FINAL, FINISHED, INCLUDES, NflApiClient
from arbit_data.schema import nfl_api_game

MAX_GAMES = 2
ROUTES: dict[str, float] = {
    "v2-direct": 2.0,
    "v1": 4.0,
    "slug": 4.0,
    "player-stats": 4.0,
    "weekly": 10.0,
    "stream": 60.0,
}


class NflProbe:
    def __init__(
        self,
        uow: UnitOfWork,
        season: int,
        *,
        client: Any | None = None,
        live_log: nfl_log.LiveLog | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        log: Callable[..., None] = lambda **_: None,
    ):
        self.uow, self.season, self.clock = uow, season, clock
        self.client = client or NflApiClient(spacing=0.4, timeout=5)
        self.live_log = live_log or nfl_log.LiveLog(
            on_problem=lambda code: log(event="capture_problem", code=code)
        )
        self.enabled = self.live_log.enabled and os.environ.get("ARBIT_NFL_PROBE", "1") != "0"
        self.due: dict[tuple[str, ...], float] = {}
        self.retry_at = 0.0

    def live_games(self, now: datetime) -> list[Any]:
        with self.uow.engine.connect() as c:
            rows = c.execute(select(nfl_api_game).where(nfl_api_game.c.season == self.season)).all()
        live = [
            r
            for r in rows
            if r.kickoff is not None
            and r.kickoff - timedelta(minutes=5) <= now <= r.kickoff + timedelta(hours=6)
            and (
                r.phase not in FINISHED
                or (
                    r.phase in FINAL
                    and r.details_observed_at is not None
                    and now - r.details_observed_at <= timedelta(minutes=1)
                )
            )
        ]
        return sorted(live, key=lambda r: (r.phase in FINAL, r.kickoff, r.game_id))[:MAX_GAMES]

    def _request(self, route: str, game: Any, weekly_games: set[str]) -> None:
        context: dict[str, Any] = {"game": game.game_id, "event_id": game.event_id}
        accept, limit = "application/json", None
        params: dict[str, Any] | None
        if route in ("v2-direct", "stream"):
            path, params = f"/experience/v2/gamedetails/{game.game_id}", INCLUDES
            if route == "stream":
                accept, limit = "text/event-stream", 4096
        elif route == "v1":
            path, params = f"/experience/v1/gamedetails/{game.game_id}", None
        elif route == "slug":
            if not game.slug:
                return
            path, params = (
                f"/experience/v1/gamedetailsbyslug/{game.slug}",
                {"includeReplays": "true"},
            )
        elif route == "player-stats":
            path, params = f"/football/v2/stats/live/player-statistics/{game.game_id}", None
        else:  # one weekly request per week, shared by the selected games
            context = {
                "season_type": game.season_type,
                "week": game.week,
                "game_ids": sorted(weekly_games),
            }
            path, params = (
                "/football/v2/experience/weekly-game-details",
                {
                    "season": self.season,
                    "type": game.season_type,
                    "week": game.week,
                    "includeDriveChart": "true",
                },
            )
        try:
            payload, _ = self.client.get(path, params, accept=accept, limit=limit)
        except SourceError as error:
            self.live_log.request("nfl_probe", route, self.client, error=error.code, **context)
            if error.code == "RATE_LIMITED":
                self.retry_at = time.monotonic() + max(60, error.retry_after_seconds or 0)
            return
        if route == "weekly":
            facts = nfl_log.plays(
                [r for r in payload if isinstance(r, dict) and r.get("id") in weekly_games]
                if isinstance(payload, list)
                else payload
            )
        elif route == "player-stats":
            facts = {"fingerprint": nfl_log.fingerprint(payload)}
        elif route == "stream":
            facts = {"accept": accept}
        else:
            facts = nfl_log.plays(payload)
        self.live_log.request("nfl_probe", route, self.client, **context, **facts)

    def step(self) -> float:
        if not self.enabled:
            return 30.0
        if (wait := self.retry_at - time.monotonic()) > 0:
            return min(wait, 15.0)
        games = self.live_games(self.clock())
        keys = {
            (str(game.season_type), str(game.week)) if route == "weekly" else (game.game_id, route)
            for game in games
            for route in ROUTES
        }
        self.due = {key: when for key, when in self.due.items() if key in keys}
        if not games:
            return 15.0
        for game in games:
            for route, every in ROUTES.items():
                scope = (game.season_type, game.week)
                key = tuple(map(str, scope)) if route == "weekly" else (game.game_id, route)
                now = time.monotonic()
                if now >= self.due.get(key, 0.0):
                    weekly_games = {g.game_id for g in games if (g.season_type, g.week) == scope}
                    self._request(route, game, weekly_games)
                    self.due[key] = time.monotonic() + every
                    if self.retry_at > now:
                        return 15.0
        return 0.5
