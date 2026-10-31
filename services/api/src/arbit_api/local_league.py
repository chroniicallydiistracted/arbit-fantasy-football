"""Local operator inspection, separate from the future invite-only member application."""

import hmac
from collections.abc import Awaitable, Callable
from ipaddress import ip_address
from typing import Any
from uuid import UUID

from arbit_data.db import UnitOfWork
from arbit_data.league_store import read_current, read_history, read_snapshot, read_sync
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from arbit_api.settings import RuntimeSettings

HEADERS = {"Cache-Control": "no-store"}


def install_operator_routes(
    app: FastAPI, settings: RuntimeSettings, database: Engine | None, season: int
) -> None:
    if settings.operator_token is None:
        return
    expected = ("Bearer " + settings.operator_token.get_secret_value()).encode()

    @app.middleware("http")
    async def local_access(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not request.url.path.startswith("/internal/league"):
            return await call_next(request)
        try:
            loopback = request.client is not None and ip_address(request.client.host).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            return JSONResponse({"error": "LOCAL_OPERATOR_ONLY"}, status_code=403, headers=HEADERS)
        supplied = request.headers.get("Authorization", "").encode()
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(
                {"error": "OPERATOR_AUTH_REQUIRED"}, status_code=401, headers=HEADERS
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def serve(query: Callable[[UnitOfWork], Any]) -> JSONResponse:
        if database is None:
            return JSONResponse(
                {"error": "DATABASE_NOT_CONFIGURED"}, status_code=503, headers=HEADERS
            )
        try:
            result = query(UnitOfWork(database))
            if result is None:
                return JSONResponse(
                    {"error": "SNAPSHOT_NOT_FOUND"}, status_code=404, headers=HEADERS
                )
            return JSONResponse(result, headers=HEADERS)
        except SQLAlchemyError:
            return JSONResponse({"error": "DATABASE_UNAVAILABLE"}, status_code=503, headers=HEADERS)

    @app.get("/internal/league/current")
    def current() -> JSONResponse:
        return serve(lambda uow: read_current(uow, season))

    @app.get("/internal/league/history")
    def history(limit: int = Query(default=50, ge=1, le=100)) -> JSONResponse:
        return serve(lambda uow: {"revisions": read_history(uow, season, limit)})

    @app.get("/internal/league/snapshots/{snapshot_id}")
    def snapshot(snapshot_id: UUID) -> JSONResponse:
        def scoped(uow: UnitOfWork) -> Any:
            result = read_snapshot(uow, snapshot_id)
            return result if result is not None and result["league"]["season"] == season else None

        return serve(scoped)

    @app.get("/internal/league/sync")
    def sync() -> JSONResponse:
        return serve(lambda uow: read_sync(uow, season))
