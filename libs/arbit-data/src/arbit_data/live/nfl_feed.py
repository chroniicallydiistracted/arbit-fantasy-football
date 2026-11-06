"""The NFL API live lane (OWN-041): discover games, poll them, detect changes, publish.

The owner's four steps, run by the worker's `nfl` lane:
1. **Discover.** The NFL week containing today (`/football/v2/weeks/date/{date}`), then that
   week's schedule, gives each game's UUID and kickoff. Each is linked to ESPN's event, which the
   ESPN scoreboard lane keeps, by kickoff time and teams.
2. **Poll.** One small request (`/football/v2/stats/live/game-summaries`, about 11 kB for the
   week) gives every game's phase, clock, down, spot and score. It is read every 2 seconds while a
   game is on, every 30 within half an hour of a kickoff, and every 5 minutes otherwise.
3. **Detect.** A game whose summary changed is fetched in full (`/experience/v2/gamedetails`),
   and an active game is refetched every 20 seconds anyway, so corrections to earlier plays are
   seen. Its plays become ESPN-shaped plays (`nfl_api.to_live_plays`) and are compared with the
   stored revisions play by play.
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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.client import HTTPException
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data import freshness
from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.http_deadline import DeadlineHTTPSHandler
from arbit_data.espn.transport import _NoRedirect, _retry_after
from arbit_data.live import nfl_log, store
from arbit_data.live.nfl_api import NFL_CODES, GameLink, to_live_plays
from arbit_data.public_sources.transport import MAX_BYTES
from arbit_data.schema import entity_alias, nfl_api_game, nfl_game, nfl_play_revision, nfl_team

HOST = "https://api.nfl.com"
SOURCE = "nfl.api.plays"
ACTIVE_SECONDS, PREGAME_SECONDS, IDLE_SECONDS = 2.0, 30.0, 300.0
REFRESH_SECONDS = 20.0  # an active game is refetched this often, for corrections
UNLISTED_SECONDS = 5.0  # a live game the summaries don't list is fetched in full this often
CHASE_SECONDS = 30.0  # after the summary changes, how long to keep fetching a record still cached
DISCOVER_SECONDS = 6 * 3600
STALE_SECONDS = 90  # past this the ESPN lane takes the game's plays back (the fallback)
FINAL = {"FINAL", "FINAL_OVERTIME"}
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


def retire_espn_leftovers(uow: UnitOfWork, event_id: str, nfl_ids: set[str]) -> int:
    """ESPN numbers timeouts and two-minute warnings itself, so once the NFL has a game, ESPN's
    administrative plays without an NFL record would show twice. They stop being current; their
    history stays. ESPN football plays always share the NFL's IDs and are never touched here."""
    with uow.engine.begin() as c:
        rows = c.execute(
            select(nfl_play_revision.c.play_id, nfl_play_revision.c.payload).where(
                nfl_play_revision.c.event_id == event_id, nfl_play_revision.c.is_current
            )
        ).all()
        stale = [
            r.play_id
            for r in rows
            if r.play_id not in nfl_ids
            and (r.payload or {}).get("source") != "nfl"
            and (r.payload or {}).get("kind") in ("administrative", "unknown")
        ]
        if stale:
            c.execute(
                update(nfl_play_revision)
                .where(
                    nfl_play_revision.c.event_id == event_id, nfl_play_revision.c.play_id.in_(stale)
                )
                .values(is_current=False)
            )
    return len(stale)


def nfl_primary(uow: UnitOfWork, event_id: str, now: datetime) -> bool:
    """Whether the NFL lane has this game's plays fresh, so the ESPN lane leaves them alone."""
    with uow.engine.connect() as c:
        seen = c.scalar(
            select(nfl_api_game.c.details_observed_at).where(nfl_api_game.c.event_id == event_id)
        )
    return seen is not None and now - seen <= timedelta(seconds=STALE_SECONDS)


@dataclass
class Watched:
    game_id: str
    event_id: str | None
    slug: str | None
    kickoff: datetime | None
    phase: str | None
    summary_hash: str | None
    details_at: datetime | None


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
        self.week: tuple[str, int] | None = None  # (season type, week)
        self.discovered_at: datetime | None = None
        self.summaries_due: datetime | None = None
        self.ids: dict[str, str] = {}
        self.ids_at: datetime | None = None
        self.failures = 0
        self.live_log = live_log or nfl_log.LiveLog(
            on_problem=lambda code: self.log(event="capture_problem", code=code)
        )
        self.chasing: dict[str, datetime] = {}  # game → until when to refetch a stale record
        self.plays_seen: dict[str, str] = {}  # game → fingerprint of its plays last fetched

    def _get(
        self, route: str, path: str, params: Mapping[str, Any] | None = None, **context: Any
    ) -> tuple[Any, bytes]:
        """A request, written to the live log with its timing, cache headers and what it says."""
        try:
            payload, body = self.client.get(path, params)
        except SourceError as error:
            self.live_log.request(self.lane, route, self.client, error=error.code, **context)
            raise
        facts: dict[str, Any] = {}
        if route == "summaries":
            facts = nfl_log.summaries(payload)
        elif route in ("v2", "v1", "slug", "weekly"):
            facts = nfl_log.plays(payload)
        self.live_log.request(self.lane, route, self.client, **context, **facts)
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
                    and_(
                        nfl_api_game.c.season == self.season,
                        nfl_api_game.c.season_type == self.week[0],
                        nfl_api_game.c.week == self.week[1],
                    )
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
            )
            for r in rows
        ]

    def poll(self, now: datetime) -> float:
        """Read the week's summaries and fetch every game that changed. Returns the next wait."""
        assert self.week is not None
        payload, _ = self._get(
            "summaries",
            "/football/v2/stats/live/game-summaries",
            {"season": self.season, "seasonType": self.week[0], "week": self.week[1]},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise SourceError("NFL_API_SUMMARIES_INVALID")
        summaries = {
            str(s["gameId"]): s for s in payload["data"] if isinstance(s, dict) and s.get("gameId")
        }
        watched = self._watched()
        any_active = False
        for game in watched:
            summary = summaries.get(game.game_id)
            phase = (summary or {}).get("phase") or game.phase
            digest = (
                hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()
                if summary
                else None
            )
            # Live from kickoff until the summary says final, whatever the summary shows: a
            # game the summaries don't list yet is still watched by its own record.
            near_kickoff = game.kickoff is not None and game.kickoff - timedelta(
                minutes=5
            ) <= now <= game.kickoff + timedelta(hours=6)
            active = phase not in NOT_ACTIVE or (near_kickoff and phase not in FINISHED)
            any_active = any_active or active
            changed = digest is not None and digest != game.summary_hash
            every = REFRESH_SECONDS if summary is not None else UNLISTED_SECONDS
            refresh = active and (
                game.details_at is None or (now - game.details_at).total_seconds() >= every
            )
            finished_unread = phase in FINAL and game.details_at is None and summary is not None
            deadline = self.chasing.get(game.game_id)
            chase = deadline is not None and now <= deadline
            moved = changed and (active or phase in FINAL)
            # If a final detail still lags after the fast chase, retry at the correction cadence.
            final_pending = phase in FINAL and changed and deadline is not None
            if final_pending and not chase and near_kickoff:
                moved = game.details_at is None or now - game.details_at >= timedelta(
                    seconds=REFRESH_SECONDS
                )
                any_active = True
            acknowledged = not final_pending
            if game.event_id and (moved or chase or refresh or finished_unread):
                reason = (
                    "summary" if moved else "chase" if chase else "refresh" if refresh else "final"
                )
                before = self.plays_seen.get(game.game_id)
                detail_phase = self.read_game(game, reason=reason)
                acknowledged = True
                if phase in FINAL and detail_phase not in FINAL and near_kickoff:
                    self.chasing.setdefault(game.game_id, now + timedelta(seconds=CHASE_SECONDS))
                    any_active = True
                    acknowledged = False
                elif phase in FINISHED or self.plays_seen.get(game.game_id) != before:
                    self.chasing.pop(game.game_id, None)  # the record caught up
                elif moved:
                    # The summary moved but the record is still the cached copy: keep fetching it.
                    self.chasing[game.game_id] = now + timedelta(seconds=CHASE_SECONDS)
            if summary is not None and changed and (acknowledged or not near_kickoff):
                # A failed detail read must leave the summary eligible for retry, including final.
                with self.uow.engine.begin() as c:
                    c.execute(
                        update(nfl_api_game)
                        .where(nfl_api_game.c.game_id == game.game_id)
                        .values(summary=summary, summary_hash=digest, phase=phase, observed_at=now)
                    )
            if not any_active and game.game_id in self.chasing:
                any_active = now <= self.chasing[game.game_id]
            if game.game_id in self.chasing and not active and not near_kickoff:
                self.chasing.pop(game.game_id)
        pregame = any(
            g.kickoff is not None and timedelta(0) <= g.kickoff - now <= timedelta(minutes=30)
            for g in watched
        )
        return ACTIVE_SECONDS if any_active else PREGAME_SECONDS if pregame else IDLE_SECONDS

    def read_game(self, game: Watched, *, reason: str) -> str | None:
        game_id, event_id = game.game_id, game.event_id
        assert event_id is not None
        details, body = self._get(
            "v2",
            f"/experience/v2/gamedetails/{game_id}",
            INCLUDES,
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
        phase = (details.get("summary") or {}).get("phase")
        digest = hashlib.sha256(body).hexdigest()
        fingerprint = nfl_log.fingerprint((details.get("driveChart") or {}).get("plays"))
        if self.ids_at is None or now - self.ids_at > timedelta(hours=6):
            self.ids, self.ids_at = gsis_to_espn(self.uow), now
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
        change = store.publish_plays(self.uow, event_id, plays, now, body_hash=digest)
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
        retire_espn_leftovers(self.uow, event_id, {p.provider_id for p in plays})
        with self.uow.engine.begin() as c:
            c.execute(
                update(nfl_api_game)
                .where(nfl_api_game.c.game_id == game_id)
                .values(details_hash=digest, details_observed_at=now)
            )
        self.plays_seen[game_id] = fingerprint
        if change.any:
            self.log(
                event="plays",
                game=event_id,
                introduced=len(change.introduced),
                revised=len(change.revised),
                cancelled=len(change.cancelled),
            )
        return phase if isinstance(phase, str) else None

    def step(self) -> float:
        now = self.clock()
        try:
            if (
                self.week is None
                or self.discovered_at is None
                or (now - self.discovered_at).total_seconds() >= DISCOVER_SECONDS
            ):
                self.discover(now)
            if self.summaries_due is not None and now < self.summaries_due:
                return min(1.0, (self.summaries_due - now).total_seconds())
            wait = self.poll(now)
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
        self.summaries_due = self.clock() + timedelta(seconds=wait)
        return min(1.0, wait)
