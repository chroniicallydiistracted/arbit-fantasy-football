"""The NFL API live lane (OWN-041): discover games, poll them, detect changes, publish.

The owner's four steps, run by the worker's `nfl` lane:
1. **Discover.** The NFL week containing today (`/football/v2/weeks/date/{date}`), then that
   week's schedule, gives each game's UUID and kickoff. Each is linked to ESPN's event, which the
   ESPN scoreboard lane keeps, by kickoff time and teams.
2. **Poll.** Each active game gets a full `/experience/v2/gamedetails` read every two-second
   round. The week summaries still provide game state, with 30-second pregame and five-minute
   idle rounds. Each summary or detail request uses a new CDN cache key.
3. **Detect.** Convert changed responses to canonical plays and compare them with the stored
   revisions, including corrections to earlier plays.
4. **Publish.** `store.publish_plays` appends changed plays and emits `game.plays` or
   `game.corrected` in the same transaction, so the app's events follow the commit.

Sign-in is NFL.com's anonymous device grant with the public web-client values from the
sportsdataverse source file named by `ARBIT_NFL_API_CLIENT_SOURCE` (read with `ast`, never
executed). The token lasts about an hour and is renewed before it expires. It carries the
requester's approximate location, so it is never logged or stored.
"""

import ast
import gzip
import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.client import HTTPException
from io import BytesIO
from pathlib import Path
from threading import local
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data import freshness
from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.http_deadline import DeadlineHTTPSHandler
from arbit_data.espn.transport import _NoRedirect, _retry_after
from arbit_data.live import nfl_log, store
from arbit_data.live.contracts import LivePlay
from arbit_data.live.nfl_api import NFL_CODES, GameLink, to_live_plays
from arbit_data.public_sources.transport import MAX_BYTES
from arbit_data.schema import entity_alias, nfl_api_game, nfl_game, nfl_team

HOST = "https://api.nfl.com"
SOURCE = "nfl.api.plays"
ACTIVE_SECONDS, PREGAME_SECONDS, IDLE_SECONDS = 2.0, 30.0, 300.0
MAX_DETAIL_WORKERS = 8
DISCOVER_SECONDS = 6 * 3600
STALE_SECONDS = store.NFL_STALE_SECONDS
FINAL = store.NFL_FINAL_PHASES
FINISHED = FINAL | {"CANCELLED", "POSTPONED"}
NOT_ACTIVE = FINISHED | {None, "", "PREGAME", "SCHEDULED"}
INCLUDES = {
    "includeDriveChart": "true",
    "includeReplays": "true",
    "includeStandings": "true",
    "includeTaggedVideos": "true",
}


# Response headers kept in the live log: caching (Varnish), size and timing. Never a request header.
KEPT_HEADERS = {
    "age",
    "cache-control",
    "x-cache",
    "x-cache-hits",
    "x-varnish",
    "via",
    "date",
    "etag",
    "last-modified",
    "content-type",
    "content-encoding",
    "content-length",
    "x-served-by",
    "x-timer",
    "expires",
    "surrogate-control",
    "x-cache-status",
    "retry-after",
}


class NflApiClient:
    """GETs on `api.nfl.com` with an anonymous token, at most one request per `spacing` seconds."""

    def __init__(
        self, client_source: Path | None = None, *, spacing: float = 0.5, timeout: float = 20.0
    ):
        self.client_source = client_source or Path(
            os.environ.get("ARBIT_NFL_API_CLIENT_SOURCE", "data/nfl-api/client/nfl_games.py")
        )
        self.spacing, self.timeout = spacing, timeout
        self.opener = build_opener(_NoRedirect(), DeadlineHTTPSHandler())
        self._token: str | None = None
        self.last: dict[str, Any] = {}
        self.attempts: list[dict[str, Any]] = []
        self._expires = 0.0
        self._last = 0.0

    def _defaults(self) -> dict[str, Any]:
        found: dict[str, Any] = {}
        try:
            tree = ast.parse(self.client_source.read_text())
        except (OSError, SyntaxError, UnicodeError):
            raise SourceError("NFL_API_CLIENT_MISSING") from None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in (
                        "_DEFAULT_CLIENT_KEY",
                        "_DEFAULT_CLIENT_SECRET",
                        "_DEFAULT_DEVICE_INFO",
                    ):
                        found[target.id] = ast.literal_eval(node.value)
        if len(found) != 3:
            raise SourceError("NFL_API_CLIENT_MISSING")
        return found

    def _sign_in(self) -> None:
        values = self._defaults()
        body = urlencode(
            {
                "clientKey": values["_DEFAULT_CLIENT_KEY"],
                "clientSecret": values["_DEFAULT_CLIENT_SECRET"],
                "deviceInfo": values["_DEFAULT_DEVICE_INFO"],
                "deviceId": str(uuid.uuid4()),
                "networkType": "other",
            }
        ).encode()
        request = Request(
            HOST + "/identity/v3/token",
            data=body,
            headers={
                "X-Domain-Id": "100",
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            reply = json.loads(self._send(request, "/identity/v3/token"))
        except (ValueError, RecursionError):
            raise SourceError("NFL_API_SIGN_IN_FAILED") from None
        if not isinstance(reply, dict):
            raise SourceError("NFL_API_SIGN_IN_FAILED")
        token, expires = reply.get("accessToken"), reply.get("expiresIn")
        if not isinstance(token, str) or not token:
            raise SourceError("NFL_API_SIGN_IN_FAILED")
        self._token = token
        # `expiresIn` is an absolute time in seconds; renew a few minutes early.
        self._expires = (
            float(expires) - 300
            if isinstance(expires, (int, float)) and expires > 1e9
            else time.time() + 1800
        )

    def _send(self, request: Request, path: str, limit: int | None = None) -> bytes:
        """One request at the client's pace. Asks for gzip (the API serves it, about a seventh
        of the size) and keeps the response's status, cache headers and timing in `last`."""
        wait = self.spacing - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        started, sent_at = time.monotonic(), datetime.now(UTC)
        request.add_header("Accept-Encoding", "gzip")
        self.last = {"path": path, "method": request.get_method(), "sent_at": sent_at.isoformat()}
        self.attempts.append(self.last)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                headers = {
                    k.lower(): v for k, v in response.headers.items() if k.lower() in KEPT_HEADERS
                }
                self.last.update(status=response.status, headers=headers)
                is_stream = headers.get("content-type", "").split(";", 1)[0] == "text/event-stream"
                # The probe needs the handshake. A genuine stream need not have sent an event yet.
                raw: bytes = b"" if limit and is_stream else response.read(limit or MAX_BYTES + 1)
            self.last["wire_bytes"] = len(raw)
            if len(raw) > MAX_BYTES:
                raise SourceError("NFL_API_RESPONSE_TOO_LARGE")
            body = raw
            if not limit and headers.get("content-encoding", "").lower() == "gzip":
                try:
                    with gzip.GzipFile(fileobj=BytesIO(raw)) as decoded:
                        body = decoded.read(MAX_BYTES + 1)
                except (OSError, EOFError):
                    raise SourceError("NFL_API_BAD_GZIP") from None
                if len(body) > MAX_BYTES:
                    raise SourceError("NFL_API_RESPONSE_TOO_LARGE")
            self.last["bytes"] = len(body)
            return body
        except HTTPError as error:
            status = error.code
            self.last.update(
                status=status,
                headers={
                    k.lower(): v for k, v in error.headers.items() if k.lower() in KEPT_HEADERS
                },
            )
            retry = _retry_after(error.headers.get("Retry-After"))
            error.close()
            code = {401: "NFL_API_UNAUTHORIZED", 429: "RATE_LIMITED"}.get(
                status, f"NFL_API_HTTP_{status}"
            )
            raise SourceError(code, status=status, retry_after_seconds=retry) from None
        except (URLError, OSError, HTTPException):
            raise SourceError("NFL_API_UNREACHABLE") from None
        finally:
            self.last.update(
                received_at=datetime.now(UTC).isoformat(),
                seconds=round(time.monotonic() - started, 4),
            )

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        accept: str = "application/json",
        limit: int | None = None,
    ) -> tuple[Any, bytes]:
        """The JSON at `path`, and its raw bytes. Signs in again once if the token was refused.
        `accept` and `limit` let the probe ask for an event stream without holding it open."""
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("NFL_API_PATH")
        self.last = {}
        self.attempts.clear()
        for attempt in (1, 2):
            if self._token is None or time.time() >= self._expires:
                self._sign_in()
            url = HOST + path + (("?" + urlencode(params)) if params else "")
            request = Request(
                url,
                headers={
                    "Accept": accept,
                    "Authorization": "Bearer " + str(self._token),
                    "X-Domain-Id": "100",
                    "Origin": "https://www.nfl.com",
                    "Referer": "https://www.nfl.com/",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            try:
                body = self._send(request, path, limit)
            except SourceError as error:
                if error.code == "NFL_API_UNAUTHORIZED" and attempt == 1:
                    self._token = None
                    continue
                raise
            if limit:
                return None, body
            try:
                return json.loads(body), body
            except (ValueError, RecursionError):
                raise SourceError("NFL_API_NOT_JSON") from None
        raise SourceError("NFL_API_UNAUTHORIZED")


def gsis_to_espn(uow: UnitOfWork) -> dict[str, str]:
    """Current GSIS → ESPN player IDs from the identity crosswalk (nflverse's players table)."""
    gsis, espn = entity_alias.alias("gsis"), entity_alias.alias("espn")
    with uow.engine.connect() as c:
        rows = c.execute(
            select(gsis.c.external_id, espn.c.external_id)
            .select_from(gsis.join(espn, gsis.c.entity_id == espn.c.entity_id))
            .where(
                gsis.c.provider == "gsis",
                espn.c.provider == "espn",
                gsis.c.valid_to.is_(None),
                espn.c.valid_to.is_(None),
            )
        ).all()
    return {row[0]: row[1] for row in rows}


def _code(team: Mapping[str, Any] | None) -> str | None:
    """A team's code from its NFL logo address (".../logos/SEA"), as ESPN writes it."""
    logo = str((team or {}).get("currentLogo") or "")
    match = re.search(r"/logos/([A-Z]{2,4})$", logo)
    return NFL_CODES.get(match.group(1), match.group(1)) if match else None


def _slug(game: Mapping[str, Any]) -> str | None:
    for external_id in game.get("externalIds") or []:
        if isinstance(external_id, Mapping) and external_id.get("source") == "slug":
            value = external_id.get("id")
            if isinstance(value, str) and re.fullmatch(r"[a-z0-9-]{1,128}", value):
                return value
    return None


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def nfl_primary(uow: UnitOfWork, event_id: str, now: datetime) -> bool:
    """A fresh NFL read or a confirmed NFL final owns this game's play feed."""
    with uow.engine.connect() as c:
        return store.nfl_detail_primary(c, event_id, now)


def _usable_final(plays: tuple[LivePlay, ...], summary: dict[str, Any], phase: str | None) -> bool:
    """A final needs football through the last period, an end marker, and matching totals."""
    last = plays[-1]
    if last.cancelled or (last.nfl or {}).get("play", {}).get("playType") != "END_GAME":
        return False
    periods = {
        play.period
        for play in plays
        if not play.cancelled and play.kind not in ("administrative", "unknown")
    }
    last_period = 5 if phase == "FINAL_OVERTIME" else 4
    if not set(range(1, last_period + 1)).issubset(periods):
        return False
    for side, score in (("homeTeam", last.home_score), ("awayTeam", last.away_score)):
        team = summary.get(side)
        totals = team.get("score") if isinstance(team, dict) else None
        total = totals.get("total") if isinstance(totals, dict) else None
        if type(total) is not int or str(total) != score:
            return False
    return True


@dataclass
class Watched:
    game_id: str
    event_id: str | None
    slug: str | None
    kickoff: datetime | None
    phase: str | None
    summary_hash: str | None
    details_at: datetime | None
    details_phase: str | None = None


class NflFeed:
    def __init__(
        self,
        uow: UnitOfWork,
        season: int,
        *,
        client: NflApiClient | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        log: Callable[..., None] = lambda **_: None,
        live_log: "nfl_log.LiveLog | None" = None,
        lane: str = "nfl",
    ):
        self.uow, self.season, self.clock, self.log, self.lane = uow, season, clock, log, lane
        self.client = client or NflApiClient()
        self.detail_pool = (
            ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) if client is None else None
        )
        self.detail_clients = local()
        self.week: tuple[str, int] | None = None  # (season type, week)
        self.discovered_at: datetime | None = None
        self.summaries_due: datetime | None = None
        self.ids: dict[str, str] = {}
        self.ids_at: datetime | None = None
        self.failures = 0
        self.live_log = live_log or nfl_log.LiveLog(
            on_problem=lambda code: self.log(event="capture_problem", code=code)
        )

    def _get(
        self,
        route: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        fresh: bool = False,
        client: NflApiClient | None = None,
        **context: Any,
    ) -> tuple[Any, bytes]:
        """A request, written to the live log with its timing, cache headers and what it says."""
        client = client or self.client
        if fresh:
            cache_key = uuid.uuid4().hex
            params = {**(params or {}), "_cache_probe": cache_key}
            context["cache_key"] = cache_key
        try:
            payload, body = client.get(path, params)
        except SourceError as error:
            self.live_log.request(self.lane, route, client, error=error.code, **context)
            raise
        facts: dict[str, Any] = {}
        if route == "summaries":
            facts = nfl_log.summaries(payload)
        elif route in ("v2", "v1", "slug", "weekly"):
            facts = nfl_log.plays(payload)
        self.live_log.request(self.lane, route, client, **context, **facts)
        return payload, body

    # 1. Discover --------------------------------------------------------------------------------

    def discover(self, now: datetime) -> None:
        week, _ = self._get(
            "week", f"/football/v2/weeks/date/{now.astimezone(UTC).date().isoformat()}"
        )
        if week.get("season") != self.season:
            raise SourceError("NFL_API_SEASON_MISMATCH")
        season_type, number = str(week.get("seasonType") or "REG"), int(week.get("week"))
        schedule, _ = self._get(
            "schedule",
            f"/football/v2/games/season/{self.season}/seasonType/{season_type}/week/{number}",
        )
        teams = self._espn_teams()
        with self.uow.engine.begin() as c:
            espn_games = c.execute(
                select(nfl_game.c.event_id, nfl_game.c.payload).where(
                    nfl_game.c.season == self.season
                )
            ).all()
            by_key = {}
            for row in espn_games:
                payload = row.payload or {}
                key = (
                    teams.get(str(payload.get("home_team_id"))),
                    teams.get(str(payload.get("away_team_id"))),
                    (payload.get("date") or "")[:10],
                )
                by_key[key] = row.event_id
            for game in schedule.get("games") or []:
                kickoff = _instant(game.get("time"))
                home, away = _code(game.get("homeTeam")), _code(game.get("awayTeam"))
                event = None
                for day in {
                    kickoff.date().isoformat() if kickoff else "",
                    str(game.get("date") or ""),
                }:
                    event = event or by_key.get((home, away, day))
                values = {
                    "season": self.season,
                    "season_type": season_type,
                    "week": number,
                    "event_id": event,
                    "kickoff": kickoff,
                    "observed_at": now,
                }
                if (slug := _slug(game)) is not None:
                    values["slug"] = slug
                c.execute(
                    insert(nfl_api_game)
                    .values(game_id=str(game["id"]), **values)
                    .on_conflict_do_update(index_elements=[nfl_api_game.c.game_id], set_=values)
                )
        self.week = (season_type, number)
        self.discovered_at = now
        self.log(event="discovered", week=number, games=len(schedule.get("games") or []))

    def _espn_teams(self) -> dict[str, str]:
        with self.uow.engine.connect() as c:
            return {
                row.espn_id: row.abbreviation
                for row in c.execute(select(nfl_team.c.espn_id, nfl_team.c.abbreviation))
            }

    # 2. Poll, 3. detect, 4. publish ------------------------------------------------------------

    def _watched(self) -> list[Watched]:
        assert self.week is not None
        with self.uow.engine.connect() as c:
            rows = c.execute(
                select(nfl_api_game).where(
                    nfl_api_game.c.season == self.season,
                    or_(
                        and_(
                            nfl_api_game.c.season_type == self.week[0],
                            nfl_api_game.c.week == self.week[1],
                        ),
                        # A linked legacy final may still need reconciliation after rollover.
                        and_(
                            nfl_api_game.c.event_id.is_not(None),
                            nfl_api_game.c.phase.in_(FINAL),
                            nfl_api_game.c.details_phase.is_(None),
                        ),
                    ),
                )
            ).all()
        return [
            Watched(
                r.game_id,
                r.event_id,
                r.slug,
                r.kickoff,
                r.phase,
                r.summary_hash,
                r.details_observed_at,
                r.details_phase,
            )
            for r in rows
        ]

    def poll(self, now: datetime) -> float:
        """Refresh week state and read every active game's full record."""
        assert self.week is not None
        summary_error = None
        try:
            payload, _ = self._get(
                "summaries",
                "/football/v2/stats/live/game-summaries",
                {"season": self.season, "seasonType": self.week[0], "week": self.week[1]},
                fresh=True,
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise SourceError("NFL_API_SUMMARIES_INVALID")
            summaries = {
                str(s["gameId"]): s
                for s in payload["data"]
                if isinstance(s, dict) and s.get("gameId")
            }
        except SourceError as error:
            if error.code == "RATE_LIMITED":
                raise
            summary_error = error
            summaries = {}

        watched = self._watched()
        if self.ids_at is None or now - self.ids_at > timedelta(hours=6):
            self.ids, self.ids_at = gsis_to_espn(self.uow), now
        if self.detail_pool is not None and len(watched) > 1:
            # Each thread keeps its own transport and request receipts. Wait for the whole
            # round so the same game can never be published by two overlapping rounds.
            reads = [
                self.detail_pool.submit(
                    self._poll_in_thread, game, summaries.get(game.game_id), now
                )
                for game in watched
            ]
            wait(reads)
            errors = [failure for read in reads if (failure := read.exception()) is not None]
            for failure in errors:
                if not isinstance(failure, (SourceError, ValueError, KeyError, TypeError)):
                    raise failure
            limits = [e for e in errors if isinstance(e, SourceError) and e.code == "RATE_LIMITED"]
            if limits:
                raise max(limits, key=lambda error: error.retry_after_seconds or 0)
            any_active = any(read.result() for read in reads if read.exception() is None)
            if errors and not any_active:
                raise errors[0]
            for failure in errors:
                self.log(
                    event="game_error",
                    code=failure.code if isinstance(failure, SourceError) else "NFL_API_INVALID",
                )
        else:
            results = [self._poll_game(game, summaries.get(game.game_id), now) for game in watched]
            any_active = any(results)

        if summary_error is not None:
            if not any_active:
                raise summary_error
            self.log(event="summary_error", code=summary_error.code)
        pregame = any(
            g.kickoff is not None and timedelta(0) <= g.kickoff - now <= timedelta(minutes=30)
            for g in watched
        )
        return ACTIVE_SECONDS if any_active else PREGAME_SECONDS if pregame else IDLE_SECONDS

    def _poll_in_thread(self, game: Watched, summary: dict[str, Any] | None, now: datetime) -> bool:
        if not hasattr(self.detail_clients, "client"):
            self.detail_clients.client = NflApiClient()
        client: NflApiClient = self.detail_clients.client
        return self._poll_game(game, summary, now, client=client)

    def _poll_game(
        self,
        game: Watched,
        summary: dict[str, Any] | None,
        now: datetime,
        *,
        client: NflApiClient | None = None,
    ) -> bool:
        reported = (summary or {}).get("phase")
        phase = reported if isinstance(reported, str) and reported else game.phase
        if game.details_phase in FINAL:
            phase = game.details_phase
        elif game.phase in FINAL and phase not in FINISHED:
            phase = game.phase  # a lagging summary cannot reopen a completed record
        near_kickoff = game.kickoff is not None and (
            game.kickoff - timedelta(minutes=5) <= now <= game.kickoff + timedelta(hours=6)
        )
        active = phase not in FINISHED and (phase not in NOT_ACTIVE or near_kickoff)
        final_pending = (
            game.event_id is not None and phase in FINAL and game.details_phase not in FINAL
        )
        active = active or (final_pending and near_kickoff)
        digest = (
            hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()
            if summary
            else None
        )
        changed = digest is not None and digest != game.summary_hash
        check_final = game.event_id is not None and phase in FINAL and (final_pending or changed)

        if game.event_id and (active or check_final):
            detail_phase = self.read_game(
                game, reason="active" if active else "final", client=client
            )
            if detail_phase in FINAL:
                phase, active, check_final = detail_phase, False, False
            elif detail_phase not in NOT_ACTIVE and not check_final:
                phase = detail_phase
        values: dict[str, Any] = {}
        if changed and not check_final:
            values.update(summary=summary, summary_hash=digest, observed_at=now)
        # Linked finals set their phase when they publish. Keep unlinked summary
        # phases so discovery can retry their details once an event is found.
        if phase != game.phase and (phase not in FINAL or not game.event_id) and not check_final:
            values["phase"] = phase
        if values:
            statement = update(nfl_api_game).where(
                nfl_api_game.c.game_id == game.game_id, nfl_api_game.c.observed_at <= now
            )
            if phase not in FINAL:
                statement = statement.where(
                    or_(
                        nfl_api_game.c.details_phase.is_(None),
                        nfl_api_game.c.details_phase.not_in(FINAL),
                    )
                )
            with self.uow.engine.begin() as c:
                c.execute(statement.values(**values))
        return active

    def read_game(
        self, game: Watched, *, reason: str, client: NflApiClient | None = None
    ) -> str | None:
        game_id, event_id = game.game_id, game.event_id
        assert event_id is not None
        details, body = self._get(
            "v2",
            f"/experience/v2/gamedetails/{game_id}",
            INCLUDES,
            fresh=True,
            client=client,
            game=game_id,
            event_id=event_id,
            reason=reason,
        )
        now = self.clock()
        if not isinstance(details, dict) or details.get("id") != game_id:
            raise SourceError("NFL_API_DETAILS_INVALID")
        # Schedule responses omit this identifier. The detail can supply it before the first play.
        if (slug := _slug(details)) is not None and slug != game.slug:
            with self.uow.engine.begin() as c:
                c.execute(
                    update(nfl_api_game).where(nfl_api_game.c.game_id == game_id).values(slug=slug)
                )
        summary = details.get("summary")
        summary = summary if isinstance(summary, dict) else {}
        reported = summary.get("phase")
        phase = reported if isinstance(reported, str) else None
        if game.details_phase in FINAL and phase not in FINAL:
            return None
        digest = hashlib.sha256(body).hexdigest()
        nfl_read = store.NflPlayRead(game_id, phase)
        if store.plays_unchanged(self.uow, event_id, digest, now, nfl_read=nfl_read):
            return phase
        with self.uow.engine.connect() as c:
            espn = c.execute(
                select(nfl_game.c.payload).where(nfl_game.c.event_id == event_id)
            ).scalar()
            codes = self._espn_teams()
        if not espn:
            return None
        home, away = espn["home_team_id"], espn["away_team_id"]
        link = GameLink(game_id, event_id, home, away, codes.get(home, ""), codes.get(away, ""))
        plays = to_live_plays(details, link, self.ids, self.season)
        if not any(p.kind != "administrative" for p in plays):
            return None  # nothing to show yet: ESPN keeps the game
        if phase in FINAL and not _usable_final(plays, summary, phase):
            return None
        change = store.publish_plays(
            self.uow, event_id, plays, now, body_hash=digest, nfl_read=nfl_read
        )
        if change.any:
            self.live_log.write(
                self.lane,
                "published",
                {},
                game=game_id,
                event_id=event_id,
                received_at=now.isoformat(),
                published_at=self.clock().isoformat(),
                introduced=change.introduced,
                revised=change.revised,
                cancelled=change.cancelled,
            )
        if change.any:
            self.log(
                event="plays",
                game=event_id,
                introduced=len(change.introduced),
                revised=len(change.revised),
                cancelled=len(change.cancelled),
            )
        return phase

    def step(self) -> float:
        now = self.clock()
        if self.summaries_due is not None and now < self.summaries_due:
            return min(1.0, (self.summaries_due - now).total_seconds())
        try:
            if (
                self.week is None
                or self.discovered_at is None
                or (now - self.discovered_at).total_seconds() >= DISCOVER_SECONDS
            ):
                self.discover(now)
            started = self.clock()
            wait = self.poll(started)
        except (SourceError, ValueError, KeyError, TypeError) as error:
            code = error.code if isinstance(error, SourceError) else "NFL_API_INVALID"
            self.failures += 1
            freshness.record_failure(
                self.uow,
                SOURCE,
                code,
                now=self.clock(),
                cadence_seconds=int(ACTIVE_SECONDS),
                stale_after_seconds=STALE_SECONDS,
            )
            self.log(event="error", code=code)
            backoff = min(60.0, 2.0 * 2 ** min(self.failures, 5))
            retry_after = error.retry_after_seconds if isinstance(error, SourceError) else None
            self.summaries_due = self.clock() + timedelta(seconds=max(backoff, retry_after or 0))
            return 1.0
        self.failures = 0
        freshness.record_success(
            self.uow,
            SOURCE,
            now=self.clock(),
            cadence_seconds=max(1, int(wait)),
            stale_after_seconds=int(max(STALE_SECONDS, 3 * wait)),
            changed=False,
        )
        self.summaries_due = started + timedelta(seconds=wait)
        return min(1.0, max(0.0, (self.summaries_due - self.clock()).total_seconds()))
