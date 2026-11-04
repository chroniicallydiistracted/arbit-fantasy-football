"""Session-authorized stored facts and bounded administrative actions."""

import asyncio
import hmac
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from ipaddress import ip_address
from typing import Any, Literal, cast
from uuid import UUID

from arbit_data import freshness
from arbit_data.db import UnitOfWork
from arbit_data.league import LeagueDocument, Matchup, MatchupSide, Player
from arbit_data.league_store import read_current, read_snapshot
from arbit_data.live import store as live_store
from arbit_data.members import (
    SESSION_ABSOLUTE,
    MemberError,
    account_exists,
    authenticate,
    bind_manager,
    consume_flow,
    create_flow,
    create_invitation,
    csrf_token,
    is_observer,
    list_accounts,
    list_sessions,
    logout,
    manager_ids,
    reactivate_account,
    read_preferences,
    revoke_binding,
    revoke_device,
    revoke_sessions,
    sign_in,
    update_preferences,
)
from fastapi import APIRouter, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from arbit_api.member_contracts import (
    Account,
    AdminDirectory,
    AuthStatus,
    BindingRequest,
    DeviceSession,
    DeviceSessions,
    FixtureRequest,
    FrontOffice,
    InviteRequest,
    InviteResponse,
    LiveDrive,
    LiveGameDetail,
    LiveGameRow,
    LiveGames,
    LiveLastPlay,
    LiveLeader,
    LivePlayRow,
    LivePlays,
    LiveSituation,
    LiveTeam,
    LiveTeamStat,
    LiveVenue,
    LiveWeather,
    LiveWinPoint,
    Me,
    PlayerFacts,
    PlayerNfl,
    PlayerSearch,
    Preferences,
    ReactivateRequest,
    RevokeDevice,
    RevokeRequest,
    RosterPlayer,
    SeasonCell,
    Snapshot,
    SourceRow,
    Sources,
    StartRequest,
    StartResponse,
    Success,
    Team,
    Teams,
)
from arbit_api.oidc import OidcClient
from arbit_api.problems import (
    PRIVATE_HEADERS,
    install_problem_openapi,
    is_member_path,
    problem_response,
    problem_responses,
    request_id,
)
from arbit_api.realtime import EventHub, describe_device, event_stream, parse_cursor
from arbit_api.settings import RuntimeSettings

# What the read-only dev account may still change: its own session and preferences.
OBSERVER_WRITES = ("/auth/logout", "/api/v1/me/preferences")
COOKIE = "arbit_session"
SESSION_COOKIE_SECONDS = int(SESSION_ABSOLUTE.total_seconds())
FLOW_COOKIE = "arbit_flow"
# Display order only. Slot legality and counts always come from stored rules.
SLOT_ORDER = {
    slot: index
    for index, slot in enumerate(
        ("QB", "RB", "RB_WR", "WR", "WR_TE", "TE", "FLEX", "OP", "DST", "K", "BENCH", "IR")
    )
}


def _cents(value: Decimal | None) -> Decimal | None:
    """Official totals at the verified 0.01 half-up policy. ESPN serializes binary floats."""
    return None if value is None else value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _team(team: Any) -> Team:
    facts = Team.model_validate(team.model_dump(exclude={"managers", "primary_manager"}))
    return facts.model_copy(
        update={
            "points_for": _cents(facts.points_for),
            "points_against": _cents(facts.points_against),
        }
    )


def _matchup(matchup: Matchup) -> Matchup:
    def side(value: MatchupSide | None) -> MatchupSide | None:
        if value is None:
            return None
        return value.model_copy(update={"official_points": _cents(value.official_points)})

    return matchup.model_copy(update={"home": side(matchup.home), "away": side(matchup.away)})


def _roster_key(player: Player) -> tuple[int, str]:
    return (SLOT_ORDER.get(player.lineup_slot or "", len(SLOT_ORDER)), player.display_name)


def _standing_key(team: Team) -> tuple[bool, int, str]:
    return (team.playoff_seed is None, team.playoff_seed or 0, team.name)


def _season_strip(document: LeagueDocument, team_id: UUID) -> list[SeasonCell]:
    """Own results by period. Totals only count as a result once the period has completed."""
    cells = []
    for matchup in sorted(document.matchups, key=lambda m: m.matchup_period):
        sides = [side for side in (matchup.home, matchup.away) if side is not None]
        own = next((side for side in sides if side.team_id == team_id), None)
        if own is None:
            continue
        other = next((side for side in sides if side.team_id != team_id), None)
        result: Literal["win", "loss", "tie"] | None = None
        if (
            matchup.matchup_period < document.matchup_period
            and other is not None
            and own.official_points is not None
            and other.official_points is not None
        ):
            result = (
                "win"
                if own.official_points > other.official_points
                else "loss"
                if own.official_points < other.official_points
                else "tie"
            )
        cells.append(
            SeasonCell(
                matchup_period=matchup.matchup_period,
                opponent_team_id=other.team_id if other else None,
                own_points=_cents(own.official_points),
                opponent_points=_cents(other.official_points) if other else None,
                result=result,
            )
        )
    return cells


def _playoff_team_count(rules: dict[str, Any] | None) -> int | None:
    schedule = ((rules or {}).get("provider_policy") or {}).get("scheduleSettings") or {}
    count = schedule.get("playoffTeamCount")
    return count if type(count) is int and count > 0 else None


def install_member_routes(
    app: FastAPI, settings: RuntimeSettings, database: Engine | None, season: int
) -> None:
    if settings.auth_mode == "disabled":
        return
    if database is None:
        raise ValueError("member authentication requires a database")
    # Verify actual injected database too; a safe URL in settings cannot bless an unsafe engine.
    if settings.auth_mode == "fixture" and (
        database.url.host not in ("127.0.0.1", "localhost", "::1")
        or not (database.url.database or "").endswith(("_test", "_fixture"))
    ):
        raise ValueError("fixture engine requires a dedicated loopback test database")
    router = APIRouter(responses=problem_responses())
    uow = UnitOfWork(database)
    provider = OidcClient(settings)
    secure = settings.environment == "production" or str(settings.public_origin).startswith(
        "https://"
    )

    def cookie(response: Response, key: str, value: str, max_age: int) -> None:
        response.set_cookie(
            key, value, max_age=max_age, httponly=True, secure=secure, samesite="lax", path="/"
        )

    @app.middleware("http")
    async def boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if not is_member_path(path):
            return await call_next(request)
        identifier = request_id(request)
        if settings.auth_mode == "fixture":
            try:
                local_peer = (
                    request.client is not None and ip_address(request.client.host).is_loopback
                )
            except ValueError:
                local_peer = False
            if not local_peer:
                return problem_response(request, 403, "FIXTURE_LOOPBACK_ONLY")
        # Remove sensitive authorization-code query strings before server access logging.
        if path == "/auth/callback":
            request.state.oidc_query = dict(request.query_params)
            request.scope["query_string"] = b""
        try:
            token = request.cookies.get(COOKIE, "")
            principal = authenticate(uow, token) if token else None
            if is_observer(principal):
                if settings.environment == "production":
                    principal = None  # the dev account never opens a production app
                elif (
                    request.method not in ("GET", "HEAD", "OPTIONS") and path not in OBSERVER_WRITES
                ):
                    return problem_response(request, 403, "OBSERVER_READ_ONLY")
            request.state.principal = principal
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if request.headers.get("origin") != settings.public_origin:
                    return problem_response(request, 403, "ORIGIN_REQUIRED")
                if path not in ("/auth/start", "/auth/fixture") and (
                    not token
                    or not hmac.compare_digest(
                        request.headers.get("x-csrf-token", "").encode(), csrf_token(token).encode()
                    )
                ):
                    return problem_response(request, 403, "CSRF_REQUIRED")
            if path.startswith("/api/") and principal is None:
                return problem_response(request, 401, "AUTH_REQUIRED")
            response = await call_next(request)
        except SQLAlchemyError:
            response = problem_response(request, 503, "MEMBER_STORAGE_UNAVAILABLE")
        except MemberError as error:
            code = str(error)
            status = (
                429
                if code == "SIGN_IN_LIMIT"
                else 409
                if code
                in (
                    "PREFERENCES_CONFLICT",
                    "BINDING_CONFLICT",
                    "INVITATION_LIMIT",
                    "LAST_ADMINISTRATOR",
                )
                else 404
                if code == "ACCOUNT_NOT_FOUND"
                else 403
            )
            response = problem_response(
                request, status, code, retry_after=600 if status == 429 else None
            )
        except ValidationError:
            response = problem_response(request, 503, "MEMBER_FACTS_UNAVAILABLE")
        response.headers["X-Request-ID"] = identifier
        for key, value in PRIVATE_HEADERS.items():
            response.headers[key] = value
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, error: RequestValidationError) -> Response:
        if not is_member_path(request.url.path):
            return await request_validation_exception_handler(request, error)
        return problem_response(request, 422, "INVALID_REQUEST")

    @app.exception_handler(StarletteHTTPException)
    async def denied(request: Request, error: StarletteHTTPException) -> Response:
        if not is_member_path(request.url.path):
            return await http_exception_handler(request, error)
        code = (
            error.detail
            if isinstance(error.detail, str) and error.detail.isupper()
            else {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
                error.status_code, "REQUEST_FAILED"
            )
        )
        return problem_response(request, error.status_code, code)

    def principal(request: Request, *, admin: bool = False) -> dict[str, Any]:
        result: dict[str, Any] | None = request.state.principal
        if result is None:
            raise HTTPException(401, "AUTH_REQUIRED")
        # The dev account reads administrator pages; the boundary refuses its changes.
        if admin and result["role"] != "admin" and not is_observer(result):
            raise HTTPException(403, "ADMIN_REQUIRED")
        return result

    def stored(snapshot_id: UUID | None = None) -> tuple[dict[str, Any], LeagueDocument, Snapshot]:
        result = read_snapshot(uow, snapshot_id) if snapshot_id else read_current(uow, season)
        if snapshot_id and not result:
            raise HTTPException(404, "SNAPSHOT_NOT_FOUND")
        if result is None:
            raise HTTPException(503, "SNAPSHOT_UNAVAILABLE")
        document = LeagueDocument.model_validate(result["league"])
        if document.season != season:
            raise HTTPException(404 if snapshot_id else 503, "SNAPSHOT_NOT_FOUND")
        health = result["sync"]
        if health.get("last_snapshot_id") != result["snapshot_id"]:
            health = {**health, "stale": True, "status": "stale"}
        status = health.get("status")
        source_status = {
            "fresh": "fresh",
            "healthy": "fresh",
            "stale": "stale",
            "degraded": "degraded",
            "paused": "degraded",
        }.get(status, "unavailable")
        snapshot = Snapshot(
            id=result["snapshot_id"],
            observed_at=result["observed_at"],
            confirmed_at=health.get("last_success_at")
            if health.get("last_snapshot_id") == result["snapshot_id"]
            else None,
            source_status=cast(Literal["fresh", "stale", "unavailable", "degraded"], source_status),
            stale=health["stale"] or source_status == "unavailable",
            season=season,
            scoring_period=document.scoring_period,
            matchup_period=document.matchup_period,
        )
        return result, document, snapshot

    def member_teams(member: dict[str, Any], document: LeagueDocument) -> list[Team]:
        if is_observer(member):
            return [_team(t) for t in document.teams]  # the dev account can view any team
        approved = manager_ids(uow, member["id"], season)
        return [_team(t) for t in document.teams if approved.intersection(t.managers)]

    def require_binding(
        member: dict[str, Any], document: LeagueDocument | None = None
    ) -> LeagueDocument:
        if not is_observer(member) and not manager_ids(uow, member["id"], season):
            raise HTTPException(403, "BINDING_REQUIRED")
        if document is None:
            _, document, _ = stored()
        if not member_teams(member, document):
            raise HTTPException(403, "BINDING_REQUIRED")
        return document

    def with_nfl(document: LeagueDocument, players: Iterable[Player]) -> list[RosterPlayer]:
        """Attach NFL team, bye and this period's game. Missing directory data stays unknown."""
        directory = live_store.read_directory(uow)
        games = live_store.read_period_games(uow, season, document.scoring_period)
        by_espn = {row.espn_id: row for row in directory.values()}
        result = []
        for player in players:
            row = directory.get(player.nfl_team_id) if player.nfl_team_id else None
            nfl = None
            if row is not None:
                game = games.get(row.espn_id)
                home = game.home_espn_id == row.espn_id if game else None
                opponent = (
                    by_espn.get(game.away_espn_id if home else game.home_espn_id) if game else None
                )
                nfl = PlayerNfl(
                    team_abbreviation=row.abbreviation,
                    team_name=f"{row.location} {row.name}",
                    bye_week=row.bye_week,
                    on_bye=row.bye_week == document.scoring_period,
                    opponent_abbreviation=opponent.abbreviation if opponent else None,
                    home=home,
                    kickoff=game.kickoff if game else None,
                )
            result.append(RosterPlayer.model_validate({**player.model_dump(), "nfl": nfl}))
        return result

    def team_facts(document: LeagueDocument) -> list[Team]:
        return sorted((_team(t) for t in document.teams), key=_standing_key)

    @router.get("/auth/status", response_model=AuthStatus)
    def auth_status(request: Request) -> AuthStatus:
        signed_in = request.state.principal is not None
        return AuthStatus(
            enabled=True,
            authenticated=signed_in,
            csrf_token=csrf_token(request.cookies[COOKIE]) if signed_in else None,
            fixture=settings.auth_mode == "fixture",
        )

    @router.post("/auth/start", response_model=StartResponse)
    def auth_start(body: StartRequest, response: Response) -> StartResponse:
        if settings.auth_mode != "oidc":
            raise HTTPException(503, "OIDC_NOT_CONFIGURED")
        flow = create_flow(uow, body.invitation)
        cookie(response, FLOW_COOKIE, flow["browser"], 600)
        return StartResponse(authorization_url=provider.authorization_url(flow))

    @router.get("/auth/callback", response_class=RedirectResponse)
    def auth_callback(request: Request) -> Response:
        query = request.state.oidc_query
        try:
            state, code = query.get("state", ""), query.get("code", "")
            if not code or len(code) > 4096 or "error" in query or settings.auth_mode != "oidc":
                raise ValueError("SIGN_IN_FAILED")
            flow = consume_flow(uow, state, request.cookies.get(FLOW_COOKIE, ""))
            claims = provider.exchange(code, flow)
            token, _ = sign_in(
                uow,
                str(settings.oidc_issuer),
                claims["sub"],
                claims["email"],
                claims["email_verified"] is True,
                invitation_hash=flow["invitation_hash"],
                display_name=claims.get("name", "FFA member"),
                replaces=request.cookies.get(COOKIE),
                device_label=describe_device(request.headers.get("user-agent")),
            )
            response = RedirectResponse("/", status_code=303)
            cookie(response, COOKIE, token, SESSION_COOKIE_SECONDS)
        except Exception:
            # Provider and JOSE exceptions can contain tokens, codes and PII. Never return/log them.
            response = RedirectResponse("/?auth_error=sign_in_failed", status_code=303)
        response.delete_cookie(FLOW_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
        return response

    @router.post("/auth/logout", response_model=Success)
    def auth_logout(request: Request, response: Response) -> Success:
        logout(uow, request.cookies.get(COOKIE, ""))
        response.delete_cookie(COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
        return Success()

    if settings.auth_mode == "fixture":

        @router.post("/auth/fixture", response_model=Success)
        def fixture_login(request: Request, body: FixtureRequest, response: Response) -> Success:
            email = f"{body.member}@fiction.invalid"
            invite = (
                None
                if account_exists(uow, "https://fiction.invalid", body.member)
                else create_invitation(uow, "https://fiction.invalid", email)
            )
            token, _ = sign_in(
                uow,
                "https://fiction.invalid",
                body.member,
                email,
                True,
                invitation=invite,
                display_name=f"Fictional member {body.member}",
                replaces=request.cookies.get(COOKIE),
                device_label=describe_device(request.headers.get("user-agent")),
            )
            cookie(response, COOKIE, token, SESSION_COOKIE_SECONDS)
            return Success()

    @router.get("/api/v1/me", response_model=Me)
    def me(request: Request) -> Me:
        member = principal(request)
        current = read_current(uow, season)
        teams = (
            member_teams(member, LeagueDocument.model_validate(current["league"]))
            if current
            else []
        )
        team_id = teams[0].id if teams else None
        return Me(
            account=Account.model_validate({k: member[k] for k in ("id", "role", "display_name")}),
            binding_status="bound" if teams else "pending",
            team_id=team_id,
            current_team_id=team_id,
            teams=teams,
            season=season,
            preferences=Preferences.model_validate(read_preferences(uow, member["id"])),
            fixture=settings.auth_mode == "fixture",
            observer=is_observer(member),
        )

    @router.get("/api/v1/front-office", response_model=FrontOffice)
    def front_office(
        request: Request,
        team_id: UUID | None = None,
        matchup_period: int | None = Query(default=None, ge=1, le=30),
    ) -> FrontOffice:
        member = principal(request)
        stored_result, document, snapshot = stored()
        allowed = member_teams(member, document)
        if not allowed:
            raise HTTPException(403, "BINDING_REQUIRED")
        chosen = next((t for t in allowed if t.id == team_id), None) if team_id else allowed[0]
        if chosen is None:
            raise HTTPException(403, "TEAM_CONTEXT_DENIED")
        period = matchup_period or document.matchup_period
        periods = sorted({m.matchup_period for m in document.matchups} | {document.matchup_period})
        if period not in periods:
            raise HTTPException(404, "PERIOD_NOT_FOUND")
        matchup = next(
            (
                m
                for m in document.matchups
                if m.matchup_period == period
                and any(side is not None and side.team_id == chosen.id for side in (m.home, m.away))
            ),
            None,
        )
        historical = period != document.matchup_period
        roster = (
            []
            if historical
            else sorted((p for p in document.players if p.team_id == chosen.id), key=_roster_key)
        )
        return FrontOffice(
            snapshot=snapshot,
            team=chosen,
            matchup=_matchup(matchup) if matchup else None,
            roster=with_nfl(document, roster),
            standings=team_facts(document),
            matchup_periods=periods,
            selected_matchup_period=period,
            season_strip=_season_strip(document, chosen.id),
            playoff_team_count=_playoff_team_count(stored_result.get("rules")),
            historical_roster_unavailable=historical,
            fixture=settings.auth_mode == "fixture",
        )

    @router.get("/api/v1/league/teams", response_model=Teams)
    def teams(request: Request) -> Teams:
        member = principal(request)
        _, document, snapshot = stored()
        require_binding(member, document)
        return Teams(snapshot=snapshot, teams=team_facts(document))

    @router.get("/api/v1/players", response_model=PlayerSearch)
    def search_players(
        request: Request,
        query: str = Query(min_length=2, max_length=80),
        limit: int = Query(default=20, ge=1, le=20),
    ) -> PlayerSearch:
        member = principal(request)
        _, document, snapshot = stored()
        require_binding(member, document)
        needle = query.strip().casefold()
        if len(needle) < 2:
            raise HTTPException(422, "INVALID_SEARCH")
        found = sorted(
            (p for p in document.players if needle in p.display_name.casefold()),
            key=lambda p: (p.display_name, str(p.id)),
        )[:limit]
        return PlayerSearch(snapshot=snapshot, players=with_nfl(document, found))

    @router.get("/api/v1/players/{entity_id}", response_model=PlayerFacts)
    def player(request: Request, entity_id: UUID, snapshot_id: UUID | None = None) -> PlayerFacts:
        member = principal(request)
        require_binding(member)
        _, document, snapshot = stored(snapshot_id)
        found = next((p for p in document.players if p.id == entity_id), None)
        if found is None:
            raise HTTPException(404, "PLAYER_NOT_FOUND")
        return PlayerFacts(snapshot=snapshot, player=with_nfl(document, [found])[0])

    @router.put("/api/v1/me/preferences", response_model=Preferences)
    def preferences(request: Request, body: Preferences) -> Preferences:
        member = principal(request)
        existing = read_preferences(uow, member["id"])
        if [str(player) for player in body.watchlist] != existing["watchlist"]:
            document = require_binding(member)
            if not set(body.watchlist).issubset(p.id for p in document.players):
                raise HTTPException(422, "UNKNOWN_WATCHLIST_PLAYER")
        return Preferences.model_validate(
            update_preferences(uow, member["id"], body.version, body.theme, body.watchlist)
        )

    @router.get("/api/v1/me/sessions", response_model=DeviceSessions)
    def my_sessions(request: Request) -> DeviceSessions:
        member = principal(request)
        rows = list_sessions(uow, member["id"], request.cookies.get(COOKIE, ""))
        return DeviceSessions(sessions=[DeviceSession.model_validate(row) for row in rows])

    @router.post("/api/v1/me/sessions/revoke", response_model=Success)
    def end_my_session(request: Request, body: RevokeDevice) -> Success:
        member = principal(request)
        revoke_device(uow, member["id"], body.session_id)
        return Success()

    @router.get("/api/v1/sources", response_model=Sources)
    def sources(request: Request) -> Sources:
        member = principal(request)
        require_binding(member)
        admin = member["role"] == "admin"
        return Sources(
            sources=[
                SourceRow(
                    source=row.source,
                    label=row.label,
                    state=row.state,
                    last_success_at=row.last_success_at,
                    # Provider failure codes are operator detail, not member copy.
                    error_code=row.error_code if admin else None,
                )
                for row in freshness.read_sources(uow, season)
            ]
        )

    def own_team_players(member: dict[str, Any], document: LeagueDocument) -> list[Player]:
        allowed = {t.id for t in member_teams(member, document)}
        return [p for p in document.players if p.team_id in allowed]

    def game_row(
        game: dict[str, Any], teams: dict[str, Any], own_by_team: dict[str, list[str]]
    ) -> LiveGameRow:
        situation = game.get("situation") or {}
        # Outside live play there is no ball to place, even if the last reading had one.
        in_play = game["phase"] in ("in_progress", "overtime", "delayed")
        ball = situation.get("possession_team_id") if in_play else None

        def side(espn_id: str, score: str | None, where: str) -> LiveTeam:
            team = teams.get(espn_id)
            line = game.get(f"{where}_line") or {}
            return LiveTeam(
                abbreviation=team.abbreviation if team else None,
                name=f"{team.location} {team.name}" if team else None,
                score=score,
                color=line.get("color"),
                record=line.get("record"),
                periods=line.get("periods", []) if started else [],
                timeouts=situation.get(f"{where}_timeouts") if in_play else None,
                has_ball=ball == espn_id,
            )

        # ESPN reports 0 before kickoff. No game has been played, so the score is unknown.
        started = game["phase"] not in ("scheduled", "postponed", "cancelled", "unknown")
        return LiveGameRow(
            event_id=game["event_id"],
            phase=game["phase"],
            kickoff=game.get("date"),
            period=game.get("period") if started else None,
            clock=game.get("clock") if started else None,
            home=side(game["home_team_id"], game.get("home_score") if started else None, "home"),
            away=side(game["away_team_id"], game.get("away_score") if started else None, "away"),
            situation=live_situation(game) if in_play else None,
            venue=LiveVenue(**game["venue"]) if game.get("venue") else None,
            weather=LiveWeather(**game["weather"]) if game.get("weather") else None,
            broadcast=game.get("broadcast", []),
            own_players=own_by_team.get(game["home_team_id"], [])
            + own_by_team.get(game["away_team_id"], []),
            observed_at=game["observed_at"],
            changed_at=game["changed_at"],
        )

    def live_situation(game: dict[str, Any]) -> LiveSituation | None:
        raw = game.get("situation")
        if not raw:
            return None
        team = raw.get("possession_team_id")
        possession: Literal["home", "away"] | None = None
        if team == game["home_team_id"]:
            possession = "home"
        elif team == game["away_team_id"]:
            possession = "away"
        line, distance = raw.get("yard_line"), raw.get("distance")
        first_down = None
        if line is not None and distance is not None and possession:
            # The home team drives away from its own goal line, which is 0 on ESPN's scale.
            first_down = (
                min(100, line + distance) if possession == "home" else max(0, line - distance)
            )
        last = raw.get("last_play")
        return LiveSituation(
            down=raw.get("down"),
            distance=distance,
            short_text=raw.get("short_text"),
            field_text=raw.get("field_text"),
            yard_line=line,
            first_down_line=first_down,
            possession=possession,
            # ESPN's flag can outlast the snap: it was seen set during a timeout with no down.
            red_zone=raw.get("red_zone") if raw.get("down") is not None else None,
            last_play=LiveLastPlay(
                kind=last.get("kind_text"), text=last.get("text"), yards=last.get("yards")
            )
            if last
            else None,
        )

    def own_by_nfl_team(member: dict[str, Any], document: LeagueDocument) -> dict[str, list[str]]:
        directory = live_store.read_directory(uow)
        result: dict[str, list[str]] = {}
        for player in own_team_players(member, document):
            row = directory.get(player.nfl_team_id) if player.nfl_team_id else None
            if row is not None:
                result.setdefault(row.espn_id, []).append(player.display_name)
        return result

    def scoreboard_state() -> freshness.SourceStatus:
        return next(
            s for s in freshness.read_sources(uow, season) if s.source == freshness.SCOREBOARD
        )

    @router.get("/api/v1/live/games", response_model=LiveGames)
    def live_games(request: Request) -> LiveGames:
        member = principal(request)
        _, document, _ = stored()
        require_binding(member, document)
        status = scoreboard_state()
        board = live_store.read_games(uow, season)
        if board is None:
            return LiveGames(
                week=None,
                season_type=None,
                games=[],
                source_state=status.state,
                last_success_at=status.last_success_at,
            )
        own = own_by_nfl_team(member, document)
        return LiveGames(
            week=board["week"],
            season_type=board["season_type"],
            games=sorted(
                (game_row(game, board["teams"], own) for game in board["games"]),
                key=lambda g: (g.kickoff is None, g.kickoff, g.event_id),
            ),
            source_state=status.state,
            last_success_at=status.last_success_at,
        )

    @router.get("/api/v1/live/games/{event_id}", response_model=LiveGameDetail)
    def live_game(
        request: Request, event_id: str = Path(pattern=r"^[1-9][0-9]{0,19}$")
    ) -> LiveGameDetail:
        member = principal(request)
        _, document, _ = stored()
        require_binding(member, document)
        board = live_store.read_games(uow, season)
        game = next((g for g in (board or {}).get("games", []) if g["event_id"] == event_id), None)
        stored_game = live_store.read_game(uow, event_id)
        if board is None or game is None or stored_game is None:
            raise HTTPException(404, "GAME_NOT_FOUND")
        teams = board["teams"]

        def team_abbreviation(espn_id: str | None) -> str | None:
            team = teams.get(espn_id)
            return team.abbreviation if team else None

        detail = stored_game["detail"]
        return LiveGameDetail(
            game=game_row(game, teams, own_by_nfl_team(member, document)),
            leaders=[
                LiveLeader(
                    category=x["category"],
                    name=x.get("name"),
                    team=team_abbreviation(x.get("team_id")),
                    line=x.get("line"),
                )
                for x in game.get("leaders", [])
            ],
            drives=[
                LiveDrive(
                    team=team_abbreviation(d.get("team_id")),
                    result=d.get("result"),
                    plays=d.get("plays"),
                    yards=d.get("yards"),
                    elapsed=d.get("elapsed"),
                    start=d.get("start"),
                    end=d.get("end"),
                    scored=d.get("scored"),
                    current=d.get("current") is True,
                )
                for d in detail.get("drives", [])
            ],
            win_probability=[
                LiveWinPoint(home=p["home"]) for p in detail.get("win_probability", [])
            ],
            team_stats=[LiveTeamStat(**s) for s in detail.get("team_stats", [])],
            summary_observed_at=stored_game["summary_observed_at"],
        )

    @router.get("/api/v1/live/games/{event_id}/plays", response_model=LivePlays)
    def live_plays(
        request: Request,
        event_id: str = Path(pattern=r"^[1-9][0-9]{0,19}$"),
        own: bool = False,
        limit: int = Query(default=100, ge=1, le=400),
    ) -> LivePlays:
        member = principal(request)
        _, document, _ = stored()
        require_binding(member, document)
        board = live_store.read_games(uow, season)
        game = next((g for g in (board or {}).get("games", []) if g["event_id"] == event_id), None)
        if board is None or game is None:
            raise HTTPException(404, "GAME_NOT_FOUND")
        roster = {p.id for p in own_team_players(member, document)}
        aliases = live_store.athlete_espn_ids(uow, roster, datetime.now(UTC))
        plays = live_store.read_plays(
            uow, event_id, limit=limit, espn_ids=set(aliases) if own else None
        )
        detail = live_store.read_game(uow, event_id) or {}
        rows = [
            LivePlayRow(
                id=p["provider_id"],
                period=p["period"],
                clock=p["clock"],
                kind=p["kind"],
                text=p["text"],
                home_score=p["home_score"],
                away_score=p["away_score"],
                scoring=p["scoring_play"] is True,
                cancelled=p["cancelled"],
                corrected=p["corrected"],
                own=bool({x["espn_id"] for x in p["participants"]} & set(aliases)),
            )
            for p in plays
        ]
        return LivePlays(
            game=game_row(game, board["teams"], own_by_nfl_team(member, document)),
            plays=rows,
            plays_observed_at=detail.get("plays_observed_at"),
            has_participants=any(p["participants"] for p in plays),
        )

    hub = EventHub(uow)

    @router.get("/api/v1/events", response_class=StreamingResponse)
    async def events_stream(request: Request) -> StreamingResponse:
        member = principal(request)
        await asyncio.to_thread(require_binding, member)
        token = request.cookies.get(COOKIE, "")

        def check() -> bool:
            current = authenticate(uow, token)
            return current is not None and bool(manager_ids(uow, current["id"], season))

        async def still_authorized() -> bool:
            try:
                return await asyncio.to_thread(check)
            except SQLAlchemyError:
                return True  # Storage trouble isn't revocation; the next heartbeat checks again.

        return StreamingResponse(
            event_stream(hub, parse_cursor(request.headers.get("last-event-id")), still_authorized),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    @router.get("/api/v1/admin/directory", response_model=AdminDirectory)
    def admin_directory(request: Request) -> AdminDirectory:
        principal(request, admin=True)
        _, document, _ = stored()
        return AdminDirectory.model_validate(
            {
                "accounts": list_accounts(uow, season),
                "managers": [
                    {
                        "id": m.id,
                        "display_name": m.display_name,
                        "first_name": m.first_name,
                        "team_names": [t.name for t in document.teams if m.id in t.managers],
                        "team_ids": [t.id for t in document.teams if m.id in t.managers],
                    }
                    for m in document.managers
                ],
            }
        )

    @router.post("/api/v1/admin/invitations", response_model=InviteResponse)
    def invite(request: Request, body: InviteRequest) -> InviteResponse:
        member = principal(request, admin=True)
        if settings.auth_mode != "oidc":
            raise HTTPException(503, "OIDC_NOT_CONFIGURED")
        token = create_invitation(
            uow, str(settings.oidc_issuer), body.email, role=body.role, actor=member["id"]
        )
        return InviteResponse(invitation_url=f"{settings.public_origin}/join#{token}")

    @router.post("/api/v1/admin/bindings", response_model=Success)
    def bind(request: Request, body: BindingRequest) -> Success:
        member = principal(request, admin=True)
        _, document, _ = stored()
        if body.manager_id not in {m.id for m in document.managers}:
            raise HTTPException(422, "UNKNOWN_MANAGER")
        bind_manager(uow, body.account_id, body.manager_id, season, member["id"])
        return Success()

    @router.post("/api/v1/admin/bindings/revoke", response_model=Success)
    def unbind(request: Request, body: BindingRequest) -> Success:
        member = principal(request, admin=True)
        revoke_binding(uow, body.account_id, body.manager_id, season, member["id"])
        return Success()

    @router.post("/api/v1/admin/sessions/revoke", response_model=Success)
    def revoke(request: Request, body: RevokeRequest) -> Success:
        member = principal(request, admin=True)
        revoke_sessions(uow, body.account_id, actor=member["id"], suspend=body.suspend)
        return Success()

    @router.post("/api/v1/admin/accounts/reactivate", response_model=Success)
    def reactivate(request: Request, body: ReactivateRequest) -> Success:
        member = principal(request, admin=True)
        reactivate_account(uow, body.account_id, actor=member["id"])
        return Success()

    app.include_router(router)
    install_problem_openapi(app)
