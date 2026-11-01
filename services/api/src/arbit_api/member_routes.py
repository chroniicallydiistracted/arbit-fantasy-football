"""Session-authorized stored facts and bounded administrative actions."""

import hmac
from collections.abc import Awaitable, Callable
from ipaddress import ip_address
from typing import Any, Literal, cast
from uuid import UUID

from arbit_data.db import UnitOfWork
from arbit_data.league import LeagueDocument
from arbit_data.league_store import read_current, read_snapshot
from arbit_data.members import (
    MemberError,
    account_exists,
    authenticate,
    bind_manager,
    consume_flow,
    create_flow,
    create_invitation,
    csrf_token,
    list_accounts,
    logout,
    manager_ids,
    reactivate_account,
    read_preferences,
    revoke_binding,
    revoke_sessions,
    sign_in,
    update_preferences,
)
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from arbit_api.member_contracts import (
    Account,
    AdminDirectory,
    AuthStatus,
    BindingRequest,
    FixtureRequest,
    FrontOffice,
    InviteRequest,
    InviteResponse,
    Me,
    PlayerFacts,
    PlayerSearch,
    Preferences,
    ReactivateRequest,
    RevokeRequest,
    Snapshot,
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
from arbit_api.settings import RuntimeSettings

COOKIE = "arbit_session"
FLOW_COOKIE = "arbit_flow"


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
        if admin and result["role"] != "admin":
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
            source_status=cast(Literal["fresh", "stale", "unavailable", "degraded"], source_status),
            stale=health["stale"] or source_status == "unavailable",
            season=season,
            scoring_period=document.scoring_period,
            matchup_period=document.matchup_period,
        )
        return result, document, snapshot

    def member_teams(account_id: UUID, document: LeagueDocument) -> list[Team]:
        approved = manager_ids(uow, account_id, season)
        return [
            Team.model_validate(t.model_dump(exclude={"managers", "primary_manager"}))
            for t in document.teams
            if approved.intersection(t.managers)
        ]

    def require_binding(
        member: dict[str, Any], document: LeagueDocument | None = None
    ) -> LeagueDocument:
        if not manager_ids(uow, member["id"], season):
            raise HTTPException(403, "BINDING_REQUIRED")
        if document is None:
            _, document, _ = stored()
        if not member_teams(member["id"], document):
            raise HTTPException(403, "BINDING_REQUIRED")
        return document

    def team_facts(document: LeagueDocument) -> list[Team]:
        return [
            Team.model_validate(t.model_dump(exclude={"managers", "primary_manager"}))
            for t in document.teams
        ]

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
            )
            response = RedirectResponse("/", status_code=303)
            cookie(response, COOKIE, token, 30 * 86400)
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
        def fixture_login(body: FixtureRequest, response: Response) -> Success:
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
            )
            cookie(response, COOKIE, token, 30 * 86400)
            return Success()

    @router.get("/api/v1/me", response_model=Me)
    def me(request: Request) -> Me:
        member = principal(request)
        current = read_current(uow, season)
        teams = (
            member_teams(member["id"], LeagueDocument.model_validate(current["league"]))
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
        )

    @router.get("/api/v1/front-office", response_model=FrontOffice)
    def front_office(
        request: Request,
        team_id: UUID | None = None,
        matchup_period: int | None = Query(default=None, ge=1, le=30),
    ) -> FrontOffice:
        member = principal(request)
        _, document, snapshot = stored()
        allowed = member_teams(member["id"], document)
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
        roster = [] if historical else [p for p in document.players if p.team_id == chosen.id]
        return FrontOffice(
            snapshot=snapshot,
            team=chosen,
            matchup=matchup,
            roster=roster,
            standings=team_facts(document),
            matchup_periods=periods,
            selected_matchup_period=period,
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
        return PlayerSearch(snapshot=snapshot, players=found)

    @router.get("/api/v1/players/{entity_id}", response_model=PlayerFacts)
    def player(request: Request, entity_id: UUID, snapshot_id: UUID | None = None) -> PlayerFacts:
        member = principal(request)
        require_binding(member)
        _, document, snapshot = stored(snapshot_id)
        found = next((p for p in document.players if p.id == entity_id), None)
        if found is None:
            raise HTTPException(404, "PLAYER_NOT_FOUND")
        return PlayerFacts(snapshot=snapshot, player=found)

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
